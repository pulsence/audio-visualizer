"""Cross-package integration smoke tests.

Tests the shared event protocol works end-to-end with the logging bridge
and verifies both packages can coexist.
"""

import logging

from audio_visualizer.events import (
    AppEvent,
    AppEventEmitter,
    EventLevel,
    EventType,
    LoggingBridge,
)


class TestCrossPackageEventSmoke:
    def test_both_packages_share_emitter(self):
        """Both srt and caption can share a single AppEventEmitter."""
        emitter = AppEventEmitter()
        received = []
        emitter.subscribe(lambda e: received.append(e))

        # Simulate srt event
        emitter.emit(AppEvent(
            event_type=EventType.STAGE,
            message="Transcribing",
            data={"stage_number": 2, "total_stages": 4},
        ))

        # Simulate caption event
        emitter.emit(AppEvent(
            event_type=EventType.RENDER_START,
            message="Starting render",
        ))

        assert len(received) == 2
        assert received[0].event_type == EventType.STAGE
        assert received[1].event_type == EventType.RENDER_START

    def test_logging_bridge_captures_both_packages(self, caplog):
        """LoggingBridge captures events from both packages in one log."""
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.integration.bridge")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.integration.bridge"):
            emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message="SRT: model loaded",
                level=EventLevel.INFO,
            ))
            emitter.emit(AppEvent(
                event_type=EventType.LOG,
                message="Caption: render complete",
                level=EventLevel.INFO,
            ))

        assert "SRT: model loaded" in caplog.text
        assert "Caption: render complete" in caplog.text

    def test_progress_events_filtered_in_bridge(self, caplog):
        """Progress events from both packages are downgraded to DEBUG."""
        emitter = AppEventEmitter()
        logger = logging.getLogger("test.integration.progress")
        LoggingBridge(logger, emitter)

        with caplog.at_level(logging.DEBUG, logger="test.integration.progress"):
            emitter.emit(AppEvent(
                event_type=EventType.PROGRESS,
                message="SRT progress",
                data={"percent": 50.0},
            ))
            emitter.emit(AppEvent(
                event_type=EventType.RENDER_PROGRESS,
                message="Caption progress",
                data={"frame": 100},
            ))

        assert len(caplog.records) == 2
        assert all(r.levelno == logging.DEBUG for r in caplog.records)


class TestBothPackagesCoexist:
    def test_import_both_packages(self):
        """Both packages can be imported in the same process."""
        import audio_visualizer.srt
        import audio_visualizer.caption
        assert hasattr(audio_visualizer.srt, "__all__")
        assert hasattr(audio_visualizer.caption, "__all__")

    def test_event_types_shared(self):
        """Both packages use the same EventType enum."""
        from audio_visualizer.events import EventType
        # SRT types
        assert EventType.LOG is not None
        assert EventType.PROGRESS is not None
        assert EventType.STAGE is not None
        assert EventType.JOB_START is not None
        assert EventType.MODEL_LOAD is not None
        # Caption types
        assert EventType.RENDER_START is not None
        assert EventType.RENDER_PROGRESS is not None
        assert EventType.RENDER_COMPLETE is not None
