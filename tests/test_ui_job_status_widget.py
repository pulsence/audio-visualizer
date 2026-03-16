"""Tests for the persistent JobStatusWidget."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.jobStatusWidget import (
    JobStatusWidget,
    _STATE_IDLE,
)


class TestJobStatusWidget:
    def test_progress_bar_returns_for_next_job_after_completion(self):
        widget = JobStatusWidget()

        widget.show_job("render", "audio_visualizer", "Rendering video")
        widget.show_completed("Done", output_path="/tmp/out.mp4")
        assert widget._progress_bar.isHidden() is True

        widget.reset()
        widget.show_job("render", "caption_animate", "Rendering captions")

        assert widget._progress_bar.isHidden() is False
        assert widget._progress_bar.value() == 0

    def test_failed_state_is_compact_and_dismissible(self):
        widget = JobStatusWidget()

        widget.show_job("render", "audio_visualizer", "Rendering video")
        widget.show_failed("boom")

        assert widget._progress_bar.isHidden() is True
        assert widget._cancel_button.text() == "Dismiss"


class TestTerminalStateButtonText:
    """Button text should be 'Finished' for completed, 'Dismiss' for failed/canceled."""

    def test_completed_shows_finished(self):
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_completed("Done")
        assert widget._cancel_button.text() == "Finished"

    def test_failed_shows_dismiss(self):
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_failed("error")
        assert widget._cancel_button.text() == "Dismiss"

    def test_canceled_shows_dismiss(self):
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_canceled("user canceled")
        assert widget._cancel_button.text() == "Dismiss"


class TestAutoResetTimer:
    """Auto-reset timer fires after 5 seconds in terminal states."""

    def test_timer_is_widget_owned_qtimer(self):
        widget = JobStatusWidget()
        assert isinstance(widget._auto_reset_timer, QTimer)
        assert widget._auto_reset_timer.isSingleShot() is True
        assert widget._auto_reset_timer.interval() == 5000

    def test_timer_starts_on_completed(self):
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_completed("Done")
        assert widget._auto_reset_timer.isActive() is True

    def test_timer_starts_on_failed(self):
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_failed("error")
        assert widget._auto_reset_timer.isActive() is True

    def test_timer_starts_on_canceled(self):
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_canceled("canceled")
        assert widget._auto_reset_timer.isActive() is True

    def test_timer_timeout_resets_widget(self):
        """Simulating the timer timeout triggers reset."""
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_completed("Done", output_path="/tmp/out.mp4")
        assert widget.isVisible() is True

        # Directly emit the timeout signal to simulate timer firing.
        widget._auto_reset_timer.timeout.emit()

        assert widget._state == _STATE_IDLE
        assert widget.isVisible() is False

    def test_manual_reset_stops_timer(self):
        """Clicking Finished/Dismiss calls reset() which stops the timer."""
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_completed("Done")
        assert widget._auto_reset_timer.isActive() is True

        widget.reset()
        assert widget._auto_reset_timer.isActive() is False

    def test_new_job_stops_pending_timer(self):
        """Starting a new job while in terminal state clears the old timer."""
        widget = JobStatusWidget()
        widget.show_job("render", "tab", "label")
        widget.show_completed("Done")
        assert widget._auto_reset_timer.isActive() is True

        widget.show_job("transcribe", "tab", "new label")
        assert widget._auto_reset_timer.isActive() is False
        assert widget._state != _STATE_IDLE  # still active, not reset
