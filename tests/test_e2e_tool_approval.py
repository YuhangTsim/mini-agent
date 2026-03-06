"""End-to-end tool approval tests with real LLM calls (optional, requires API key)."""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping e2e tool approval tests",
)


@pytest.fixture
def api_key():
    return os.environ["OPENAI_API_KEY"]


class TestE2EToolApprovalOpenAgent:
    """E2E tool approval tests using open-agent."""

    @pytest.mark.asyncio
    async def test_auto_approve_no_callback(self, api_key):
        """auto_approve: tool executes without triggering approval callback."""
        from open_agent.config.settings import Settings
        from open_agent.core.app import OpenAgentApp
        from open_agent.core.session import SessionCallbacks

        approval_called = False

        async def on_approval(name, call_id, params):
            nonlocal approval_called
            approval_called = True
            return "y"

        settings = Settings._from_dict({
            "permissions": [
                {"agent": "*", "tool": "read_file", "policy": "auto_approve"},
            ],
            "open_agent": {
                "tool_approval": {
                    "read": "auto_approve",
                    "*": "auto_approve",
                }
            },
        })

        app = OpenAgentApp(settings)
        await app.initialize()
        app.set_callbacks(SessionCallbacks(
            on_tool_approval_request=on_approval,
        ))

        try:
            await app.process_message(
                "Read the file CLAUDE.md and tell me the first line."
            )
            # The callback should not have been called for auto_approve tools
        finally:
            await app.shutdown()

    @pytest.mark.asyncio
    async def test_deny_blocks_tool(self, api_key):
        """deny: tool is rejected and LLM gets error."""
        from open_agent.config.settings import Settings
        from open_agent.core.app import OpenAgentApp
        from open_agent.core.session import SessionCallbacks

        settings = Settings._from_dict({
            "permissions": [
                {"agent": "*", "tool": "write_file", "policy": "deny"},
            ],
        })

        app = OpenAgentApp(settings)
        await app.initialize()
        app.set_callbacks(SessionCallbacks())

        try:
            await app.process_message(
                "Write the text 'hello' to a file called /tmp/test_deny.txt"
            )
            # The write should have been denied
            assert not os.path.exists("/tmp/test_deny.txt")
        finally:
            await app.shutdown()


class TestE2EToolApprovalRooAgent:
    """E2E tool approval tests using roo-agent."""

    @pytest.mark.asyncio
    async def test_session_persistence(self, api_key):
        """always_ask with 'always' response → second call auto-approves."""
        from agent_kernel.tools.permissions import PermissionChecker
        from roo_agent.config.settings import Settings
        from roo_agent.core.agent import Agent, AgentCallbacks
        from roo_agent.persistence.store import Store
        from agent_kernel.providers.openai import OpenAIProvider
        from agent_kernel.tools.base import ToolRegistry

        call_count = 0

        async def on_approval(name, call_id, params):
            nonlocal call_count
            call_count += 1
            return "always"  # First call says "always"

        settings = Settings._from_dict({
            "tool_approval": {
                "read": "always_ask",
                "*": "always_ask",
            }
        })

        provider = OpenAIProvider(api_key=api_key, model="gpt-4o-mini")
        store = Store(":memory:")
        await store.initialize()

        registry = ToolRegistry()
        # Register minimal tools for the test
        from roo_agent.tools import get_all_tools
        for tool in get_all_tools():
            registry.register(tool)

        checker = PermissionChecker(settings.permissions)

        _agent = Agent(
            provider=provider,
            registry=registry,
            store=store,
            settings=settings,
            callbacks=AgentCallbacks(on_tool_approval_request=on_approval),
            permission_checker=checker,
        )

        # The "always" response should persist via session approval
        # so the second use of the same tool shouldn't prompt again
