"""Tests for OpenAgentApp wiring."""

from open_agent.config import Settings
from open_agent.core.app import OpenAgentApp


async def test_app_initialization():
    """Test that the app wires everything together correctly."""
    settings = Settings()
    app = OpenAgentApp(settings)
    await app.initialize()

    # All 6 agents registered
    assert len(app.agent_registry.all_agents()) == 6
    roles = set(app.agent_registry.roles())
    assert roles == {"orchestrator", "coder", "explorer", "planner", "debugger", "reviewer"}

    # All 10 tools registered (6 native + 4 delegation)
    all_tools = app.tool_registry.all_tools()
    tool_names = {t.name for t in all_tools}
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "delegate_task" in tool_names
    assert "report_result" in tool_names
    assert len(all_tools) == 10

    # Tool filtering works per agent
    coder = app.agent_registry.get_required("coder")
    allowed, denied = coder.get_tool_filter()
    coder_tools = app.tool_registry.get_tools_for_agent(allowed=allowed, denied=denied)
    coder_tool_names = {t.name for t in coder_tools}
    assert "read_file" in coder_tool_names
    assert "write_file" in coder_tool_names
    assert "delegate_task" not in coder_tool_names

    orchestrator = app.agent_registry.get_required("orchestrator")
    allowed, denied = orchestrator.get_tool_filter()
    orch_tools = app.tool_registry.get_tools_for_agent(allowed=allowed, denied=denied)
    orch_tool_names = {t.name for t in orch_tools}
    assert "delegate_task" in orch_tool_names
    assert "read_file" not in orch_tool_names

    await app.shutdown()


async def test_app_provider_registry():
    """Test that provider registry creates providers per model."""
    settings = Settings()
    app = OpenAgentApp(settings)
    await app.initialize()

    # Different agents can have different models
    coder_config = settings.agents["coder"]
    explorer_config = settings.agents["explorer"]
    assert coder_config.model == "gpt-4o"
    assert explorer_config.model == "gpt-4o-mini"

    await app.shutdown()


async def test_persistence_integration():
    """Test that persistence store is properly wired."""
    settings = Settings()
    app = OpenAgentApp(settings)
    await app.initialize()

    # Store should be initialized
    assert app.store._db is not None

    # Can list sessions (should be empty)
    sessions = await app.store.list_sessions()
    assert sessions == []

    await app.shutdown()
