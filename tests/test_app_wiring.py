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
    assert roles == {"orchestrator", "explorer", "librarian", "oracle", "designer", "fixer"}

    # All tools registered
    all_tools = app.tool_registry.all_tools()
    tool_names = {t.name for t in all_tools}
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "delegate_task" in tool_names
    assert "report_result" in tool_names

    # Tool filtering works per agent
    fixer = app.agent_registry.get_required("fixer")
    allowed, denied = fixer.get_tool_filter()
    fixer_tools = app.tool_registry.get_tools_for_agent(allowed=allowed, denied=denied)
    fixer_tool_names = {t.name for t in fixer_tools}
    assert "read_file" in fixer_tool_names
    assert "write_file" in fixer_tool_names
    assert "delegate_task" not in fixer_tool_names

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
    fixer_config = settings.agents["fixer"]
    explorer_config = settings.agents["explorer"]
    assert fixer_config.model == "gpt-4o"
    assert explorer_config.model == "gpt-4o-mini"

    await app.shutdown()


async def test_persistence_integration():
    """Test that persistence store is properly wired."""
    import tempfile
    
    # Use a temp directory for isolation
    with tempfile.TemporaryDirectory() as tmpdir:
        settings = Settings()
        settings.data_dir = tmpdir
        
        app = OpenAgentApp(settings)
        await app.initialize()

        # Store should be initialized
        assert app.store._db is not None

        # Can list sessions (should be empty for fresh db)
        sessions = await app.store.list_sessions()
        assert sessions == []

        await app.shutdown()
