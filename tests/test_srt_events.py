"""Tests for the shared AppEvent protocol as used by the SRT package.

The old Local SRT event classes (LogEvent, ProgressEvent, EventEmitter) have
been replaced by the unified AppEvent / AppEventEmitter / EventType /
EventLevel protocol in audio_visualizer.events.  These tests verify that the
shared protocol covers the same behaviour the original SRT-specific tests
required.
"""
from audio_visualizer.events import AppEvent, AppEventEmitter, EventLevel, EventType


def test_event_emitter_subscribe_emit():
    """AppEventEmitter delivers an event with message and level."""
    emitter = AppEventEmitter()
    received = []

    def handler(event):
        received.append(event)

    emitter.subscribe(handler)
    emitter.emit(AppEvent(event_type=EventType.LOG, message="hello", level=EventLevel.INFO))

    assert len(received) == 1
    assert isinstance(received[0], AppEvent)
    assert received[0].message == "hello"
    assert received[0].event_type == EventType.LOG
    assert received[0].level == EventLevel.INFO


def test_event_emitter_multiple_subscribers():
    """Multiple subscribers each receive the same event instance."""
    emitter = AppEventEmitter()
    a = []
    b = []

    emitter.subscribe(a.append)
    emitter.subscribe(b.append)

    event = AppEvent(
        event_type=EventType.PROGRESS,
        message="12.5% done",
        data={"percent": 12.5, "segment_count": 3, "media_time": 4.2, "elapsed": 1.0, "eta": 2.0},
    )
    emitter.emit(event)

    assert a[0] is event
    assert b[0] is event


def test_log_event_via_app_event():
    """A LOG-type AppEvent carries message and level like the old LogEvent."""
    event = AppEvent(event_type=EventType.LOG, message="something happened", level=EventLevel.WARNING)
    assert event.message == "something happened"
    assert event.level == EventLevel.WARNING


def test_progress_event_via_app_event():
    """A PROGRESS-type AppEvent carries data like the old ProgressEvent."""
    event = AppEvent(
        event_type=EventType.PROGRESS,
        message="transcribing",
        data={"percent": 50.0, "segment_count": 10, "media_time": 30.0, "elapsed": 5.0, "eta": 5.0},
    )
    assert event.event_type == EventType.PROGRESS
    assert event.data["percent"] == 50.0
    assert event.data["segment_count"] == 10
