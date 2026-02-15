"""Tests for delegation validation and agent registry."""

from open_agent.agents import AgentRegistry
from open_agent.agents.orchestrator import OrchestratorAgent
from open_agent.agents.designer import DesignerAgent
from open_agent.agents.fixer import FixerAgent
from open_agent.agents.explorer import ExplorerAgent


def test_orchestrator_can_delegate_to_agents():
    agent = OrchestratorAgent()
    assert agent.can_delegate("explorer")
    assert agent.can_delegate("librarian")
    assert agent.can_delegate("oracle")
    assert agent.can_delegate("designer")
    assert agent.can_delegate("fixer")
    assert not agent.can_delegate("unknown_agent")


def test_designer_is_leaf():
    agent = DesignerAgent()
    assert agent.is_leaf
    assert not agent.can_delegate("explorer")


def test_fixer_is_leaf():
    agent = FixerAgent()
    assert agent.is_leaf


def test_explorer_is_leaf():
    agent = ExplorerAgent()
    assert agent.is_leaf


def test_agent_registry():
    registry = AgentRegistry()
    orch = OrchestratorAgent()
    fixer = FixerAgent()

    registry.register(orch)
    registry.register(fixer)

    assert registry.get("orchestrator") is orch
    assert registry.get("fixer") is fixer
    assert registry.get("unknown") is None
    assert set(registry.roles()) == {"orchestrator", "fixer"}


def test_agent_registry_get_required():
    registry = AgentRegistry()
    registry.register(FixerAgent())

    agent = registry.get_required("fixer")
    assert agent.role == "fixer"

    try:
        registry.get_required("unknown")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_tool_filter():
    fixer = FixerAgent()
    allowed, denied = fixer.get_tool_filter()
    assert "read_file" in allowed
    assert "write_file" in allowed
    assert "delegate_task" not in allowed
    assert denied == []
