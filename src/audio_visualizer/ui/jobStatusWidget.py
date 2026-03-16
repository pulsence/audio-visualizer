"""Persistent job-status widget visible across tab switches.

Displays active job information including job type, source tab, progress,
status text, and a cancel button.  Intended to sit in a status-bar area
at the bottom of the main window so the user can monitor long-running
operations regardless of which tab is currently selected.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QWidget,
)

logger = logging.getLogger(__name__)

# Job lifecycle states used internally to decide which controls are
# enabled and what styling to apply.
_STATE_IDLE = "idle"
_STATE_ACTIVE = "active"
_STATE_COMPLETED = "completed"
_STATE_FAILED = "failed"
_STATE_CANCELED = "canceled"


class JobStatusWidget(QWidget):
    """Compact horizontal widget that reports the status of a running job.

    Signals
    -------
    cancel_requested()
        Emitted when the user clicks the cancel button.
    """

    cancel_requested = Signal()
    preview_requested = Signal(str)
    open_output_requested = Signal(str)
    open_folder_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._state: str = _STATE_IDLE
        self._output_path: str | None = None

        # -- widgets ---------------------------------------------------

        self._job_info_label = QLabel()
        self._job_info_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._status_label = QLabel()
        self._status_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setFixedWidth(70)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)

        self._preview_button = QPushButton("Preview")
        self._preview_button.clicked.connect(self._emit_preview_requested)
        self._preview_button.hide()

        self._open_output_button = QPushButton("Open Output")
        self._open_output_button.clicked.connect(self._emit_open_output_requested)
        self._open_output_button.hide()

        self._open_folder_button = QPushButton("Open Folder")
        self._open_folder_button.clicked.connect(self._emit_open_folder_requested)
        self._open_folder_button.hide()

        # -- layout ----------------------------------------------------

        layout = QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self._job_info_label)
        layout.addWidget(self._progress_bar, stretch=1)
        layout.addWidget(self._status_label)
        layout.addWidget(self._preview_button)
        layout.addWidget(self._open_output_button)
        layout.addWidget(self._open_folder_button)
        layout.addWidget(self._cancel_button)
        self.setLayout(layout)

        # Start hidden — nothing to show until a job begins.
        self.setVisible(False)

    # -- public API ----------------------------------------------------

    def show_job(self, job_type: str, owner_tab: str, label: str) -> None:
        """Display job information and enter the active state.

        Parameters
        ----------
        job_type : str
            Short identifier for the kind of job (e.g. ``"render"``,
            ``"transcribe"``).
        owner_tab : str
            Human-readable name of the tab that owns the job.
        label : str
            Descriptive label for the current operation.
        """
        self._state = _STATE_ACTIVE
        self._output_path = None
        self._job_info_label.setText(f"[{owner_tab}] {job_type}: {label}")
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._status_label.setText("")
        self._set_action_buttons_visible(False)
        self._cancel_button.setEnabled(True)
        self._cancel_button.setText("Cancel")
        self.setVisible(True)
        logger.debug(
            "Job shown: type=%s, tab=%s, label=%s", job_type, owner_tab, label
        )

    def update_progress(self, percent: float, message: str) -> None:
        """Update the progress bar and status message.

        Parameters
        ----------
        percent : float
            Progress percentage (0-100).  Pass ``-1`` to switch the
            progress bar to indeterminate (pulsing) mode.
        message : str
            Short status text displayed beside the progress bar.
        """
        if percent < 0:
            # Indeterminate — pulsing bar.
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(int(min(percent, 100)))
        self._status_label.setText(message)

    def update_status(self, message: str) -> None:
        """Update the status text without changing progress.

        Parameters
        ----------
        message : str
            Short status text.
        """
        self._status_label.setText(message)

    def show_completed(self, message: str, output_path: str | None = None) -> None:
        """Transition to a compact dismissible completed state.

        The progress bar is hidden, completion actions are shown inline,
        and a dismiss button allows the user to clear the status area
        without leaving the progress row pinned at 100%.

        Parameters
        ----------
        message : str
            Completion message to display.
        output_path : str | None
            Path to the output file, used for action buttons.
        """
        self._state = _STATE_COMPLETED
        self._output_path = output_path
        self._progress_bar.setVisible(False)
        self._job_info_label.setText("")
        self._status_label.setText(message)
        self._set_action_buttons_visible(bool(output_path))
        self._cancel_button.setText("Dismiss")
        self._cancel_button.setEnabled(True)
        self._rewire_cancel_button(self.reset)
        logger.debug("Job completed: %s", message)

    def show_failed(self, error: str) -> None:
        """Transition to the failed state.

        Parameters
        ----------
        error : str
            Error description to display.
        """
        self._state = _STATE_FAILED
        self._output_path = None
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        self._status_label.setText(f"Error: {error}")
        self._set_action_buttons_visible(False)
        self._cancel_button.setText("Dismiss")
        self._cancel_button.setEnabled(True)
        self._rewire_cancel_button(self.reset)
        logger.warning("Job failed: %s", error)

    def show_canceled(self, message: str) -> None:
        """Transition to the canceled state.

        Parameters
        ----------
        message : str
            Cancellation message to display.
        """
        self._state = _STATE_CANCELED
        self._output_path = None
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        self._status_label.setText(message)
        self._set_action_buttons_visible(False)
        self._cancel_button.setText("Dismiss")
        self._cancel_button.setEnabled(True)
        self._rewire_cancel_button(self.reset)
        logger.debug("Job canceled: %s", message)

    def reset(self) -> None:
        """Hide all job information and return to the idle state."""
        # Ensure the button is wired back to the cancel handler for the
        # next job, regardless of which handler is currently connected.
        try:
            self._cancel_button.clicked.disconnect()
        except RuntimeError:
            pass
        self._cancel_button.clicked.connect(self._on_cancel_clicked)

        self._state = _STATE_IDLE
        self._output_path = None
        self._job_info_label.setText("")
        self._progress_bar.setVisible(True)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._status_label.setText("")
        self._set_action_buttons_visible(False)
        self._cancel_button.setEnabled(True)
        self._cancel_button.setText("Cancel")
        self.setVisible(False)
        logger.debug("Job status widget reset to idle.")

    def is_job_active(self) -> bool:
        """Return ``True`` if a job is currently being tracked."""
        return self._state == _STATE_ACTIVE

    # -- internal slots ------------------------------------------------

    def _on_cancel_clicked(self) -> None:
        """Handle the cancel button click during an active job."""
        if self._state != _STATE_ACTIVE:
            return
        self._cancel_button.setEnabled(False)
        self._status_label.setText("Canceling\u2026")
        logger.debug("Cancel requested by user.")
        self.cancel_requested.emit()

    def _emit_preview_requested(self) -> None:
        if self._output_path:
            self.preview_requested.emit(self._output_path)

    def _emit_open_output_requested(self) -> None:
        if self._output_path:
            self.open_output_requested.emit(self._output_path)

    def _emit_open_folder_requested(self) -> None:
        if self._output_path:
            self.open_folder_requested.emit(self._output_path)

    def _set_action_buttons_visible(self, visible: bool) -> None:
        self._preview_button.setVisible(visible)
        self._open_output_button.setVisible(visible)
        self._open_folder_button.setVisible(visible)

    def _rewire_cancel_button(self, callback) -> None:
        try:
            self._cancel_button.clicked.disconnect()
        except RuntimeError:
            pass
        self._cancel_button.clicked.connect(callback)
