"""Session-aware file picker dialog.

Provides a reusable dialog that lets the user choose between session
assets (filtered by category) and a traditional filesystem browse.
Any tab can use :func:`pick_session_or_file` to offer a unified
selection experience.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from audio_visualizer.ui.sessionContext import SessionContext

logger = logging.getLogger(__name__)


def resolve_browse_directory(
    current_path: str | Path | None = None,
    session_context: "SessionContext | None" = None,
    selected_asset_path: str | Path | None = None,
) -> str:
    """Resolve the best starting directory for a file dialog.

    Precedence:
    1. Parent of *current_path* if valid
    2. Parent of *selected_asset_path* if valid
    3. ``SessionContext.project_folder`` if set
    4. User home directory
    """
    for candidate in (current_path, selected_asset_path):
        if not candidate:
            continue
        path = Path(str(candidate)).expanduser()
        if path.is_dir():
            return str(path)
        if path.parent.is_dir():
            return str(path.parent)

    if session_context is not None and session_context.project_folder is not None:
        pf = session_context.project_folder
        if pf.is_dir():
            return str(pf)

    return str(Path.home())


def resolve_output_directory(
    explicit_directory: str | Path | None = None,
    session_context: "SessionContext | None" = None,
    source_path: str | Path | None = None,
) -> Path:
    """Resolve the parent directory for auto-derived output paths.

    Precedence:
    1. *explicit_directory* when the user chose one
    2. ``SessionContext.project_folder`` when configured
    3. Parent of *source_path* when available
    4. User home directory
    """
    if explicit_directory:
        directory = Path(str(explicit_directory)).expanduser()
        return directory

    if session_context is not None and session_context.project_folder is not None:
        project_folder = session_context.project_folder
        if project_folder is not None:
            return project_folder

    if source_path:
        source = Path(str(source_path)).expanduser()
        if source.is_dir():
            return source
        return source.parent

    return Path.home()


class SessionFilePickerDialog(QDialog):
    """Dialog showing session assets alongside a filesystem browse button.

    The user can select a session asset from the list or click "Browse..."
    to choose a file from disk.  The chosen source type and path are
    accessible after the dialog closes via :attr:`result_source` and
    :attr:`result_path`.
    """

    def __init__(
        self,
        parent: QWidget | None,
        session_context: SessionContext,
        category: str | None,
        title: str = "Select File",
        file_filter: str = "All Files (*)",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setMinimumHeight(300)

        self._session_context = session_context
        self._category = category
        self._file_filter = file_filter

        self.result_source: str = ""
        self.result_path: Path | None = None

        self._build_ui()
        self._populate_assets()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()

        # Session assets section
        layout.addWidget(QLabel("Session Assets:"))
        self._asset_list = QListWidget()
        self._asset_list.setAlternatingRowColors(True)
        self._asset_list.itemDoubleClicked.connect(self._on_asset_double_clicked)
        layout.addWidget(self._asset_list, stretch=1)

        # Filesystem browse section
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(QLabel("Or browse filesystem:"))
        browse_layout.addStretch()
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse)
        browse_layout.addWidget(self._browse_btn)
        layout.addLayout(browse_layout)

        # Dialog buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def _populate_assets(self) -> None:
        """Fill the list with assets from the session context."""
        assets = self._session_context.list_assets(category=self._category)
        for asset in assets:
            item = QListWidgetItem(f"{asset.display_name}  ({asset.path.name})")
            item.setData(Qt.ItemDataRole.UserRole, str(asset.path))
            item.setData(Qt.ItemDataRole.UserRole + 1, asset.id)
            self._asset_list.addItem(item)

        if not assets:
            placeholder = QListWidgetItem("(no matching session assets)")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._asset_list.addItem(placeholder)

    def _on_asset_double_clicked(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.ItemDataRole.UserRole)
        if path_str:
            self.result_source = "session"
            self.result_path = Path(path_str)
            self.accept()

    def _on_accept(self) -> None:
        """Handle OK button: use the selected session asset."""
        current = self._asset_list.currentItem()
        if current is not None:
            path_str = current.data(Qt.ItemDataRole.UserRole)
            if path_str:
                self.result_source = "session"
                self.result_path = Path(path_str)
                self.accept()
                return
        # Nothing selected — treat as cancel
        self.reject()

    def _on_browse(self) -> None:
        """Handle Browse button: open a standard file dialog."""
        selected_item = self._asset_list.currentItem()
        selected_path = None
        if selected_item is not None:
            selected_path = selected_item.data(Qt.ItemDataRole.UserRole)
        start_dir = resolve_browse_directory(
            session_context=self._session_context,
            selected_asset_path=selected_path,
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.windowTitle(),
            start_dir,
            self._file_filter,
        )
        if path:
            self.result_source = "file"
            self.result_path = Path(path)
            self.accept()


def pick_session_or_file(
    parent: QWidget | None,
    session_context: SessionContext,
    category: str | None,
    title: str = "Select File",
    file_filter: str = "All Files (*)",
) -> tuple[str, Path | None]:
    """Show a dialog with session assets and a filesystem browse option.

    Parameters
    ----------
    parent : QWidget | None
        Parent widget for the dialog.
    session_context : SessionContext
        The live session context to query for assets.
    category : str | None
        Asset category filter (e.g. ``"audio"``, ``"subtitle"``).
        Pass ``None`` to show all assets.
    title : str
        Dialog window title.
    file_filter : str
        File filter string for the filesystem browse dialog.

    Returns
    -------
    tuple[str, Path | None]
        ``(source_type, path)`` where *source_type* is ``"session"`` or
        ``"file"``.  Returns ``("", None)`` if the user canceled.
    """
    dialog = SessionFilePickerDialog(
        parent, session_context, category, title, file_filter
    )
    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted and dialog.result_path is not None:
        return dialog.result_source, dialog.result_path

    return "", None
