"""Compaction manager for context management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from agent_kernel.providers.base import ModelInfo, PROVIDER_MODELS
from open_agent.agents.compaction import CompactionAgent
from open_agent.bus import EventBus
from open_agent.bus.events import Event
from open_agent.config.settings import CompactionSettings
from open_agent.core.context.pruning import PruningResult, PruningStrategy
from open_agent.persistence.models import AgentRun, Message, MessageRole
from open_agent.persistence.store import Store
from open_agent.providers.base import BaseProvider

logger = logging.getLogger(__name__)


@dataclass
class CompactionOptions:
    """Options for compaction operations."""
    
    session_id: str
    model: str
    total_tokens: int
    auto_compact: bool = True
    auto_prune: bool = True
    abort_signal: Any = None


@dataclass
class CompactionResult:
    """Result of a compaction operation."""
    
    summary: str
    tokens_before: int
    tokens_after: int
    was_pruned: bool = False
    prune_result: PruningResult | None = None


class CompactionManager:
    """Manages context compaction for open-agent sessions.
    
    Flow:
    1. Check if tokens exceed usable context
    2. If auto_prune: run pruning first (cheaper)
    3. If still over limit and auto_compact: run compaction agent
    4. Store summary as special message
    """
    
    # Default to 80% of max context as usable (leave room for output)
    USABLE_CONTEXT_RATIO = 0.8
    
    def __init__(
        self,
        store: Store,
        provider: BaseProvider,
        bus: EventBus,
        settings: CompactionSettings | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.bus = bus
        self.settings = settings or CompactionSettings()
        self.pruning = PruningStrategy(
            store, 
            protect_tokens=self.settings.prune_protect
        )
    
    async def is_overflow(
        self,
        tokens: int,
        model: str,
    ) -> bool:
        """Check if tokens exceed model's usable context.
        
        Args:
            tokens: Current token count
            model: Model ID string
            
        Returns:
            True if tokens exceed usable context
        """
        model_info = self._get_model_info(model)
        usable = int(model_info.max_context * self.USABLE_CONTEXT_RATIO)
        return tokens > usable
    
    def _get_model_info(self, model: str) -> ModelInfo:
        """Get model info for a given model ID."""
        # Find provider and model info
        for provider_name, models in PROVIDER_MODELS.items():
            for model_info in models:
                if model_info.model_id == model:
                    return model_info
        
        # Default fallback
        return ModelInfo(provider="unknown", model_id=model, max_context=128000)
    
    async def check_and_compact(
        self,
        session_id: str,
        agent_run: AgentRun,
        current_tokens: int,
        abort_signal: Any = None,
    ) -> CompactionResult | None:
        """Check if compaction is needed and run if necessary.
        
        Args:
            session_id: The session to check
            agent_run: Current agent run
            current_tokens: Current token count
            abort_signal: Optional abort signal
            
        Returns:
            CompactionResult if compaction occurred, None otherwise
        """
        model = agent_run.token_usage.model or "gpt-4o"
        
        # Check if we're over the limit
        if not await self.is_overflow(current_tokens, model):
            return None
        
        logger.info(
            f"Context overflow detected: {current_tokens} tokens "
            f"for model {model} in session {session_id}"
        )
        
        prune_result: PruningResult | None = None
        
        # Step 1: Prune if enabled
        if self.settings.auto_prune:
            prune_result = await self.pruning.prune(session_id)
            
            # Re-check tokens after pruning
            # (simplified - in reality we'd recalculate)
            if prune_result:
                current_tokens -= prune_result_tokens(prune_result)
                
                if not await self.is_overflow(current_tokens, model):
                    logger.info("Pruning sufficient, skipping compaction")
                    return CompactionResult(
                        summary="",
                        tokens_before=current_tokens + prune_result_tokens(prune_result),
                        tokens_after=current_tokens,
                        was_pruned=True,
                        prune_result=prune_result,
                    )
        
        # Step 2: Compact if enabled and still over limit
        if self.settings.auto_compact:
            return await self.compact(
                session_id=session_id,
                agent_run_id=agent_run.id,
                model=model,
                abort_signal=abort_signal,
                prune_result=prune_result,
            )
        
        return None
    
    async def compact(
        self,
        session_id: str,
        agent_run_id: str,
        model: str,
        abort_signal: Any = None,
        prune_result: PruningResult | None = None,
    ) -> CompactionResult:
        """Run compaction agent to generate summary.
        
        Args:
            session_id: The session to compact
            agent_run_id: The agent run to compact
            model: Model to use for compaction
            abort_signal: Optional abort signal
            prune_result: Previous pruning result if any
            
        Returns:
            CompactionResult with summary
        """
        logger.info(f"Running compaction for session {session_id}")
        
        # Get messages that can be compacted
        messages = await self.store.get_compactable_messages(agent_run_id)
        
        if not messages:
            logger.warning(f"No messages to compact for run {agent_run_id}")
            return CompactionResult(
                summary="",
                tokens_before=0,
                tokens_after=0,
            )
        
        # Calculate tokens before
        tokens_before = sum(m.token_count for m in messages)
        
        # Create compaction agent
        agent = CompactionAgent()
        
        # Generate summary
        summary = await agent.summarize(
            messages=messages,
            provider=self.provider,
            abort_signal=abort_signal,
        )
        
        # Calculate tokens after (summary only)
        tokens_after = int(len(summary) * 0.25)  # Approximate tokens
        
        # Store the summary as a special compaction message
        compaction_message = Message(
            agent_run_id=agent_run_id,
            role=MessageRole.SYSTEM,
            content="[Compacted conversation summary]",
            token_count=tokens_after,
            is_compaction=True,
            summary=summary,
        )
        await self.store.add_message(compaction_message)
        
        # Publish event
        await self.bus.publish(
            Event.COMPACTION_COMPLETE,
            session_id=session_id,
            agent_role="compaction",
            data={
                "tokens_before": tokens_before,
                "tokens_after": tokens_after,
                "summary_length": len(summary),
                "was_pruned": prune_result is not None,
            },
        )
        
        logger.info(
            f"Compaction complete: {tokens_before} -> {tokens_after} tokens "
            f"for session {session_id}"
        )
        
        return CompactionResult(
            summary=summary,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            was_pruned=prune_result is not None,
            prune_result=prune_result,
        )


def prune_result_tokens(prune_result: PruningResult) -> int:
    """Get total tokens from prune result."""
    return prune_result.tokens_pruned if prune_result else 0
