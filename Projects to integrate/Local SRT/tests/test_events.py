"""Tests for the events module."""
from local_srt.events import EventEmitter, LogEvent, ProgressEvent, EventLevel


def test_event_emitter_subscribe_emit():
    emitter = EventEmitter()
    received = []

    def handler(event):
        received.append(event)

    emitter.subscribe(handler)
    emitter.emit(LogEvent(message="hello", level=EventLevel.INFO))

    assert len(received) == 1
    assert isinstance(received[0], LogEvent)
    assert received[0].message == "hello"


def test_event_emitter_multiple_subscribers():
    emitter = EventEmitter()
    a = []
    b = []

    emitter.subscribe(a.append)
    emitter.subscribe(b.append)

    event = ProgressEvent(percent=12.5, segment_count=3, media_time=4.2, elapsed=1.0, eta=2.0)
    emitter.emit(event)

    assert a[0] is event
    assert b[0] is event
