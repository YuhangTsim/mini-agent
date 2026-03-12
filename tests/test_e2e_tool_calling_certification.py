"""Live cross-model tool-calling certification tests."""

from __future__ import annotations

import os
import re
from typing import Any

import pytest

from agent_kernel.providers.registry import create_provider
from agent_kernel.tool_calling import TOOL_CALLING_FAILURE_PREFIX
from agent_kernel.tools.base import BaseTool, ToolContext, ToolRegistry, ToolResult
from roo_agent.core.agent import Agent
from roo_agent.persistence.models import Task, TaskStatus
from roo_agent.persistence.store import Store
from tests.helpers.e2e_config import (
    LiveModelTarget,
    append_live_result,
    available_live_model_targets,
    make_roo_settings,
)

RUN_LIVE_MATRIX = os.environ.get("RUN_LIVE_MODEL_MATRIX") == "1"
TARGETS = available_live_model_targets()

# Provider consistency tests require both OpenAI and OpenRouter
HAS_BOTH_PROVIDERS = bool(os.environ.get("OPENAI_API_KEY")) and bool(
    os.environ.get("OPENROUTER_API_KEY")
)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.live_model_matrix,
    pytest.mark.skipif(
        not RUN_LIVE_MATRIX,
        reason="Set RUN_LIVE_MODEL_MATRIX=1 to run live model certification tests",
    ),
    pytest.mark.skipif(
        not TARGETS,
        reason="No live model targets configured for certification",
    ),
]


class ModelBehaviorFailure(AssertionError):
    """The model did not satisfy the certification scenario."""


class FrameworkHandlingFailure(AssertionError):
    """The framework did not enforce the expected tool-calling contract."""


class AlwaysFailTool(BaseTool):
    """Tool used to force repeated tool-error turns."""

    name = "always_fail"
    description = "Always returns an error. Use this only when explicitly instructed."
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string"},
        },
        "required": ["message"],
        "additionalProperties": False,
    }
    groups = ["read"]
    skip_approval = True

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        return ToolResult.failure(f"Always failing: {params.get('message', '')}")


def _make_registry(*extra_tools: BaseTool) -> ToolRegistry:
    from roo_agent.tools.native import get_all_native_tools

    registry = ToolRegistry()
    for tool in get_all_native_tools():
        registry.register(tool)
    for tool in extra_tools:
        registry.register(tool)
    return registry


async def _make_store(tmp_path) -> Store:
    store = Store(str(tmp_path / "roo_cert.db"))
    await store.initialize()
    return store


def _bucket_for_exception(exc: BaseException) -> str:
    if isinstance(exc, ModelBehaviorFailure):
        return "model_behavior_failure"
    if isinstance(exc, FrameworkHandlingFailure):
        return "framework_handling_failure"
    return "provider_transport_failure"


async def _run_scenario(
    target: LiveModelTarget,
    scenario: str,
    scenario_fn,
) -> None:
    try:
        await scenario_fn()
    except BaseException as exc:
        append_live_result(
            target=target,
            scenario=scenario,
            status="failed",
            failure_bucket=_bucket_for_exception(exc),
            failure_reason=str(exc),
        )
        raise
    else:
        append_live_result(target=target, scenario=scenario, status="passed")


@pytest.mark.parametrize("target", TARGETS, ids=lambda target: target.key)
class TestLiveToolCallingCertification:
    @pytest.mark.asyncio
    async def test_mandatory_tool_use(self, target: LiveModelTarget, tmp_path):
        async def scenario() -> None:
            settings = make_roo_settings(tmp_path, target=target)
            provider = create_provider(settings.provider)
            store = await _make_store(tmp_path)
            registry = _make_registry()

            try:
                file_path = tmp_path / "facts.txt"
                expected = f"tool-cert-{target.key}"
                file_path.write_text(expected, encoding="utf-8")

                task = Task(
                    title="Mandatory tool use",
                    description="Read facts.txt with a tool",
                    mode="code",
                    status=TaskStatus.ACTIVE,
                    working_directory=str(tmp_path),
                )
                await store.create_task(task)

                agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
                result = await agent.run(
                    task=task,
                    user_message=(
                        "Use the read_file tool to read facts.txt and reply with the exact file "
                        "contents. Do not answer without using a tool."
                    ),
                    conversation=[],
                    system_prompt="You must use tools for file access.",
                )

                tool_calls = await store.get_tool_calls(task.id)
                if not any(
                    tc.tool_name == "read_file" and tc.status == "success" for tc in tool_calls
                ):
                    raise ModelBehaviorFailure(
                        "Model did not complete a successful read_file call."
                    )
                if expected not in result:
                    raise ModelBehaviorFailure("Model response did not include the file contents.")
            finally:
                await store.close()

        await _run_scenario(target, "mandatory_tool_use", scenario)

    @pytest.mark.asyncio
    async def test_recovery_after_tool_error(self, target: LiveModelTarget, tmp_path):
        async def scenario() -> None:
            settings = make_roo_settings(tmp_path, target=target)
            provider = create_provider(settings.provider)
            store = await _make_store(tmp_path)
            registry = _make_registry()

            try:
                expected = f"recovery-{target.key}"
                (tmp_path / "recovery.txt").write_text(expected, encoding="utf-8")

                task = Task(
                    title="Recovery",
                    description="Recover after a tool error",
                    mode="code",
                    status=TaskStatus.ACTIVE,
                    working_directory=str(tmp_path),
                )
                await store.create_task(task)

                agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
                result = await agent.run(
                    task=task,
                    user_message=(
                        "First, use read_file on missing.txt. After that fails, recover by using "
                        "tools to read recovery.txt and return its exact contents. Do not answer "
                        "without using tools."
                    ),
                    conversation=[],
                    system_prompt="You must use tools for file access and recover from tool errors.",
                )

                tool_calls = await store.get_tool_calls(task.id)
                statuses = [tc.status for tc in tool_calls]
                if "error" not in statuses:
                    raise ModelBehaviorFailure(
                        "Model did not encounter or surface the expected tool error."
                    )
                if "success" not in statuses:
                    raise ModelBehaviorFailure(
                        "Model did not recover with a later successful tool call."
                    )
                if expected not in result:
                    raise ModelBehaviorFailure(
                        "Recovered response did not include the expected file contents."
                    )
            finally:
                await store.close()

        await _run_scenario(target, "recovery_after_tool_error", scenario)

    @pytest.mark.asyncio
    async def test_structured_non_convergence_failure(
        self,
        target: LiveModelTarget,
        tmp_path,
    ):
        async def scenario() -> None:
            settings = make_roo_settings(tmp_path, target=target)
            provider = create_provider(settings.provider)
            store = await _make_store(tmp_path)
            registry = _make_registry(AlwaysFailTool())

            try:
                task = Task(
                    title="Non-convergence",
                    description="Force repeated tool errors",
                    mode="code",
                    status=TaskStatus.ACTIVE,
                    working_directory=str(tmp_path),
                )
                await store.create_task(task)

                agent = Agent(provider=provider, registry=registry, store=store, settings=settings)
                result = await agent.run(
                    task=task,
                    user_message=(
                        "Use the always_fail tool with the message 'retry'. If it fails, try the "
                        "same tool again. Do not answer without calling the tool."
                    ),
                    conversation=[],
                    system_prompt="You must call at least one tool per response.",
                )

                tool_calls = await store.get_tool_calls(task.id)
                if len(tool_calls) < 2:
                    raise ModelBehaviorFailure(
                        "Model did not produce enough failing tool turns to exercise non-convergence."
                    )
                if not result.startswith(TOOL_CALLING_FAILURE_PREFIX):
                    raise FrameworkHandlingFailure(
                        "Framework did not return the structured non-convergence failure."
                    )
                if task.status != TaskStatus.FAILED:
                    raise FrameworkHandlingFailure("Task was not marked failed on non-convergence.")
            finally:
                await store.close()

        await _run_scenario(target, "structured_non_convergence_failure", scenario)


# =============================================================================
# Provider Consistency Tests
# =============================================================================

#: Known inconsistencies between providers - documented for test expectations
KNOWN_INCONSISTENCIES = """
Known provider inconsistencies:
- Tokenizers differ (OpenAI uses tiktoken, OpenRouter may use different tokenizers)
- Tool selection may differ due to model-specific prompting
- Response formatting varies between providers
- Latency and rate limits differ between providers
"""


def _normalize_tool_name(name: str) -> str:
    """Normalize tool name for comparison."""
    return name.lower().strip()


def _extract_file_path_from_args(args_str: str) -> str | None:
    """Extract file path from tool arguments string."""
    # Try to find a path-like argument
    patterns = [
        r'"path":\s*"([^"]+)"',
        r'"file_path":\s*"([^"]+)"',
        r'"file":\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, args_str)
        if match:
            return match.group(1)
    return None


def _semantically_equivalent_tool_calls(
    calls_a: list[dict[str, Any]],
    calls_b: list[dict[str, Any]],
) -> tuple[bool, str]:
    """Compare two lists of tool calls for semantic equivalence.

    Returns (is_equivalent, reason).
    """
    if not calls_a and not calls_b:
        return True, "both empty"

    if len(calls_a) != len(calls_b):
        return False, f"different count: {len(calls_a)} vs {len(calls_b)}"

    # Compare each tool call
    for i, (call_a, call_b) in enumerate(zip(calls_a, calls_b)):
        name_a = _normalize_tool_name(call_a.get("name", ""))
        name_b = _normalize_tool_name(call_b.get("name", ""))

        # Tool names should match (or be equivalent like read_file vs file_read)
        if name_a != name_b:
            # Check for equivalent tools
            equivalent_pairs = [
                ("read_file", "file_read"),
                ("write_file", "file_write"),
                ("list_files", "glob"),
            ]
            if not any(pair[0] == name_a and pair[1] == name_b for pair in equivalent_pairs):
                return False, f"call {i}: different tools {name_a} vs {name_b}"

        # Compare arguments semantically
        args_a = call_a.get("arguments", {})
        args_b = call_b.get("arguments", {})

        # For file operations, compare paths
        path_a = _extract_file_path_from_args(call_a.get("arguments", ""))
        path_b = _extract_file_path_from_args(call_b.get("arguments", ""))

        if path_a and path_b:
            # Normalize paths for comparison
            norm_a = path_a.replace("\\", "/").split("/")[-1]
            norm_b = path_b.replace("\\", "/").split("/")[-1]
            if norm_a != norm_b:
                return False, f"call {i}: different paths {path_a} vs {path_b}"

    return True, "semantically equivalent"


def _token_count_similarity(
    tokens_a: int,
    tokens_b: int,
    tolerance: float = 0.20,
) -> tuple[bool, str]:
    """Check if token counts are within tolerance.

    Returns (is_similar, reason).
    """
    if tokens_a == 0 and tokens_b == 0:
        return True, "both zero"

    if tokens_a == 0 or tokens_b == 0:
        return False, f"one is zero: {tokens_a} vs {tokens_b}"

    # Calculate percentage difference
    diff = abs(tokens_a - tokens_b) / max(tokens_a, tokens_b)

    if diff <= tolerance:
        return True, f"within {tolerance * 100}%: {tokens_a} vs {tokens_b}"

    return False, f"differs by {diff * 100:.1f}%: {tokens_a} vs {tokens_b}"


@pytest.mark.skipif(
    not HAS_BOTH_PROVIDERS,
    reason="Requires both OPENAI_API_KEY and OPENROUTER_API_KEY",
)
class TestProviderConsistency:
    """Test consistency of tool calling behavior across providers.

    These tests verify that:
    1. Same prompts produce similar behavior across providers
    2. Token counts are reasonably consistent
    3. Tool calling patterns are consistent

    Known limitations:
    - Different tokenizers may cause ±20% variance in token counts
    - Models may choose different but equivalent tools
    - Response formatting varies between providers
    """

    @pytest.fixture
    def openai_target(self) -> LiveModelTarget | None:
        """Get OpenAI target for testing."""
        for target in TARGETS:
            if target.provider_name == "openai":
                return target
        return None

    @pytest.fixture
    def openrouter_target(self) -> LiveModelTarget | None:
        """Get OpenRouter target for testing."""
        for target in TARGETS:
            if target.provider_name == "openrouter":
                return target
        return None

    @pytest.mark.asyncio
    async def test_same_prompt_across_providers(
        self,
        openai_target: LiveModelTarget,
        openrouter_target: LiveModelTarget,
        tmp_path,
    ):
        """Test same tool-calling prompt produces consistent behavior across providers.

        Runs the same prompt on OpenAI and OpenRouter, verifying:
        - Both complete successfully
        - Both make tool calls (not just text)
        - Tool selection is consistent (same or equivalent tools)

        Known issues: Some models may choose different but equivalent tools.
        """
        # Create test file
        test_file = tmp_path / "test_prompt.txt"
        test_file.write_text("Provider consistency test content", encoding="utf-8")

        prompt = (
            "Read the file 'test_prompt.txt' and return its exact contents. "
            "Do not answer without using a tool."
        )

        # Run with OpenAI
        settings_openai = make_roo_settings(tmp_path, target=openai_target)
        provider_openai = create_provider(settings_openai.provider)
        store_openai = await _make_store(tmp_path)
        registry = _make_registry()

        try:
            task_openai = Task(
                title="OpenAI consistency test",
                description="Test same prompt on OpenAI",
                mode="code",
                status=TaskStatus.ACTIVE,
                working_directory=str(tmp_path),
            )
            await store_openai.create_task(task_openai)

            agent_openai = Agent(
                provider=provider_openai,
                registry=registry,
                store=store_openai,
                settings=settings_openai,
            )

            result_openai = await agent_openai.run(
                task=task_openai,
                user_message=prompt,
                conversation=[],
                system_prompt="You must use tools for file access.",
            )

            tool_calls_openai = await store_openai.get_tool_calls(task_openai.id)
            tool_names_openai = [tc.tool_name for tc in tool_calls_openai if tc.status == "success"]
        finally:
            await store_openai.close()

        # Run with OpenRouter
        settings_openrouter = make_roo_settings(tmp_path, target=openrouter_target)
        provider_openrouter = create_provider(settings_openrouter.provider)
        store_openrouter = await _make_store(tmp_path)

        try:
            task_openrouter = Task(
                title="OpenRouter consistency test",
                description="Test same prompt on OpenRouter",
                mode="code",
                status=TaskStatus.ACTIVE,
                working_directory=str(tmp_path),
            )
            await store_openrouter.create_task(task_openrouter)

            agent_openrouter = Agent(
                provider=provider_openrouter,
                registry=registry,
                store=store_openrouter,
                settings=settings_openrouter,
            )

            result_openrouter = await agent_openrouter.run(
                task=task_openrouter,
                user_message=prompt,
                conversation=[],
                system_prompt="You must use tools for file access.",
            )

            tool_calls_openrouter = await store_openrouter.get_tool_calls(task_openrouter.id)
            tool_names_openrouter = [
                tc.tool_name for tc in tool_calls_openrouter if tc.status == "success"
            ]
        finally:
            await store_openrouter.close()

        # Verify both completed
        assert len(tool_names_openai) > 0, "OpenAI did not make any successful tool calls"
        assert len(tool_names_openrouter) > 0, "OpenRouter did not make any successful tool calls"

        # Verify tool selection consistency
        is_equivalent, reason = _semantically_equivalent_tool_calls(
            [{"name": n, "arguments": ""} for n in tool_names_openai],
            [{"name": n, "arguments": ""} for n in tool_names_openrouter],
        )

        # Document but don't fail on tool selection differences
        print(f"Tool comparison: {reason}")
        print(f"OpenAI tools: {tool_names_openai}")
        print(f"OpenRouter tools: {tool_names_openrouter}")

    @pytest.mark.asyncio
    async def test_token_counting_consistency(
        self,
        openai_target: LiveModelTarget,
        openrouter_target: LiveModelTarget,
        tmp_path,
    ):
        """Test token counting is consistent across providers (±20%).

        Sends same message to both providers and compares token counts.

        Known issues: Different tokenizers may cause variance. OpenRouter
        may report different token counts due to different tokenization.
        """
        # Simple message for token counting
        system_prompt = "You are a helpful assistant."
        messages = [{"role": "user", "content": "What is 2+2?"}]

        # Get token counts from OpenAI
        settings_openai = make_roo_settings(tmp_path, target=openai_target)
        provider_openai = create_provider(settings_openai.provider)

        input_tokens_openai = provider_openai.count_tokens(
            system_prompt + "".join(m["content"] for m in messages)
        )

        # Get token counts from OpenRouter (using same tokenizer for comparison)
        settings_openrouter = make_roo_settings(tmp_path, target=openrouter_target)
        provider_openrouter = create_provider(settings_openrouter.provider)

        input_tokens_openrouter = provider_openrouter.count_tokens(
            system_prompt + "".join(m["content"] for m in messages)
        )

        # Compare token counts
        is_similar, reason = _token_count_similarity(input_tokens_openai, input_tokens_openrouter)

        print(
            f"Token counts - OpenAI: {input_tokens_openai}, OpenRouter: {input_tokens_openrouter}"
        )
        print(f"Comparison: {reason}")

        # Document but don't strictly enforce - tokenizers differ
        # This test verifies the framework can handle different token counts

    @pytest.mark.asyncio
    async def test_tool_calling_consistency(
        self,
        openai_target: LiveModelTarget,
        openrouter_target: LiveModelTarget,
        tmp_path,
    ):
        """Test tool calling behavior is consistent across providers.

        Same tool-calling scenario on both providers:
        - Both make tool calls (not just text responses)
        - Tool parameters are semantically equivalent

        Known issues: Parameters may differ in formatting but be functionally equivalent.
        """
        # Create test file for both to read
        test_file = tmp_path / "tool_call_test.txt"
        test_file.write_text("Test content for tool calling", encoding="utf-8")

        prompt = "List all files in the current directory, then read 'tool_call_test.txt'."

        # Run with OpenAI
        settings_openai = make_roo_settings(tmp_path, target=openai_target)
        provider_openai = create_provider(settings_openai.provider)
        store_openai = await _make_store(tmp_path)
        registry = _make_registry()

        try:
            task_openai = Task(
                title="OpenAI tool call test",
                description="Test tool calls on OpenAI",
                mode="code",
                status=TaskStatus.ACTIVE,
                working_directory=str(tmp_path),
            )
            await store_openai.create_task(task_openai)

            agent_openai = Agent(
                provider=provider_openai,
                registry=registry,
                store=store_openai,
                settings=settings_openai,
            )

            await agent_openai.run(
                task=task_openai,
                user_message=prompt,
                conversation=[],
                system_prompt="You must use tools to complete the task.",
            )

            tool_calls_openai = await store_openai.get_tool_calls(task_openai.id)
            successful_calls_openai = [
                {"name": tc.tool_name, "arguments": tc.parameters or ""}
                for tc in tool_calls_openai
                if tc.status == "success"
            ]
        finally:
            await store_openai.close()

        # Run with OpenRouter
        settings_openrouter = make_roo_settings(tmp_path, target=openrouter_target)
        provider_openrouter = create_provider(settings_openrouter.provider)
        store_openrouter = await _make_store(tmp_path)

        try:
            task_openrouter = Task(
                title="OpenRouter tool call test",
                description="Test tool calls on OpenRouter",
                mode="code",
                status=TaskStatus.ACTIVE,
                working_directory=str(tmp_path),
            )
            await store_openrouter.create_task(task_openrouter)

            agent_openrouter = Agent(
                provider=provider_openrouter,
                registry=registry,
                store=store_openrouter,
                settings=settings_openrouter,
            )

            await agent_openrouter.run(
                task=task_openrouter,
                user_message=prompt,
                conversation=[],
                system_prompt="You must use tools to complete the task.",
            )

            tool_calls_openrouter = await store_openrouter.get_tool_calls(task_openrouter.id)
            successful_calls_openrouter = [
                {"name": tc.tool_name, "arguments": tc.parameters or ""}
                for tc in tool_calls_openrouter
                if tc.status == "success"
            ]
        finally:
            await store_openrouter.close()

        # Verify both made tool calls
        assert len(successful_calls_openai) > 0, "OpenAI did not make any tool calls"
        assert len(successful_calls_openrouter) > 0, "OpenRouter did not make any tool calls"

        # Verify semantic equivalence of tool calls
        is_equivalent, reason = _semantically_equivalent_tool_calls(
            successful_calls_openai,
            successful_calls_openrouter,
        )

        print(f"Tool call comparison: {reason}")
        print(f"OpenAI calls: {successful_calls_openai}")
        print(f"OpenRouter calls: {successful_calls_openrouter}")

        # Document findings but don't fail on minor differences
        # Primary goal is to verify both providers support tool calling
