"""Tests for the shared event protocol and logging bridge."""

import logging

from audio_visualizer.events import (
    AppEvent,
    AppEventEmitter,
    EventLevel,
    EventType,
    LoggingBridge,
)


class TestEventLevel:
    def test_levels_exist(self):
        assert EventLevel.DEBUG == "DEBUG"
        assert EventLevel.INFO == "INFO"
        assert EventLevel.WARNING == "WARNING"
        assert EventLevel.ERROR == "ERROR"

    def test_level_is_string(self):
        assert isinstance(EventLevel.INFO, str)


class TestEventType:
    def test_all_types_exist(self):
        expected = {
            "LOG", "PROGRESS", "STAGE", "JOB_START", "JOB_COMPLETE",
            "RENDER_START", "RENDER_PROGRESS", "RENDER_COMPLETE", "MODEL_LOAD",
        }
        actual = {e.value for e in EventType}
        assert actual == expected


class TestAppEvent:
    def test_defaults(self):
        event = AppEvent(event_type=EventType.LOG)
        assert event.event_type == EventType.LOG
        assert event.message == ""
        assert event.level == EventLevel.INFO
        assert event.timestamp > 0
        assert event.data is None

    def test_custom_fields(self):
        event = AppEvent(
            event_type=EventType.PROGRESS,
            message="50% done",
            level=EventLevel.DEBUG,
            data={"percent": 50.0},
        )
        assert event.message == "50% done"
        assert event.level == EventLevel.DEBUG
        assert event.data["percent"] == 50.0


class TestAppEventEmitter:
    def test_subscribe_and_emit(self):
        emitter = AppEventEmitter()
        received = []
        emitter.subscribe(lambda e: received.append(e))

        event = AppEvent(event_type=EventType.LOG, message="hello")
        emitter.emit(event)

        assert len(received) == 1
        assert received[0].message == "hello"

    def test_multiple_subscribers(self):
        emitter = AppEventEmitter()
        a, b = [], []
        emitter.subscribe(lambda e: a.append(e))
        emitter.subscribe(lambda e: b.append(e))

        emitter.emit(AppEvent(event_type=EventType.LOG))
        assert len(a) == 1
        assert len(b) == 1

    def test_unsubscribe(self):
        emitter = AppEventEmitter()
        received = []
        handler = lambda e: received.append(e)
        emitter.subscribe(handler)
        emitter.unsubscribe(handler)

        emitter.emit(AppEvent(event_type=EventType.LOG))
        assert len(received) == 0

    def test_unsubscribe_nonexistent(self):
        emitter = AppEventEmitter()
        emitter.unsubscribe(lambda e: None)  # Should not raise

    def test_disable_enable(self):
        emitter = AppEventEmitter()
        received = []
        emitter.subscribe(lambda e: received.append(e))

        assert emitter.enabled is True
        emitter.disable()
        assert emitter.enabled is False
        emitter.emit(AppEvent(event_type=EventType.LOG))
        assert len(received) == 0

        emitter.enable()
        assert emitter.enabled is True
        emitter.emit(AppEvent(event_type=EventType.LOG))
        assert len(received) == 1

    def test_emit_safe_during_subscriber_modification(self):
        emitter = AppEventEmitter()
        received = []

        def handler(e):
            received.append(e)
            emitter.subscribe(lambda e2: received.append(e2))

        emitter.subscribe(handler)
        emitter.emit(AppEvent(event_type=EventType.LOG))
        assert len(received) == 1


class TestLoggingBridge:
    def test_forwards_log_event(self, caplog):
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.bridge")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.bridge"):
            emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message="test message",
                level=EventLevel.INFO,
            ))

        assert "test message" in caplog.text

    def test_progress_downgraded_to_debug(self, caplog):
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.bridge.progress")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.bridge.progress"):
            emitter.emit(AppEvent(
                event_type=EventType.PROGRESS,
                message="50%",
                level=EventLevel.INFO,
            ))

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG

    def test_render_progress_downgraded_to_debug(self, caplog):
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.bridge.render_progress")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.bridge.render_progress"):
            emitter.emit(AppEvent(
                event_type=EventType.RENDER_PROGRESS,
                message="frame 100",
                level=EventLevel.INFO,
            ))

        assert caplog.records[0].levelno == logging.DEBUG

    def test_error_level_preserved(self, caplog):
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.bridge.error")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.bridge.error"):
            emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message="something broke",
                level=EventLevel.ERROR,
            ))

        assert caplog.records[0].levelno == logging.ERROR

    def test_data_included_in_message(self, caplog):
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.bridge.data")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.bridge.data"):
            emitter.emit(AppEvent(
                event_type=EventType.STAGE,
                message="transcribing",
                data={"stage_number": 2, "total_stages": 5},
            ))

        assert "stage_number=2" in caplog.text

    def test_detach(self, caplog):
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.bridge.detach")
        bridge = LoggingBridge(logger, emitter)

        bridge.detach()

        with caplog.at_level(logging.DEBUG, logger="test.bridge.detach"):
            emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message="should not appear",
            ))

        assert "should not appear" not in caplog.text
