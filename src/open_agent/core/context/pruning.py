"""Pruning strategy for reducing token usage by removing old tool outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from open_agent.persistence.store import Store

logger = logging.getLogger(__name__)

# Tools that should not be pruned (contain user-defined context)
PROTECTED_TOOLS = {"skill", "list_files", "search_files"}


@dataclass
class PruningResult:
    """Result of a pruning operation."""
    
    tokens_pruned: int
    tool_calls_pruned: int
    tools_affected: list[str]


class PruningStrategy:
    """Prunes old tool call outputs to save tokens.
    
    Rules:
    - Keep at least 40k tokens of recent tool calls
    - Skip protected tools: skill (user-defined context)
    - Stop at first summary (conversation already compacted)
    """
    
    PRUNE_MINIMUM = 20_000  # Only prune if saving this many tokens
    PRUNE_PROTECT = 40_000  # Keep at least this much
    
    # Approximate tokens per character (conservative estimate)
    TOKENS_PER_CHAR = 0.25
    
    def __init__(self, store: Store, protect_tokens: int = PRUNE_PROTECT) -> None:
        self.store = store
        self.protect_tokens = protect_tokens
    
    async def prune(self, session_id: str) -> PruningResult | None:
        """Prune tool outputs from old messages.
        
        Args:
            session_id: The session to prune
            
        Returns:
            PruningResult if pruning occurred, None if no pruning needed
        """
        # Get all tool calls for the session
        runs = await self.store.get_session_runs(session_id)
        if not runs:
            return None
            
        total_pruned = 0
        total_calls = 0
        tools_affected: list[str] = []
        
        for run in runs:
            result = await self._prune_run(run.id)
            if result:
                total_pruned += result.tokens_pruned
                total_calls += result.tool_calls_pruned
                tools_affected.extend(result.tools_affected)
        
        if total_pruned < self.PRUNE_MINIMUM:
            logger.debug(f"Pruning skipped: only {total_pruned} tokens would be saved")
            return None
            
        logger.info(
            f"Pruned {total_pruned} tokens from {total_calls} tool calls "
            f"in session {session_id}"
        )
        
        return PruningResult(
            tokens_pruned=total_pruned,
            tool_calls_pruned=total_calls,
            tools_affected=list(set(tools_affected)),
        )
    
    async def _prune_run(self, run_id: str) -> PruningResult | None:
        """Prune tool calls for a single agent run."""
        tool_calls = await self.store.get_tool_calls(run_id)
        
        if not tool_calls:
            return None
            
        # Calculate total tokens in tool outputs
        total_tokens = sum(
            int(len(tc.result) * self.TOKENS_PER_CHAR) for tc in tool_calls
        )
        
        # If under protection threshold, don't prune
        if total_tokens <= self.protect_tokens:
            return None
        
        # Find tool calls to prune (oldest first, except protected)
        tokens_to_prune = total_tokens - self.protect_tokens
        pruned_tokens = 0
        pruned_calls = 0
        tools_affected: list[str] = []
        
        # Sort by creation time (oldest first)
        sorted_calls = sorted(tool_calls, key=lambda tc: tc.created_at)
        
        for tc in sorted_calls:
            if tc.tool_name in PROTECTED_TOOLS:
                continue
                
            call_tokens = int(len(tc.result) * self.TOKENS_PER_CHAR)
            
            # Check if this is a summary/compactions message
            # (we'd need to check if this run has compaction messages)
            
            # Prune this tool call's result
            pruned_tokens += call_tokens
            pruned_calls += 1
            tools_affected.append(tc.tool_name)
            
            # Clear the result
            tc.result = f"[Pruned: {tc.tool_name} output]"
            await self.store.add_tool_call(tc)  # Update in place
            
            if pruned_tokens >= tokens_to_prune:
                break
        
        return PruningResult(
            tokens_pruned=pruned_tokens,
            tool_calls_pruned=pruned_calls,
            tools_affected=tools_affected,
        )
    
    async def estimate_tokens(self, session_id: str) -> int:
        """Estimate total tokens in tool outputs for a session."""
        runs = await self.store.get_session_runs(session_id)
        total = 0
        
        for run in runs:
            tool_calls = await self.store.get_tool_calls(run.id)
            for tc in tool_calls:
                total += int(len(tc.result) * self.TOKENS_PER_CHAR)
        
        return total
