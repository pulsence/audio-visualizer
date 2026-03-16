"""Tests for the persistent JobStatusWidget."""

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from audio_visualizer.ui.jobStatusWidget import JobStatusWidget


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
