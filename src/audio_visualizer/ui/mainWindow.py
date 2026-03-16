'''
MIT License

Copyright (c) 2025 Timothy Eck

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

import logging
import time
from fractions import Fraction
from pathlib import Path

from audio_visualizer.app_logging import setup_logging
from audio_visualizer.app_paths import get_config_dir
from audio_visualizer import updater
from audio_visualizer.ui.sessionContext import SessionContext
from audio_visualizer.ui.navigationSidebar import NavigationSidebar
from audio_visualizer.ui.jobStatusWidget import JobStatusWidget
from audio_visualizer.ui.tabs.baseTab import BaseTab
from audio_visualizer.ui.settingsSchema import (
    create_default_schema, load_settings, migrate_settings, save_settings,
)
from audio_visualizer.ui.workflowRecipes import (
    apply_recipe,
    create_recipe_from_session,
    get_recipe_library_dir,
    load_recipe,
    save_recipe,
    validate_recipe,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Thin multi-tab shell hosting all workflow tabs.

    Owns the shared thread pools, SessionContext, navigation sidebar,
    job status widget, and menu/status behaviour.  All workflow logic
    lives inside the individual tab classes.
    """

    def __init__(self) -> None:
        _t0 = time.monotonic()
        super().__init__()
        self._log_path = setup_logging()
        self.setWindowTitle("Audio Visualizer")
        self.setGeometry(100, 100, 1600, 1000)

        # Shared state
        self.session_context = SessionContext(self)
        self.render_thread_pool = QThreadPool()
        self.render_thread_pool.setMaxThreadCount(1)
        self._background_thread_pool = QThreadPool()
        self._global_busy = False
        self._busy_owner_tab_id: str | None = None
        self._current_theme_mode = "off"

        # Tab registry
        self._tabs: list[BaseTab] = []
        self._tab_map: dict[str, BaseTab] = {}
        self._bound_undo_action: QAction | None = None
        self._bound_redo_action: QAction | None = None

        # Lazy tab registry
        self._lazy_tab_defs: dict[str, str] = {}  # tab_id -> title
        self._lazy_placeholders: dict[str, QWidget] = {}  # tab_id -> placeholder
        self._pending_tab_settings: dict[str, dict] = {}  # unapplied settings

        # Build shell layout
        self._build_shell()
        self._setup_menu()

        # Register tabs
        self._register_all_tabs()

        # Load last settings
        self._load_last_settings_if_present()

        logger.info("MainWindow startup: %.1f ms", (time.monotonic() - _t0) * 1000)

    # ------------------------------------------------------------------
    # Shell layout
    # ------------------------------------------------------------------

    def _build_shell(self) -> None:
        """Build the central QStackedWidget + NavigationSidebar + JobStatusWidget."""
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Top area: sidebar + stacked content
        content_layout = QHBoxLayout()

        self._sidebar = NavigationSidebar()
        self._sidebar.tab_selected.connect(self._on_tab_selected)
        content_layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        content_layout.addWidget(self._stack, 1)

        main_layout.addLayout(content_layout, 1)

        # Bottom area: job status
        self._job_status = JobStatusWidget()
        self._job_status.cancel_requested.connect(self._on_cancel_requested)
        self._job_status.preview_requested.connect(self._open_preview)
        self._job_status.open_output_requested.connect(self._open_output)
        self._job_status.open_folder_requested.connect(self._open_output_folder)
        main_layout.addWidget(self._job_status)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

    # ------------------------------------------------------------------
    # Tab registration
    # ------------------------------------------------------------------

    def add_tab(self, tab: BaseTab) -> None:
        """Register a tab in the shell."""
        tab.set_session_context(self.session_context)
        index = self._stack.addWidget(tab)
        self._sidebar.add_tab(tab.tab_id, tab.tab_title, index)
        self._tabs.append(tab)
        self._tab_map[tab.tab_id] = tab
        logger.info("Tab registered: %s (%s)", tab.tab_id, tab.tab_title)

    def _register_all_tabs(self) -> None:
        """Register all application tabs in order.

        Only the default tab (AudioVisualizerTab) is instantiated eagerly.
        Remaining tabs are registered as lazy placeholders and created on
        first activation.
        """
        # Eagerly instantiate AudioVisualizerTab
        from audio_visualizer.ui.tabs.audioVisualizerTab import AudioVisualizerTab
        self.add_tab(AudioVisualizerTab(self))

        # Register lazy tabs with placeholder widgets
        lazy_defs = [
            ("srt_gen", "SRT Gen"),
            ("srt_edit", "SRT Edit"),
            ("caption_animate", "Caption Animate"),
            ("render_composition", "Render Composition"),
            ("assets", "Assets"),
        ]
        for tab_id, title in lazy_defs:
            placeholder = QWidget()
            index = self._stack.addWidget(placeholder)
            self._sidebar.add_tab(tab_id, title, index)
            self._lazy_tab_defs[tab_id] = title
            self._lazy_placeholders[tab_id] = placeholder
            logger.debug("Lazy tab registered: %s (%s)", tab_id, title)

        # Default to first tab
        self._sidebar.set_active(0)
        self._stack.setCurrentIndex(0)
        self._update_undo_actions()

    # ------------------------------------------------------------------
    # Lazy tab instantiation
    # ------------------------------------------------------------------

    def _find_stack_index_for_tab_id(self, tab_id: str) -> int:
        """Return the QStackedWidget index for a tab_id, or -1 if not found.

        Searches both instantiated tabs and lazy placeholders.
        """
        for i in range(self._stack.count()):
            widget = self._stack.widget(i)
            if isinstance(widget, BaseTab) and widget.tab_id == tab_id:
                return i
            for tid, placeholder in self._lazy_placeholders.items():
                if placeholder is widget and tid == tab_id:
                    return i
        return -1

    def _instantiate_tab(self, tab_id: str) -> BaseTab | None:
        """Create a tab instance by tab_id (deferred import)."""
        if tab_id == "srt_gen":
            from audio_visualizer.ui.tabs.srtGenTab import SrtGenTab
            return SrtGenTab(self)
        elif tab_id == "srt_edit":
            from audio_visualizer.ui.tabs.srtEditTab import SrtEditTab
            return SrtEditTab(self)
        elif tab_id == "caption_animate":
            from audio_visualizer.ui.tabs.captionAnimateTab import CaptionAnimateTab
            return CaptionAnimateTab(self)
        elif tab_id == "render_composition":
            from audio_visualizer.ui.tabs.renderCompositionTab import RenderCompositionTab
            return RenderCompositionTab(self)
        elif tab_id == "assets":
            from audio_visualizer.ui.tabs.assetsTab import AssetsTab
            return AssetsTab(self)
        return None

    def _ensure_tab_instantiated(self, index: int) -> BaseTab | None:
        """If the widget at *index* is a lazy placeholder, instantiate it now.

        Returns the real tab widget (whether newly created or already
        present), or ``None`` if the index does not correspond to a tab.
        """
        widget = self._stack.widget(index)
        if isinstance(widget, BaseTab):
            return widget  # Already instantiated

        # Find which lazy tab this placeholder belongs to
        tab_id = None
        for tid, placeholder in self._lazy_placeholders.items():
            if placeholder is widget:
                tab_id = tid
                break

        if tab_id is None:
            return None

        tab = self._instantiate_tab(tab_id)
        if tab is None:
            return None

        tab.set_session_context(self.session_context)

        # Replace the placeholder widget at this index
        self._stack.removeWidget(widget)
        widget.deleteLater()
        self._stack.insertWidget(index, tab)

        self._tabs.append(tab)
        self._tab_map[tab.tab_id] = tab
        del self._lazy_placeholders[tab_id]

        # Apply pending settings if any
        pending = self._pending_tab_settings.pop(tab_id, None)
        if pending:
            tab.apply_settings(pending)

        # Apply current global busy state
        if self._global_busy:
            tab.set_global_busy(True, self._busy_owner_tab_id)

        logger.info("Lazy tab instantiated: %s", tab_id)
        return tab

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_tab_selected(self, index: int) -> None:
        """Handle sidebar navigation click."""
        self._ensure_tab_instantiated(index)
        self._stack.setCurrentIndex(index)
        self._update_undo_actions()

    def active_tab(self) -> BaseTab | None:
        """Return the currently visible tab."""
        widget = self._stack.currentWidget()
        if isinstance(widget, BaseTab):
            return widget
        return None

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        self._save_project_action = QAction("Save Project", self)
        self._save_project_action.triggered.connect(self.save_project)
        file_menu.addAction(self._save_project_action)
        self._load_project_action = QAction("Load Project", self)
        self._load_project_action.triggered.connect(self.load_project)
        file_menu.addAction(self._load_project_action)

        file_menu.addSeparator()

        self._save_recipe_action = QAction("Save Recipe...", self)
        self._save_recipe_action.triggered.connect(self.save_recipe_dialog)
        file_menu.addAction(self._save_recipe_action)

        self._apply_recipe_action = QAction("Apply Recipe...", self)
        self._apply_recipe_action.triggered.connect(self.apply_recipe_dialog)
        file_menu.addAction(self._apply_recipe_action)

        self._recipe_library_action = QAction("Recipe Library...", self)
        self._recipe_library_action.triggered.connect(self.open_recipe_library)
        file_menu.addAction(self._recipe_library_action)

        file_menu.addSeparator()
        self._settings_action = QAction("Settings...", self)
        self._settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(self._settings_action)

        # Edit menu
        edit_menu = menu_bar.addMenu("Edit")
        self._undo_action = QAction("Undo", self)
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self._trigger_active_undo)
        edit_menu.addAction(self._undo_action)
        self._redo_action = QAction("Redo", self)
        self._redo_action.setEnabled(False)
        self._redo_action.triggered.connect(self._trigger_active_redo)
        edit_menu.addAction(self._redo_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help")
        self.check_updates_action = QAction("Check for Updates", self)
        self.check_updates_action.triggered.connect(self.check_for_updates)
        help_menu.addAction(self.check_updates_action)

    def _update_undo_actions(self) -> None:
        """Rebind Edit > Undo/Redo to the active tab's stack."""
        tab = self.active_tab()
        self._disconnect_bound_undo_actions()

        if tab and tab.has_undo_support:
            self._bound_undo_action = tab.undo_action()
            self._bound_redo_action = tab.redo_action()
        else:
            self._bound_undo_action = None
            self._bound_redo_action = None

        self._connect_bound_undo_actions()
        self._sync_undo_actions()

    def _connect_bound_undo_actions(self) -> None:
        if self._bound_undo_action is not None:
            self._bound_undo_action.changed.connect(self._sync_undo_actions)
        if self._bound_redo_action is not None:
            self._bound_redo_action.changed.connect(self._sync_undo_actions)

    def _disconnect_bound_undo_actions(self) -> None:
        for action in (self._bound_undo_action, self._bound_redo_action):
            if action is None:
                continue
            try:
                action.changed.disconnect(self._sync_undo_actions)
            except RuntimeError:
                pass

    def _sync_undo_actions(self) -> None:
        undo = self._bound_undo_action
        redo = self._bound_redo_action

        if undo is not None:
            self._undo_action.setEnabled(undo.isEnabled())
            self._undo_action.setText(undo.text() or "Undo")
        else:
            self._undo_action.setEnabled(False)
            self._undo_action.setText("Undo")

        if redo is not None:
            self._redo_action.setEnabled(redo.isEnabled())
            self._redo_action.setText(redo.text() or "Redo")
        else:
            self._redo_action.setEnabled(False)
            self._redo_action.setText("Redo")

    def _trigger_active_undo(self) -> None:
        if self._bound_undo_action is not None and self._bound_undo_action.isEnabled():
            self._bound_undo_action.trigger()

    def _trigger_active_redo(self) -> None:
        if self._bound_redo_action is not None and self._bound_redo_action.isEnabled():
            self._bound_redo_action.trigger()

    # ------------------------------------------------------------------
    # Recipe actions
    # ------------------------------------------------------------------

    def save_recipe_dialog(self) -> None:
        """Create a recipe from current state and save to library or user path."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(
            self, "Save Recipe", "Recipe name:"
        )
        if not ok or not name.strip():
            return

        recipe = create_recipe_from_session(
            self._tabs, self.session_context, name.strip()
        )

        valid, msg = validate_recipe(recipe)
        if not valid:
            QMessageBox.warning(self, "Invalid Recipe", msg)
            return

        dialog = QFileDialog(self)
        dialog.setWindowTitle("Save Recipe")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("Recipe Files (*.avrecipe.json)")
        dialog.setDefaultSuffix("avrecipe.json")
        dialog.setDirectory(str(get_recipe_library_dir()))
        if dialog.exec():
            path = Path(dialog.selectedFiles()[0])
            if not save_recipe(recipe, path):
                QMessageBox.critical(
                    self, "Save Failed",
                    "Unable to save the recipe file.",
                )

    def apply_recipe_dialog(self) -> None:
        """Browse for a recipe file and apply it."""
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Apply Recipe")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("Recipe Files (*.avrecipe.json);;JSON Files (*.json)")
        dialog.setDirectory(str(get_recipe_library_dir()))
        if dialog.exec():
            path = Path(dialog.selectedFiles()[0])
            recipe = load_recipe(path)
            if recipe is None:
                QMessageBox.critical(
                    self, "Load Failed",
                    "Unable to load the recipe file.",
                )
                return
            apply_recipe(recipe, self._tabs, self.session_context)
            logger.info("Recipe applied: %s", recipe.name)

    def open_recipe_library(self) -> None:
        """Open the recipe library directory in the system file manager."""
        library_dir = get_recipe_library_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(library_dir)))

    # ------------------------------------------------------------------
    # Cross-tab handoff
    # ------------------------------------------------------------------

    def handoff_to_tab(
        self,
        target_tab_id: str,
        asset_id: str | None = None,
        role: str | None = None,
    ) -> None:
        """Switch to a target tab and optionally pre-fill with an asset.

        Parameters
        ----------
        target_tab_id : str
            The ``tab_id`` of the tab to switch to.
        asset_id : str | None
            If provided, the asset ID to pre-fill in the target tab.
        role : str | None
            If provided and *asset_id* is given, assign this role to the
            asset in the session context before switching.
        """
        # Assign role if requested
        if asset_id and role:
            asset = self.session_context.get_asset(asset_id)
            if asset is not None:
                self.session_context.set_role(asset_id, role)

        # Switch to target tab — search both real tabs and lazy placeholders
        for i in range(self._stack.count()):
            widget = self._stack.widget(i)
            # Check instantiated tabs
            if isinstance(widget, BaseTab) and widget.tab_id == target_tab_id:
                self._sidebar.set_active(i)
                self._stack.setCurrentIndex(i)
                self._update_undo_actions()
                logger.info(
                    "Handoff to tab '%s' (asset=%s, role=%s)",
                    target_tab_id,
                    asset_id,
                    role,
                )
                return
            # Check lazy placeholders
            for tid, placeholder in self._lazy_placeholders.items():
                if placeholder is widget and tid == target_tab_id:
                    self._ensure_tab_instantiated(i)
                    self._sidebar.set_active(i)
                    self._stack.setCurrentIndex(i)
                    self._update_undo_actions()
                    logger.info(
                        "Handoff to tab '%s' (asset=%s, role=%s)",
                        target_tab_id,
                        asset_id,
                        role,
                    )
                    return

        logger.warning("Handoff target tab '%s' not found.", target_tab_id)

    def handoff_srt_gen_to_srt_edit(self, asset_id: str | None = None) -> None:
        """Handoff from SRT Gen to SRT Edit after transcription."""
        self.handoff_to_tab("srt_edit", asset_id=asset_id, role="subtitle_source")

    def handoff_srt_edit_to_caption_animate(self, asset_id: str | None = None) -> None:
        """Handoff from SRT Edit to Caption Animate after saving."""
        self.handoff_to_tab("caption_animate", asset_id=asset_id, role="caption_source")

    def handoff_to_composition(self, asset_id: str | None = None) -> None:
        """Handoff from Caption Animate or Audio Visualizer to Composition."""
        self.handoff_to_tab("render_composition", asset_id=asset_id)

    # ------------------------------------------------------------------
    # Global busy state (shared job pool)
    # ------------------------------------------------------------------

    def set_global_busy(self, is_busy: bool, owner_tab_id: str | None = None) -> None:
        """Notify all tabs about shared pool busy state."""
        self._global_busy = is_busy
        self._busy_owner_tab_id = owner_tab_id if is_busy else None
        for tab in self._tabs:
            tab.set_global_busy(is_busy, owner_tab_id)
        if is_busy and owner_tab_id:
            idx = self._find_stack_index_for_tab_id(owner_tab_id)
            if idx >= 0:
                self._sidebar.set_busy(idx, True)
        elif not is_busy:
            for i in range(self._stack.count()):
                self._sidebar.set_busy(i, False)

    def is_global_busy(self) -> bool:
        """Return whether the shared job pool is busy."""
        return self._global_busy

    def try_start_job(self, owner_tab_id: str) -> bool:
        """Attempt to start a job. Returns False if pool is busy."""
        if self._global_busy:
            QMessageBox.information(
                self,
                "Job in Progress",
                f"Cannot start a new job while another is running.\n"
                f"Active job owned by: {self._busy_owner_tab_id or 'unknown'}",
            )
            return False
        self.set_global_busy(True, owner_tab_id)
        return True

    def finish_job(self, owner_tab_id: str) -> None:
        """Mark the shared pool as idle after job completion."""
        self.set_global_busy(False)

    # ------------------------------------------------------------------
    # Job status widget integration
    # ------------------------------------------------------------------

    def show_job_status(self, job_type: str, owner_tab: str, label: str) -> None:
        """Show job info in the persistent status area."""
        self._job_status.show_job(job_type, owner_tab, label)

    def update_job_progress(self, percent: float, message: str) -> None:
        """Update the persistent job progress."""
        self._job_status.update_progress(percent, message)

    def update_job_status(self, message: str) -> None:
        """Update the persistent job status text."""
        self._job_status.update_status(message)

    def show_job_completed(self, message: str, output_path: str | None = None,
                           owner_tab_id: str | None = None) -> None:
        """Show completion in status and offer actions instead of modal dialog."""
        self._job_status.show_completed(message, output_path=output_path)
        self.finish_job(owner_tab_id or "")

    def show_job_failed(self, error: str, owner_tab_id: str | None = None) -> None:
        """Show error in status area."""
        self._job_status.show_failed(error)
        self.finish_job(owner_tab_id or "")

    def show_job_canceled(self, message: str | None = None,
                          owner_tab_id: str | None = None) -> None:
        """Show canceled state in status area."""
        self._job_status.show_canceled(message or "Job canceled.")
        self.finish_job(owner_tab_id or "")

    def _on_cancel_requested(self) -> None:
        """Handle cancel from job status widget."""
        tab = self._tab_map.get(self._busy_owner_tab_id or "")
        if tab and hasattr(tab, "cancel_job"):
            tab.cancel_job()

    def _open_preview(self, output_path: str) -> None:
        """Open RenderDialog for previewing output."""
        from audio_visualizer.visualizers.utilities import VideoData
        from audio_visualizer.ui.renderDialog import RenderDialog
        # Create minimal VideoData for the dialog
        video_data = VideoData(0, 0, 0, file_path=output_path)
        dialog = RenderDialog(video_data)
        dialog.exec()

    def _open_output(self, output_path: str) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path)))

    def _open_output_folder(self, output_path: str) -> None:
        folder = Path(output_path).parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # ------------------------------------------------------------------
    # Update checking
    # ------------------------------------------------------------------

    def check_for_updates(self) -> None:
        self.check_updates_action.setEnabled(False)
        worker = UpdateCheckWorker()
        worker.signals.finished.connect(self._handle_update_check_result)
        worker.signals.error.connect(self._handle_update_check_error)
        self._background_thread_pool.start(worker)

    def _handle_update_check_result(self, current_version: str,
                                     latest_version: str, url: str) -> None:
        self.check_updates_action.setEnabled(True)
        if not latest_version:
            QMessageBox.information(
                self, "Check for Updates",
                "Unable to determine the latest version.",
            )
            return
        if updater.is_update_available(current_version, latest_version):
            message = QMessageBox(self)
            message.setIcon(QMessageBox.Icon.Information)
            message.setWindowTitle("Update Available")
            message.setText(
                f"A new version is available.\n\n"
                f"Current: {current_version}\nLatest: {latest_version}"
            )
            open_button = message.addButton(
                "Open Release Page", QMessageBox.ButtonRole.AcceptRole,
            )
            message.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            message.exec()
            if message.clickedButton() == open_button and url:
                QDesktopServices.openUrl(QUrl(url))
        else:
            QMessageBox.information(
                self, "Check for Updates",
                f"You are up to date.\n\n"
                f"Current: {current_version}\nLatest: {latest_version}",
            )

    def _handle_update_check_error(self, error: str) -> None:
        self.check_updates_action.setEnabled(True)
        QMessageBox.warning(self, "Check for Updates", error)

    # ------------------------------------------------------------------
    # Settings dialog & theme
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        """Open the Settings dialog."""
        from audio_visualizer.ui.settingsDialog import SettingsDialog
        current = self._collect_settings()
        dialog = SettingsDialog(current, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            result = dialog.result_settings
            app_settings = result.get("app", {})
            theme_mode = app_settings.get("theme_mode", "off")
            self._apply_theme(theme_mode)
            # Apply project folder
            project_folder = result.get("project_folder", "")
            if project_folder:
                self.session_context.set_project_folder(Path(project_folder))
            else:
                self.session_context.set_project_folder(None)
            # Save immediately
            self._save_settings_to_path(self._default_settings_path())

    def _apply_theme(self, mode: str) -> None:
        """Apply the theme based on mode: 'off', 'on', 'auto'."""
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette, QColor
        from PySide6.QtCore import Qt

        self._current_theme_mode = mode

        app = QApplication.instance()
        if app is None:
            return

        if mode == "on":
            # Dark theme
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
            palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
            palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128))
            palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128, 128, 128))
            app.setPalette(palette)
        elif mode == "auto":
            # Try system theme detection, fall back to default
            try:
                scheme = app.styleHints().colorScheme()
                if hasattr(scheme, 'name') and 'dark' in str(scheme).lower():
                    self._apply_theme("on")
                    return
            except (AttributeError, RuntimeError):
                pass
            # Fall back to system default
            app.setPalette(app.style().standardPalette())
        else:
            # Light theme (off) - restore default
            app.setPalette(app.style().standardPalette())

    # ------------------------------------------------------------------
    # Settings persistence (versioned schema)
    # ------------------------------------------------------------------

    def _default_settings_path(self) -> Path:
        return get_config_dir() / "last_settings.json"

    def _collect_settings(self) -> dict:
        """Collect settings from all tabs into the versioned schema."""
        schema = create_default_schema()
        # App settings
        schema["app"]["theme_mode"] = self._current_theme_mode
        # UI state
        active = self.active_tab()
        schema["ui"]["last_active_tab"] = active.tab_id if active else "audio_visualizer"
        schema["ui"]["window"]["width"] = self.width()
        schema["ui"]["window"]["height"] = self.height()
        schema["ui"]["window"]["maximized"] = self.isMaximized()

        # Tab settings (instantiated tabs)
        for tab in self._tabs:
            schema["tabs"][tab.tab_id] = tab.collect_settings()

        # Include pending settings for tabs not yet instantiated
        for tab_id, settings in self._pending_tab_settings.items():
            if tab_id not in schema["tabs"] or not schema["tabs"][tab_id]:
                schema["tabs"][tab_id] = settings

        # Session
        schema["session"] = self.session_context.to_dict()
        return schema

    def _apply_settings(self, data: dict) -> None:
        """Apply settings from a versioned schema to all tabs."""
        data = migrate_settings(data)

        # App settings
        app_data = data.get("app", {})
        theme_mode = app_data.get("theme_mode", "off")
        self._apply_theme(theme_mode)

        # UI state
        ui_state = data.get("ui", {})
        window = ui_state.get("window", {})
        if window.get("maximized"):
            self.showMaximized()
        else:
            w = window.get("width", 1600)
            h = window.get("height", 1000)
            self.resize(w, h)

        # Tab settings — apply to instantiated tabs, store for lazy ones
        tabs_data = data.get("tabs", {})
        for tab in self._tabs:
            tab_data = tabs_data.get(tab.tab_id, {})
            if tab_data:
                tab.apply_settings(tab_data)

        for tab_id in list(self._lazy_placeholders.keys()):
            if tab_id in tabs_data and tabs_data[tab_id]:
                self._pending_tab_settings[tab_id] = tabs_data[tab_id]

        # Session
        session_data = data.get("session", {})
        if session_data:
            self.session_context.from_dict(session_data)

        # Restore active tab
        last_tab = ui_state.get("last_active_tab", "audio_visualizer")
        idx = self._find_stack_index_for_tab_id(last_tab)
        if idx >= 0:
            self._ensure_tab_instantiated(idx)
            self._sidebar.set_active(idx)
            self._stack.setCurrentIndex(idx)
        self._update_undo_actions()

    def _save_settings_to_path(self, path: Path) -> bool:
        try:
            data = self._collect_settings()
            save_settings(data, path)
        except Exception:
            logger.exception("Failed to save settings to %s", path)
            return False
        return True

    def _load_settings_from_path(self, path: Path) -> bool:
        data = load_settings(path)
        if data is None:
            return False
        self._apply_settings(data)
        return True

    def _load_last_settings_if_present(self) -> None:
        path = self._default_settings_path()
        if path.exists():
            self._load_settings_from_path(path)

    def save_project(self) -> None:
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Save Project")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("JSON Files (*.json)")
        dialog.setDefaultSuffix("json")
        if dialog.exec():
            path = Path(dialog.selectedFiles()[0])
            if not self._save_settings_to_path(path):
                QMessageBox(
                    QMessageBox.Icon.Critical, "Save Failed",
                    "Unable to save the project file.",
                ).exec()

    def load_project(self) -> None:
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Load Project")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("JSON Files (*.json)")
        if dialog.exec():
            path = Path(dialog.selectedFiles()[0])
            if not self._load_settings_from_path(path):
                QMessageBox(
                    QMessageBox.Icon.Critical, "Load Failed",
                    "Unable to load the project file.",
                ).exec()

    def closeEvent(self, event) -> None:
        self._save_settings_to_path(self._default_settings_path())
        super().closeEvent(event)


# ------------------------------------------------------------------
# Background workers
# ------------------------------------------------------------------

class UpdateCheckWorker(QRunnable):
    def __init__(self) -> None:
        super().__init__()

        class UpdateSignals(QObject):
            finished = Signal(str, str, str)
            error = Signal(str)

        self.signals = UpdateSignals()

    def run(self) -> None:
        try:
            current = updater.get_current_version()
            latest = updater.fetch_latest_release()
            self.signals.finished.emit(
                current, latest.get("version", ""), latest.get("url", ""),
            )
        except Exception as exc:
            self.signals.error.emit(str(exc))


class RenderWorker(QRunnable):
    """Render worker for the Audio Visualizer tab.

    Produces video frames from a Visualizer instance and optionally
    muxes audio into the output container.
    """

    def __init__(self, audio_data, video_data, visualizer,
                 preview_seconds=None, include_audio=False) -> None:
        super().__init__()
        from audio_visualizer.visualizers.utilities import AudioData, VideoData
        from audio_visualizer.visualizers import Visualizer
        self.audio_data = audio_data
        self.video_data = video_data
        self.visualizer = visualizer
        self.preview_seconds = preview_seconds
        self.include_audio = include_audio
        self.audio_input_container = None
        self.audio_input_stream = None
        self.audio_output_stream = None
        self.audio_resampler = None
        self._cancel_requested = False
        self._logger = logging.getLogger(__name__)
        self._av = None

        class RenderSignals(QObject):
            finished = Signal(object)
            error = Signal(str)
            status = Signal(str)
            progress = Signal(int, int, float)
            canceled = Signal()
            mux_progress = Signal(float)  # 0.0-1.0 fraction of mux done
        self.signals = RenderSignals()

    def _get_av(self):
        if self._av is None:
            import av
            self._av = av
        return self._av

    def cancel(self) -> None:
        self._cancel_requested = True

    def _check_canceled(self) -> bool:
        if not self._cancel_requested:
            return False
        self._cleanup_on_cancel()
        self.signals.canceled.emit()
        return True

    def _cleanup_on_cancel(self) -> None:
        try:
            if getattr(self.video_data, "container", None) is not None:
                self.video_data.container.close()
        except Exception:
            pass
        try:
            if self.audio_input_container is not None:
                self.audio_input_container.close()
        except Exception:
            pass

    def run(self) -> None:
        try:
            self.signals.status.emit("Opening audio file...")
            if not self.audio_data.load_audio_data(self.preview_seconds):
                error = self.audio_data.last_error or "Unknown error."
                self._logger.error("Audio load failed: %s", error)
                self.signals.error.emit(f"Error opening audio file: {error}")
                return
            if self._check_canceled():
                return

            self.signals.status.emit("Analyzing audio data...")
            self.audio_data.chunk_audio(self.video_data.fps)
            self.audio_data.analyze_audio()
            if self._check_canceled():
                return

            self.signals.status.emit("Preparing video environment...")
            if not self.video_data.prepare_container():
                error = self.video_data.last_error or "Unknown error."
                self._logger.error("Video container setup failed: %s", error)
                self.signals.error.emit(f"Error opening video file: {error}")
                return
            if self._check_canceled():
                return

            if self.include_audio:
                self.signals.status.emit("Preparing audio mux...")
                if not self._prepare_audio_mux():
                    error = self._last_error or "Unknown error."
                    self._logger.error("Audio mux prep failed: %s", error)
                    self.signals.error.emit(f"Error preparing audio stream: {error}")
                    return
                if self._check_canceled():
                    return
            self.visualizer.prepare_shapes()

            frames = len(self.audio_data.audio_frames)
            if self.preview_seconds is not None:
                frames = min(len(self.audio_data.audio_frames),
                             self.video_data.fps * self.preview_seconds)

            self.signals.status.emit("Rendering video (0 %) ...")
            start_time = time.time()
            last_progress_emit = 0.0
            av = self._get_av()
            for i in range(frames):
                if self._check_canceled():
                    return
                img = self.visualizer.generate_frame(i)
                frame = av.VideoFrame.from_ndarray(img, format="rgb24")
                for packet in self.video_data.stream.encode(frame):
                    self.video_data.container.mux(packet)

                now = time.time()
                if now - last_progress_emit >= 0.5 or i == frames - 1:
                    elapsed = now - start_time
                    self.signals.progress.emit(i + 1, frames, elapsed)
                    last_progress_emit = now

            self.signals.status.emit("Render finished, saving file...")
            if self._check_canceled():
                return
            if self.include_audio:
                self.signals.status.emit("Muxing audio...")
                mux_result = self._mux_audio()
                if mux_result is None:
                    return
                if mux_result is False:
                    error = self._last_error or "Unknown error."
                    self._logger.error("Audio mux failed: %s", error)
                    self.signals.error.emit(f"Error muxing audio: {error}")
                    return
            if not self.video_data.finalize():
                error = self.video_data.last_error or "Unknown error."
                self._logger.error("Finalize failed: %s", error)
                self.signals.error.emit(f"Error closing video file: {error}")
                return
            self.signals.finished.emit(self.video_data)
        except Exception as exc:
            self._logger.exception("Unhandled error during render.")
            self.signals.error.emit(f"Unexpected error: {exc}")

    def _prepare_audio_mux(self) -> bool:
        self._last_error = ""
        av = self._get_av()
        try:
            self.audio_input_container = av.open(self.audio_data.file_path)
        except Exception as exc:
            self._last_error = str(exc)
            return False

        for stream in self.audio_input_container.streams:
            if stream.type == "audio":
                self.audio_input_stream = stream
                break
        if self.audio_input_stream is None:
            self._last_error = "No audio stream found in input."
            return False

        try:
            self.audio_output_stream = self.video_data.container.add_stream(
                "aac", rate=self.audio_input_stream.rate,
            )
        except Exception as exc:
            self._last_error = str(exc)
            return False

        self.audio_output_stream.layout = self.audio_input_stream.layout.name
        self.audio_output_stream.sample_rate = self.audio_input_stream.rate
        self.audio_output_stream.time_base = Fraction(1, self.audio_output_stream.rate)

        resample_format = "fltp"
        if (self.audio_output_stream.format is not None
                and self.audio_output_stream.format.name):
            resample_format = self.audio_output_stream.format.name
        self.audio_resampler = av.audio.resampler.AudioResampler(
            format=resample_format,
            layout=self.audio_output_stream.layout.name,
            rate=self.audio_output_stream.rate,
        )
        self._last_error = ""
        return True

    def _mux_audio(self) -> bool | None:
        if self.audio_input_container is None or self.audio_input_stream is None:
            self._last_error = "Missing audio input."
            return False
        if self.audio_output_stream is None or self.audio_resampler is None:
            self._last_error = "Missing audio output."
            return False

        # Determine total audio duration for progress reporting.
        total_duration = 0.0
        if self.preview_seconds is not None:
            total_duration = float(self.preview_seconds)
        elif self.audio_input_stream.duration and self.audio_input_stream.time_base:
            total_duration = float(
                self.audio_input_stream.duration * self.audio_input_stream.time_base
            )

        samples_written = 0
        stop_at_time = False
        last_mux_emit = 0.0
        try:
            for packet in self.audio_input_container.demux(self.audio_input_stream):
                if self._cancel_requested:
                    self._cleanup_on_cancel()
                    self.signals.canceled.emit()
                    return None
                if stop_at_time:
                    break
                for frame in packet.decode():
                    if self._cancel_requested:
                        self._cleanup_on_cancel()
                        self.signals.canceled.emit()
                        return None
                    current_time = 0.0
                    if frame.pts is not None:
                        current_time = float(frame.pts * frame.time_base)
                        if self.preview_seconds is not None:
                            if current_time >= self.preview_seconds:
                                stop_at_time = True
                                break
                    for resampled in self.audio_resampler.resample(frame):
                        if self._cancel_requested:
                            self._cleanup_on_cancel()
                            self.signals.canceled.emit()
                            return None
                        if resampled.pts is None:
                            resampled.pts = samples_written
                            resampled.time_base = self.audio_output_stream.time_base
                        samples_written += resampled.samples
                        for out_packet in self.audio_output_stream.encode(resampled):
                            self.video_data.container.mux(out_packet)
                    # Emit mux progress periodically
                    now = time.time()
                    if total_duration > 0 and now - last_mux_emit >= 0.5:
                        frac = min(current_time / total_duration, 1.0)
                        self.signals.mux_progress.emit(frac)
                        last_mux_emit = now
        except Exception as exc:
            self._last_error = str(exc)
            return False

        for out_packet in self.audio_output_stream.encode():
            self.video_data.container.mux(out_packet)

        self.signals.mux_progress.emit(1.0)

        try:
            self.audio_input_container.close()
        except Exception as exc:
            self._last_error = str(exc)
            return False
        return True
