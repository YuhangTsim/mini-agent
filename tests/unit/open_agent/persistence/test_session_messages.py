"""Tests for the open-agent session transcript persistence layer."""

from __future__ import annotations

from mini_agent.persistence.models import MessageRole
from open_agent.persistence.models import Session, SessionMessage


async def test_session_message_round_trip(open_store):
    session = Session(id="sess-1", title="Transcript")
    await open_store.create_session(session)

    message = SessionMessage(
        session_id=session.id,
        sequence=1,
        source_run_id="run-1",
        agent_role="orchestrator",
        role=MessageRole.ASSISTANT,
        content="Visible reply",
        tool_calls=[
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": "echo", "arguments": '{"message":"hi"}'},
            }
        ],
    )

    await open_store.add_session_message(message)

    messages = await open_store.get_session_messages(session.id)
    assert len(messages) == 1
    restored = messages[0]
    assert restored.session_id == session.id
    assert restored.sequence == 1
    assert restored.agent_role == "orchestrator"
    assert restored.content == "Visible reply"
    assert restored.tool_calls == message.tool_calls


async def test_session_messages_are_returned_in_sequence_order(open_store):
    session = Session(id="sess-seq", title="Ordering")
    await open_store.create_session(session)

    await open_store.add_session_message(
        SessionMessage(
            session_id=session.id,
            sequence=2,
            source_run_id="run-2",
            agent_role="orchestrator",
            role=MessageRole.ASSISTANT,
            content="second",
        )
    )
    await open_store.add_session_message(
        SessionMessage(
            session_id=session.id,
            sequence=1,
            source_run_id="run-1",
            agent_role="orchestrator",
            role=MessageRole.USER,
            content="first",
        )
    )

    messages = await open_store.get_session_messages(session.id)
    assert [message.sequence for message in messages] == [1, 2]
    assert [message.content for message in messages] == ["first", "second"]


async def test_session_messages_are_isolated_by_session(open_store):
    await open_store.create_session(Session(id="sess-a", title="A"))
    await open_store.create_session(Session(id="sess-b", title="B"))

    await open_store.add_session_message(
        SessionMessage(
            session_id="sess-a",
            sequence=1,
            source_run_id="run-a",
            agent_role="orchestrator",
            role=MessageRole.USER,
            content="only a",
        )
    )
    await open_store.add_session_message(
        SessionMessage(
            session_id="sess-b",
            sequence=1,
            source_run_id="run-b",
            agent_role="orchestrator",
            role=MessageRole.USER,
            content="only b",
        )
    )

    messages_a = await open_store.get_session_messages("sess-a")
    messages_b = await open_store.get_session_messages("sess-b")

    assert [message.content for message in messages_a] == ["only a"]
    assert [message.content for message in messages_b] == ["only b"]


async def test_next_session_sequence_increments(open_store):
    session = Session(id="sess-next", title="Next")
    await open_store.create_session(session)

    assert await open_store.get_next_session_sequence(session.id) == 1

    await open_store.add_session_message(
        SessionMessage(
            session_id=session.id,
            sequence=1,
            source_run_id="run-1",
            agent_role="orchestrator",
            role=MessageRole.USER,
            content="hello",
        )
    )

    assert await open_store.get_next_session_sequence(session.id) == 2
