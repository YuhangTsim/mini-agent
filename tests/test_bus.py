"""Tests for the EventBus and Event types."""

from open_agent.bus import Event, EventBus, EventPayload


async def test_subscribe_and_publish():
    bus = EventBus()
    received: list[EventPayload] = []

    async def handler(payload: EventPayload):
        received.append(payload)

    bus.subscribe(Event.TOKEN_STREAM, handler)
    await bus.publish(
        Event.TOKEN_STREAM, session_id="s1", agent_role="coder", data={"token": "hello"}
    )

    assert len(received) == 1
    assert received[0].event == Event.TOKEN_STREAM
    assert received[0].data["token"] == "hello"
    assert received[0].session_id == "s1"
    assert received[0].agent_role == "coder"


async def test_wildcard_handler():
    bus = EventBus()
    received: list[EventPayload] = []

    async def handler(payload: EventPayload):
        received.append(payload)

    bus.subscribe(None, handler)
    await bus.publish(Event.SESSION_START, session_id="s1", agent_role="orchestrator")
    await bus.publish(Event.TOKEN_STREAM, session_id="s1", agent_role="coder")

    assert len(received) == 2
    assert received[0].event == Event.SESSION_START
    assert received[1].event == Event.TOKEN_STREAM


async def test_unsubscribe():
    bus = EventBus()
    received: list[EventPayload] = []

    async def handler(payload: EventPayload):
        received.append(payload)

    unsub = bus.subscribe(Event.ERROR, handler)
    await bus.publish(Event.ERROR, session_id="s1", agent_role="coder")
    assert len(received) == 1

    unsub()
    await bus.publish(Event.ERROR, session_id="s1", agent_role="coder")
    assert len(received) == 1  # no new event


async def test_stream_queue():
    bus = EventBus()
    queue = bus.stream(Event.TOOL_CALL_START)

    await bus.publish(
        Event.TOOL_CALL_START, session_id="s1", agent_role="coder", data={"tool": "read_file"}
    )

    payload = queue.get_nowait()
    assert payload.event == Event.TOOL_CALL_START
    assert payload.data["tool"] == "read_file"


async def test_wildcard_stream():
    bus = EventBus()
    queue = bus.stream(None)  # wildcard

    await bus.publish(Event.AGENT_START, session_id="s1", agent_role="coder")
    await bus.publish(Event.AGENT_END, session_id="s1", agent_role="coder")

    assert queue.qsize() == 2
    p1 = queue.get_nowait()
    p2 = queue.get_nowait()
    assert p1.event == Event.AGENT_START
    assert p2.event == Event.AGENT_END


async def test_unstream():
    bus = EventBus()
    queue = bus.stream(Event.ERROR)
    bus.unstream(queue, Event.ERROR)

    await bus.publish(Event.ERROR, session_id="s1", agent_role="coder")
    assert queue.empty()


async def test_handler_error_does_not_break_other_handlers():
    bus = EventBus()
    received: list[str] = []

    async def bad_handler(payload: EventPayload):
        raise ValueError("boom")

    async def good_handler(payload: EventPayload):
        received.append("ok")

    bus.subscribe(Event.ERROR, bad_handler)
    bus.subscribe(Event.ERROR, good_handler)

    await bus.publish(Event.ERROR, session_id="s1", agent_role="coder")
    assert received == ["ok"]


async def test_multiple_handlers_same_event():
    bus = EventBus()
    results: list[int] = []

    for i in range(3):
        val = i

        async def handler(payload: EventPayload, v=val):
            results.append(v)

        bus.subscribe(Event.SESSION_START, handler)

    await bus.publish(Event.SESSION_START, session_id="s1", agent_role="orchestrator")
    assert results == [0, 1, 2]


async def test_parent_session_id():
    bus = EventBus()
    received: list[EventPayload] = []

    async def handler(payload: EventPayload):
        received.append(payload)

    bus.subscribe(Event.DELEGATION_START, handler)
    await bus.publish(
        Event.DELEGATION_START,
        session_id="child-1",
        agent_role="coder",
        parent_session_id="parent-1",
    )

    assert received[0].parent_session_id == "parent-1"


async def test_clear():
    bus = EventBus()
    received: list[EventPayload] = []

    async def handler(payload: EventPayload):
        received.append(payload)

    bus.subscribe(Event.ERROR, handler)
    queue = bus.stream(Event.ERROR)

    bus.clear()

    await bus.publish(Event.ERROR, session_id="s1", agent_role="coder")
    assert len(received) == 0
    assert queue.empty()
