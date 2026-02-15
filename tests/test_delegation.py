"""Tests for delegation validation and agent registry."""

from open_agent.agents import AgentRegistry
from open_agent.agents.orchestrator import OrchestratorAgent
from open_agent.agents.coder import CoderAgent
from open_agent.agents.explorer import ExplorerAgent


def test_orchestrator_can_delegate_to_coder():
    agent = OrchestratorAgent()
    assert agent.can_delegate("coder")
    assert agent.can_delegate("explorer")
    assert agent.can_delegate("planner")
    assert not agent.can_delegate("unknown_agent")


def test_coder_is_leaf():
    agent = CoderAgent()
    assert agent.is_leaf
    assert not agent.can_delegate("explorer")


def test_explorer_is_leaf():
    agent = ExplorerAgent()
    assert agent.is_leaf


def test_agent_registry():
    registry = AgentRegistry()
    orch = OrchestratorAgent()
    coder = CoderAgent()

    registry.register(orch)
    registry.register(coder)

    assert registry.get("orchestrator") is orch
    assert registry.get("coder") is coder
    assert registry.get("unknown") is None
    assert set(registry.roles()) == {"orchestrator", "coder"}


def test_agent_registry_get_required():
    registry = AgentRegistry()
    registry.register(CoderAgent())

    agent = registry.get_required("coder")
    assert agent.role == "coder"

    try:
        registry.get_required("unknown")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_tool_filter():
    coder = CoderAgent()
    allowed, denied = coder.get_tool_filter()
    assert "read_file" in allowed
    assert "write_file" in allowed
    assert "delegate_task" not in allowed
    assert denied == []
