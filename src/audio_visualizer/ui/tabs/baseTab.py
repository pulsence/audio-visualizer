"""Base tab abstraction for the multi-tab Audio Visualizer shell.

Defines the shared contract that every tab must implement: identification,
settings serialization, validation, workspace context injection, and optional
undo/redo support.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QUndoStack
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from audio_visualizer.ui.workspaceContext import WorkspaceContext

logger = logging.getLogger(__name__)


class BaseTab(QWidget):
    """Abstract base class for all application tabs.

    Subclasses must override the abstract properties and methods to
    participate in the tab lifecycle managed by the main window shell.
    """

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------

    settings_changed = Signal()
    """Emitted whenever a tab-local setting is modified by the user."""

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._workspace_context: WorkspaceContext | None = None
        self._undo_stack: QUndoStack | None = None

    # ------------------------------------------------------------------
    # Abstract identity properties
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def tab_id(self) -> str:
        """Stable key used for settings storage and routing.

        Must be unique across all tabs and must not change between
        application versions so that persisted settings remain valid.
        """

    @property
    @abstractmethod
    def tab_title(self) -> str:
        """Human-readable display label shown on the tab bar."""

    # ------------------------------------------------------------------
    # Abstract settings contract
    # ------------------------------------------------------------------

    @abstractmethod
    def validate_settings(self) -> tuple[bool, str]:
        """Validate the current state of this tab's controls.

        Returns:
            A ``(valid, message)`` tuple.  When *valid* is ``True`` the
            message may be empty.  When ``False`` the message should
            describe the problem so it can be shown to the user.
        """

    @abstractmethod
    def collect_settings(self) -> dict[str, Any]:
        """Serialize the tab's current configuration to a plain dict.

        The returned dict must contain only JSON-serializable values
        (no live Qt widgets or other non-picklable objects).
        """

    @abstractmethod
    def apply_settings(self, data: dict[str, Any]) -> None:
        """Restore the tab's controls from a previously collected dict.

        Args:
            data: A dict produced by a prior :meth:`collect_settings` call.
        """

    # ------------------------------------------------------------------
    # Workspace context
    # ------------------------------------------------------------------

    @property
    def workspace_context(self) -> WorkspaceContext | None:
        """Return the currently injected workspace context, or ``None``."""
        return self._workspace_context

    def set_workspace_context(self, context: WorkspaceContext) -> None:
        """Inject the shared workspace context into this tab.

        Called by the main window shell after workspace creation or change.
        Subclasses may override to react to context changes but should
        call ``super().set_workspace_context(context)`` first.

        Args:
            context: The new workspace context to use.
        """
        self._workspace_context = context
        logger.debug("Workspace context set for tab '%s'", self.tab_id)

    # ------------------------------------------------------------------
    # Global busy state
    # ------------------------------------------------------------------

    def set_global_busy(self, is_busy: bool, owner_tab_id: str | None = None) -> None:
        """Disable or re-enable start/run controls during long operations.

        Called by the shell when any tab begins or finishes a blocking
        job (e.g. rendering, transcription).  Tabs should disable their
        own "Start" buttons while *is_busy* is ``True`` and the owner is
        a different tab.

        The default implementation is a no-op.  Subclasses that own
        start/run controls should override this.

        Args:
            is_busy:      ``True`` when a job is running, ``False`` when idle.
            owner_tab_id: The :attr:`tab_id` of the tab that owns the job,
                          or ``None`` if the busy state is global.
        """

    # ------------------------------------------------------------------
    # Output asset registration
    # ------------------------------------------------------------------

    def register_output_asset(self, asset: Any) -> None:
        """Register a single output asset in the workspace context.

        Convenience helper that delegates to the workspace context.  Tabs
        call this after a job completes to make its outputs available to
        downstream tabs.

        Args:
            asset: A :class:`SessionAsset` instance to register.
        """
        if self._workspace_context is None:
            logger.warning(
                "Cannot register asset for tab '%s': no workspace context",
                self.tab_id,
            )
            return
        self._workspace_context.register_asset(asset)
        logger.info(
            "Tab '%s' registered asset '%s'",
            self.tab_id,
            getattr(asset, "id", "?"),
        )

    # ------------------------------------------------------------------
    # Optional undo / redo support
    # ------------------------------------------------------------------

    @property
    def has_undo_support(self) -> bool:
        """Return ``True`` if an undo stack has been initialised."""
        return self._undo_stack is not None

    def _init_undo_stack(self, limit: int = 100) -> None:
        """Create an undo stack for this tab.

        Should be called during subclass ``__init__`` if the tab needs
        undo/redo capability.

        Args:
            limit: Maximum number of undo levels to retain.
        """
        self._undo_stack = QUndoStack(self)
        self._undo_stack.setUndoLimit(limit)
        logger.debug(
            "Undo stack initialised for tab '%s' (limit=%d)",
            self.tab_id,
            limit,
        )

    def _push_command(self, command: Any) -> None:
        """Push a :class:`QUndoCommand` onto the undo stack.

        Args:
            command: A ``QUndoCommand`` instance representing a reversible
                     edit.

        Raises:
            RuntimeError: If the undo stack has not been initialised.
        """
        if self._undo_stack is None:
            raise RuntimeError(
                f"Undo stack not initialised for tab '{self.tab_id}'. "
                "Call _init_undo_stack() first."
            )
        self._undo_stack.push(command)

    def _clear_undo_stack(self) -> None:
        """Clear all commands from the undo stack.

        Raises:
            RuntimeError: If the undo stack has not been initialised.
        """
        if self._undo_stack is None:
            raise RuntimeError(
                f"Undo stack not initialised for tab '{self.tab_id}'. "
                "Call _init_undo_stack() first."
            )
        self._undo_stack.clear()
        logger.debug("Undo stack cleared for tab '%s'", self.tab_id)

    def undo_action(self) -> QAction | None:
        """Return a ``QAction`` wired to undo, or ``None`` if unsupported.

        The returned action automatically enables/disables itself and
        updates its text based on the undo stack state.
        """
        if self._undo_stack is None:
            return None
        return self._undo_stack.createUndoAction(self)

    def redo_action(self) -> QAction | None:
        """Return a ``QAction`` wired to redo, or ``None`` if unsupported.

        The returned action automatically enables/disables itself and
        updates its text based on the undo stack state.
        """
        if self._undo_stack is None:
            return None
        return self._undo_stack.createRedoAction(self)
