"""Tests for persistence layer models."""

from __future__ import annotations

import json
from datetime import datetime


from mini_agent.persistence.models import MessageRole, TokenUsage, new_id, utcnow
from open_agent.persistence.models import (
    Session, SessionStatus,
    AgentRun, AgentRunStatus,
    Message,
    ToolCall,
)


class TestNewId:
    """Test ID generation."""
    
    def test_new_id_returns_string(self):
        """Test that new_id returns a string."""
        id1 = new_id()
        assert isinstance(id1, str)
        assert len(id1) > 0
    
    def test_new_id_unique(self):
        """Test that new_id generates unique IDs."""
        ids = {new_id() for _ in range(100)}
        assert len(ids) == 100


class TestUtcNow:
    """Test UTC timestamp generation."""
    
    def test_utcnow_returns_datetime(self):
        """Test that utcnow returns a datetime."""
        now = utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo is not None


class TestTokenUsage:
    """Test TokenUsage model."""
    
    def test_default_usage(self):
        """Test default token usage."""
        usage = TokenUsage()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_cost == 0.0
    
    def test_add_usage(self):
        """Test adding token usage."""
        usage1 = TokenUsage(input_tokens=10, output_tokens=5, total_cost=0.01)
        usage2 = TokenUsage(input_tokens=20, output_tokens=10, total_cost=0.02)
        
        usage1.add(usage2)
        
        assert usage1.input_tokens == 30
        assert usage1.output_tokens == 15
        assert usage1.total_cost == 0.03


class TestSession:
    """Test Session model."""
    
    def test_session_creation(self):
        """Test creating a session."""
        session = Session()
        
        assert session.id is not None
        assert session.status == SessionStatus.ACTIVE
        assert session.title == ""
        assert session.working_directory == ""
        assert isinstance(session.metadata, dict)
        assert isinstance(session.token_usage, TokenUsage)
    
    def test_session_with_values(self):
        """Test creating session with specific values."""
        now = utcnow()
        session = Session(
            id="test-id",
            status=SessionStatus.COMPLETED,
            title="Test Session",
            working_directory="/tmp/test",
            metadata={"key": "value"},
            created_at=now,
            updated_at=now,
        )
        
        assert session.id == "test-id"
        assert session.status == SessionStatus.COMPLETED
        assert session.title == "Test Session"
        assert session.working_directory == "/tmp/test"
        assert session.metadata == {"key": "value"}
    
    def test_session_to_row(self):
        """Test converting session to database row."""
        session = Session(
            id="test-id",
            title="Test",
            working_directory="/tmp",
            metadata={"key": "value"},
        )
        
        row = session.to_row()
        
        assert row["id"] == "test-id"
        assert row["status"] == "active"
        assert row["title"] == "Test"
        assert row["working_directory"] == "/tmp"
        assert json.loads(row["metadata"]) == {"key": "value"}
    
    def test_session_from_row(self):
        """Test creating session from database row."""
        now = utcnow().isoformat()
        row = {
            "id": "from-row",
            "status": "completed",
            "title": "From Row",
            "working_directory": "/tmp",
            "metadata": '{"foo": "bar"}',
            "input_tokens": 100,
            "output_tokens": 50,
            "estimated_cost": 0.01,
            "created_at": now,
            "updated_at": now,
        }
        
        session = Session.from_row(row)
        
        assert session.id == "from-row"
        assert session.status == SessionStatus.COMPLETED
        assert session.title == "From Row"
        assert session.metadata == {"foo": "bar"}
        assert session.token_usage.input_tokens == 100


class TestAgentRun:
    """Test AgentRun model."""
    
    def test_agent_run_creation(self):
        """Test creating an agent run."""
        run = AgentRun()
        
        assert run.id is not None
        assert run.status == AgentRunStatus.RUNNING
        assert run.session_id == ""
        assert run.agent_role == ""
        assert run.is_background is False
    
    def test_agent_run_with_parent(self):
        """Test creating agent run with parent."""
        run = AgentRun(
            session_id="session-1",
            parent_run_id="parent-1",
            agent_role="explorer",
            is_background=True,
        )
        
        assert run.session_id == "session-1"
        assert run.parent_run_id == "parent-1"
        assert run.agent_role == "explorer"
        assert run.is_background is True
    
    def test_agent_run_to_row(self):
        """Test converting agent run to database row."""
        run = AgentRun(
            id="run-1",
            session_id="session-1",
            agent_role="fixer",
            is_background=True,
        )
        
        row = run.to_row()
        
        assert row["id"] == "run-1"
        assert row["agent_role"] == "fixer"
        assert row["is_background"] == 1
    
    def test_agent_run_from_row(self):
        """Test creating agent run from database row."""
        now = utcnow().isoformat()
        row = {
            "id": "from-row",
            "session_id": "session-1",
            "parent_run_id": None,
            "agent_role": "explorer",
            "status": "completed",
            "description": "Test run",
            "result": "Success",
            "is_background": 0,
            "input_tokens": 10,
            "output_tokens": 5,
            "estimated_cost": 0.001,
            "created_at": now,
            "completed_at": now,
        }
        
        run = AgentRun.from_row(row)
        
        assert run.agent_role == "explorer"
        assert run.status == AgentRunStatus.COMPLETED
        assert run.description == "Test run"
        assert run.result == "Success"
        assert run.is_background is False


class TestMessage:
    """Test Message model."""
    
    def test_message_creation(self):
        """Test creating a message."""
        msg = Message()
        
        assert msg.id is not None
        assert msg.role == MessageRole.USER
        assert msg.content == ""
        assert msg.token_count == 0
    
    def test_message_from_text(self):
        """Test creating message from text."""
        msg = Message.from_text(
            agent_run_id="run-1",
            role=MessageRole.ASSISTANT,
            text="Hello",
        )
        
        assert msg.agent_run_id == "run-1"
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hello"
    
    def test_message_to_row(self):
        """Test converting message to database row."""
        msg = Message(
            id="msg-1",
            agent_run_id="run-1",
            role=MessageRole.USER,
            content="Test content",
            token_count=10,
        )
        
        row = msg.to_row()
        
        assert row["id"] == "msg-1"
        assert row["agent_run_id"] == "run-1"
        assert row["role"] == "user"
        assert row["content"] == "Test content"
        assert row["token_count"] == 10
    
    def test_message_from_row(self):
        """Test creating message from database row."""
        now = utcnow().isoformat()
        row = {
            "id": "from-row",
            "agent_run_id": "run-1",
            "role": "assistant",
            "content": "Hello",
            "token_count": 5,
            "created_at": now,
        }
        
        msg = Message.from_row(row)
        
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "Hello"


class TestToolCall:
    """Test ToolCall model."""
    
    def test_tool_call_creation(self):
        """Test creating a tool call."""
        tc = ToolCall()
        
        assert tc.id is not None
        assert tc.tool_name == ""
        assert tc.status == "success"
        assert tc.duration_ms == 0
    
    def test_tool_call_with_values(self):
        """Test creating tool call with values."""
        tc = ToolCall(
            agent_run_id="run-1",
            tool_name="read_file",
            parameters='{"path": "test.txt"}',
            result="File content",
            status="success",
            duration_ms=100,
        )
        
        assert tc.tool_name == "read_file"
        assert tc.parameters == '{"path": "test.txt"}'
        assert tc.result == "File content"
        assert tc.duration_ms == 100
    
    def test_tool_call_to_row(self):
        """Test converting tool call to database row."""
        tc = ToolCall(
            id="tc-1",
            tool_name="execute_command",
            parameters='{"command": "ls"}',
            result="file1.txt\nfile2.txt",
            status="success",
            duration_ms=50,
        )
        
        row = tc.to_row()
        
        assert row["tool_name"] == "execute_command"
        assert row["status"] == "success"
        assert row["duration_ms"] == 50
    
    def test_tool_call_from_row(self):
        """Test creating tool call from database row."""
        now = utcnow().isoformat()
        row = {
            "id": "from-row",
            "agent_run_id": "run-1",
            "message_id": "msg-1",
            "tool_name": "write_file",
            "parameters": '{"path": "test.txt", "content": "hello"}',
            "result": "ok",
            "status": "success",
            "duration_ms": 25,
            "created_at": now,
        }
        
        tc = ToolCall.from_row(row)
        
        assert tc.tool_name == "write_file"
        assert tc.status == "success"
        assert tc.duration_ms == 25
