"""Assets tab — session asset browser and external asset intake."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio_visualizer.ui.workspaceContext import WorkspaceContext
from audio_visualizer.ui.tabs.baseTab import BaseTab

logger = logging.getLogger(__name__)

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
        self._imported_sources: list[str] = []
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

        btn_row = QHBoxLayout()

        self._remove_from_session_btn = QPushButton("Remove from Session")
        self._remove_from_session_btn.clicked.connect(self._on_remove_from_session)
        btn_row.addWidget(self._remove_from_session_btn)

        self._delete_from_disk_btn = QPushButton("Delete from Disk")
        self._delete_from_disk_btn.clicked.connect(self._on_delete_from_disk)
        btn_row.addWidget(self._delete_from_disk_btn)

        self._load_project_folder_btn = QPushButton("Load from Project Folder")
        self._load_project_folder_btn.clicked.connect(self._on_load_from_project_folder)
        btn_row.addWidget(self._load_project_folder_btn)

        btn_row.addStretch()
        assets_layout.addLayout(btn_row)

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

        self._imported_roots_label = QLabel("No external files or folders loaded.")
        import_layout.addWidget(self._imported_roots_label)

        import_group.setLayout(import_layout)
        layout.addWidget(import_group)

        self.setLayout(layout)

    # -- Session context --

    def set_workspace_context(self, context: WorkspaceContext) -> None:
        super().set_workspace_context(context)
        context.asset_added.connect(lambda _: self._refresh_table())
        context.asset_updated.connect(lambda _: self._refresh_table())
        context.asset_removed.connect(lambda _: self._refresh_table())
        self._refresh_table()

    def _refresh_table(self) -> None:
        ctx = self.workspace_context
        if ctx is None:
            return
        assets = ctx.list_assets()
        self._asset_table.setRowCount(len(assets))
        for row, asset in enumerate(assets):
            name_item = QTableWidgetItem(asset.display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, asset.id)
            self._asset_table.setItem(row, 0, name_item)
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

    # -- Selection helpers --

    def _selected_asset_ids(self) -> list[str]:
        """Return asset IDs for all selected rows."""
        ids = []
        for row in sorted(set(idx.row() for idx in self._asset_table.selectedIndexes())):
            item = self._asset_table.item(row, 0)
            if item is not None:
                asset_id = item.data(Qt.ItemDataRole.UserRole)
                if asset_id:
                    ids.append(asset_id)
        return ids

    # -- Asset action handlers --

    def _on_remove_from_session(self) -> None:
        """Remove selected assets from the session (keep files on disk)."""
        asset_ids = self._selected_asset_ids()
        if not asset_ids:
            return
        ctx = self.workspace_context
        if ctx is None:
            return
        answer = QMessageBox.question(
            self,
            "Remove from Session",
            f"Remove {len(asset_ids)} asset(s) from the session?\n"
            "Files will remain on disk.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for asset_id in asset_ids:
            ctx.remove_asset(asset_id)

    def _on_delete_from_disk(self) -> None:
        """Delete selected assets from disk and remove from session."""
        asset_ids = self._selected_asset_ids()
        if not asset_ids:
            return
        ctx = self.workspace_context
        if ctx is None:
            return
        answer = QMessageBox.warning(
            self,
            "Delete from Disk",
            f"Permanently delete {len(asset_ids)} asset(s) from disk?\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for asset_id in asset_ids:
            asset = ctx.get_asset(asset_id)
            if asset is not None:
                try:
                    asset.path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not delete file: %s", asset.path)
            ctx.remove_asset(asset_id)

    def _on_load_from_project_folder(self) -> None:
        """Load/reload assets from the configured project folder."""
        ctx = self.workspace_context
        if ctx is None:
            return
        folder = ctx.project_folder
        if not folder:
            QMessageBox.information(
                self,
                "No Project Folder",
                "No project folder is configured.\n"
                "Set one in Settings > Project Folder.",
            )
            return
        ctx.import_asset_folder(folder, source_tab="assets")

    # -- Import handlers --

    def _on_import_files(self) -> None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory

        start_dir = resolve_browse_directory(workspace_context=self.workspace_context)
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Files", start_dir,
            "Media Files (*.mp3 *.wav *.flac *.mp4 *.mkv *.png *.jpg *.srt *.ass);;All Files (*)"
        )
        if not files:
            return
        for file_path in files:
            imported = self._import_single_file(Path(file_path))
            if imported is not None and str(imported.path) not in self._imported_sources:
                self._imported_sources.append(str(imported.path))
        self._update_imported_label()

    def _on_import_folder(self) -> None:
        from audio_visualizer.ui.sessionFilePicker import resolve_browse_directory

        start_dir = resolve_browse_directory(workspace_context=self.workspace_context)
        folder = QFileDialog.getExistingDirectory(self, "Import Folder", start_dir)
        if not folder:
            return
        folder_path = Path(folder)
        if str(folder_path) not in self._imported_sources:
            self._imported_sources.append(str(folder_path))
        self._scan_and_import_folder(folder_path)
        self._update_imported_label()

    def _import_single_file(self, path: Path):
        ctx = self.workspace_context
        if ctx is None:
            return None
        asset = ctx.import_asset_file(path, source_tab="assets")
        if asset is None:
            logger.debug("Skipped unsupported asset import: %s", path)
        return asset

    def _scan_and_import_folder(self, folder: Path) -> None:
        ctx = self.workspace_context
        if ctx is None:
            return
        ctx.import_asset_folder(folder, source_tab="assets")

    def _update_imported_label(self) -> None:
        if self._imported_sources:
            text = "Imported sources: " + ", ".join(self._imported_sources)
        else:
            text = "No external files or folders loaded."
        self._imported_roots_label.setText(text)

    # -- BaseTab contract --

    def validate_settings(self) -> tuple[bool, str]:
        return True, ""

    def collect_settings(self) -> dict[str, Any]:
        return {
            "imported_sources": self._imported_sources,
        }

    def apply_settings(self, data: dict[str, Any]) -> None:
        self._imported_sources = data.get(
            "imported_sources",
            data.get("imported_roots", []),
        )
        self._update_imported_label()
