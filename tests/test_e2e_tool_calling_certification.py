"""Live cross-model tool-calling certification tests."""

from __future__ import annotations

import os

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
                if not any(tc.tool_name == "read_file" and tc.status == "success" for tc in tool_calls):
                    raise ModelBehaviorFailure("Model did not complete a successful read_file call.")
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
                    raise ModelBehaviorFailure("Model did not encounter or surface the expected tool error.")
                if "success" not in statuses:
                    raise ModelBehaviorFailure("Model did not recover with a later successful tool call.")
                if expected not in result:
                    raise ModelBehaviorFailure("Recovered response did not include the expected file contents.")
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
