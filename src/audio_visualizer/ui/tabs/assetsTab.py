"""Assets tab — session asset browser and external asset intake.

Shows all registered session assets in a live table and allows
importing external files/folders.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio_visualizer.ui.sessionContext import SessionAsset, SessionContext
from audio_visualizer.ui.tabs.baseTab import BaseTab

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma",
    ".mp4", ".mkv", ".webm", ".avi", ".mov", ".mxf",
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff",
    ".srt", ".ass", ".vtt",
    ".json",
}

_EXTENSION_CATEGORIES = {
    ".mp3": "audio", ".wav": "audio", ".flac": "audio",
    ".ogg": "audio", ".m4a": "audio", ".aac": "audio", ".wma": "audio",
    ".mp4": "video", ".mkv": "video", ".webm": "video",
    ".avi": "video", ".mov": "video", ".mxf": "video",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".bmp": "image", ".tiff": "image",
    ".srt": "subtitle", ".ass": "subtitle", ".vtt": "subtitle",
    ".json": "json_bundle",
}

_ASSET_COLUMNS = [
    "Name", "Category", "Role", "Source", "Path",
    "Duration", "Size", "Alpha", "Audio",
]


class AssetsTab(BaseTab):
    """Session asset browser and external import tab."""

    @property
    def tab_id(self) -> str:
        return "assets"

    @property
    def tab_title(self) -> str:
        return "Assets"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._imported_roots: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)

        # Session assets table
        assets_group = QGroupBox("Session Assets")
        assets_layout = QVBoxLayout()

        self._asset_table = QTableWidget()
        self._asset_table.setColumnCount(len(_ASSET_COLUMNS))
        self._asset_table.setHorizontalHeaderLabels(_ASSET_COLUMNS)
        self._asset_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._asset_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._asset_table.setAlternatingRowColors(True)
        self._asset_table.horizontalHeader().setStretchLastSection(True)
        self._asset_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        assets_layout.addWidget(self._asset_table)

        assets_group.setLayout(assets_layout)
        layout.addWidget(assets_group, stretch=2)

        # Import section
        import_group = QGroupBox("Import External Assets")
        import_layout = QVBoxLayout()

        btn_row = QHBoxLayout()
        self._import_files_btn = QPushButton("Import Files...")
        self._import_files_btn.clicked.connect(self._on_import_files)
        btn_row.addWidget(self._import_files_btn)

        self._import_folder_btn = QPushButton("Import Folder...")
        self._import_folder_btn.clicked.connect(self._on_import_folder)
        btn_row.addWidget(self._import_folder_btn)
        btn_row.addStretch()
        import_layout.addLayout(btn_row)

        self._imported_roots_label = QLabel("No external folders loaded.")
        import_layout.addWidget(self._imported_roots_label)

        import_group.setLayout(import_layout)
        layout.addWidget(import_group)

        self.setLayout(layout)

    # -- Session context --

    def set_session_context(self, context: SessionContext) -> None:
        super().set_session_context(context)
        context.asset_added.connect(lambda _: self._refresh_table())
        context.asset_updated.connect(lambda _: self._refresh_table())
        context.asset_removed.connect(lambda _: self._refresh_table())
        self._refresh_table()

    def _refresh_table(self) -> None:
        ctx = self.session_context
        if ctx is None:
            return
        assets = ctx.list_assets()
        self._asset_table.setRowCount(len(assets))
        for row, asset in enumerate(assets):
            self._asset_table.setItem(row, 0, QTableWidgetItem(asset.display_name))
            self._asset_table.setItem(row, 1, QTableWidgetItem(asset.category))
            self._asset_table.setItem(row, 2, QTableWidgetItem(asset.role or ""))
            self._asset_table.setItem(row, 3, QTableWidgetItem(asset.source_tab or ""))
            self._asset_table.setItem(row, 4, QTableWidgetItem(str(asset.path)))
            dur = f"{asset.duration_ms}ms" if asset.duration_ms else ""
            self._asset_table.setItem(row, 5, QTableWidgetItem(dur))
            size = f"{asset.width}x{asset.height}" if asset.width and asset.height else ""
            self._asset_table.setItem(row, 6, QTableWidgetItem(size))
            self._asset_table.setItem(row, 7, QTableWidgetItem(
                "Yes" if asset.has_alpha else ("No" if asset.has_alpha is False else "")
            ))
            self._asset_table.setItem(row, 8, QTableWidgetItem(
                "Yes" if asset.has_audio else ("No" if asset.has_audio is False else "")
            ))

    # -- Import handlers --

    def _on_import_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Files", "",
            "Media Files (*.mp3 *.wav *.flac *.mp4 *.mkv *.png *.jpg *.srt *.ass);;All Files (*)"
        )
        if not files:
            return
        for file_path in files:
            self._import_single_file(Path(file_path))

    def _on_import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Import Folder")
        if not folder:
            return
        folder_path = Path(folder)
        if str(folder_path) not in self._imported_roots:
            self._imported_roots.append(str(folder_path))
        self._scan_and_import_folder(folder_path)
        self._update_imported_label()

    def _import_single_file(self, path: Path) -> None:
        ctx = self.session_context
        if ctx is None:
            return
        # Deduplicate by path
        if ctx.find_asset_by_path(path) is not None:
            return
        category = _EXTENSION_CATEGORIES.get(path.suffix.lower(), "config")
        asset = SessionAsset(
            id=str(uuid.uuid4()),
            display_name=path.name,
            path=path,
            category=category,
            source_tab="assets",
        )
        try:
            ctx.register_asset(asset)
        except ValueError:
            logger.debug("Asset already registered: %s", path)

    def _scan_and_import_folder(self, folder: Path) -> None:
        for item in sorted(folder.rglob("*")):
            if item.is_file() and item.suffix.lower() in _SUPPORTED_EXTENSIONS:
                self._import_single_file(item)

    def _update_imported_label(self) -> None:
        if self._imported_roots:
            text = "Imported from: " + ", ".join(self._imported_roots)
        else:
            text = "No external folders loaded."
        self._imported_roots_label.setText(text)

    # -- BaseTab contract --

    def validate_settings(self) -> tuple[bool, str]:
        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "imported_roots": self._imported_roots,
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        self._imported_roots = data.get("imported_roots", [])
        self._update_imported_label()
