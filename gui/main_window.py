from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QDockWidget,
    QSplitter,
)

from core.export import ExportService
from core.load_worker import LoadWorker
from core.signal_store import SignalStore
from gui.plot_widget import PlotPanel
from gui.signal_tree import SignalTreeWidget
from gui.raw_frame_dialog import RawFrameDialog


class MainWindow(QMainWindow):
    def __init__(self, app_name: str, version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app_name = app_name
        self.version = version
        self.setWindowTitle(f'{app_name} {version}')
        self.resize(1700, 950)

        self.blf_path: str | None = None
        self.dbc_path: str | None = None
        self.store: SignalStore | None = None
        self._thread: QThread | None = None
        self._worker: LoadWorker | None = None
        self._pending_plot_keys: list[str] = []
        self._pending_plot_colors: dict[str, str] = {}
        self._raw_frame_dialog = None
        self._log_file_path = Path(__file__).resolve().parents[1] / 'blf_viewer_dev.log'

        self._build_ui()
        self._build_toolbar()
        self._build_shortcuts()
        self._set_ready_status()
        self._log(f'{self.app_name} {self.version} started.')
        self._log(f'Dev log file: {self._log_file_path}')
        self._update_measurement_tab()

    def _build_ui(self) -> None:
        self.signal_tree = SignalTreeWidget()
        self.plot_panel = PlotPanel()
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.diagnostics_box = QTextEdit()
        self.diagnostics_box.setReadOnly(True)
        self.measurement_box = QTextEdit()
        self.measurement_box.setReadOnly(True)

        self.signal_tree.signalActivated.connect(self.add_signals_to_plot)
        self.plot_panel.selectionChanged.connect(self._on_plot_selection_changed)
        self.plot_panel.signalDropped.connect(self.add_signals_to_plot)
        self.plot_panel.backgroundColorChanged.connect(self._on_background_color_changed)
        self.plot_panel.signalColorChanged.connect(self._on_signal_color_changed)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_fit = QPushButton('Fit to Window')
        self.btn_move_up = QPushButton('Move Up')
        self.btn_move_down = QPushButton('Move Down')
        self.btn_remove = QPushButton('Remove Selected Plot')
        self.btn_clear = QPushButton('Clear Plots')
        self.btn_export = QPushButton('Export Selected CSV')
        self.btn_multi_axis = QPushButton('Multi-Axis')
        self.btn_multi_axis.setCheckable(True)
        self.btn_stacked = QPushButton('Stacked')
        self.btn_stacked.setCheckable(True)
        self.btn_raw_frames = QPushButton('Raw Frames')
        self.btn_points = QPushButton('Show Data Points')
        self.btn_points.setCheckable(True)
        for btn in (self.btn_fit, self.btn_move_up, self.btn_move_down, self.btn_remove, self.btn_clear, self.btn_export, self.btn_multi_axis, self.btn_stacked, self.btn_raw_frames, self.btn_points):
            button_layout.addWidget(btn)
        button_layout.addStretch(1)

        self.btn_fit.clicked.connect(self.plot_panel.fit_to_window)
        self.btn_move_up.clicked.connect(self.plot_panel.move_selected_up)
        self.btn_move_down.clicked.connect(self.plot_panel.move_selected_down)
        self.btn_remove.clicked.connect(self.plot_panel.remove_selected_series)
        self.btn_clear.clicked.connect(self.plot_panel.clear_all)
        self.btn_export.clicked.connect(self.export_selected_csv)
        self.btn_multi_axis.toggled.connect(self._toggle_multi_axis)
        self.btn_stacked.toggled.connect(self._toggle_stacked)
        self.btn_raw_frames.clicked.connect(self.show_raw_frames)
        self.btn_points.toggled.connect(self._toggle_points)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(6, 6, 6, 6)
        center_layout.addWidget(button_row)

        self.center_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.center_splitter.setChildrenCollapsible(False)
        self.center_splitter.addWidget(self.plot_panel.table_panel)
        self.center_splitter.addWidget(self.plot_panel)
        self.center_splitter.setStretchFactor(0, 0)
        self.center_splitter.setStretchFactor(1, 1)
        self.center_splitter.setSizes([240, 1280])
        center_layout.addWidget(self.center_splitter, stretch=1)
        self.setCentralWidget(center_panel)

        self.left_dock = QDockWidget('Decoded Signals', self)
        self.left_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.left_dock.setWidget(self.signal_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.left_dock)

        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.addTab(self.log_box, 'Log')
        self.bottom_tabs.addTab(self.diagnostics_box, 'Diagnostics')
        self.bottom_tabs.addTab(self.measurement_box, 'Measurement')
        self.bottom_dock = QDockWidget('Log / Diagnostics / Measurement', self)
        self.bottom_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.bottom_dock.setWidget(self.bottom_tabs)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.bottom_dock)

        self.resizeDocks([self.bottom_dock], [180], Qt.Vertical)

        left_title = QWidget()
        left_title_layout = QHBoxLayout(left_title)
        left_title_layout.setContentsMargins(4, 2, 4, 2)
        left_title_layout.addWidget(QLabel('Decoded Signals'))
        left_title_layout.addStretch(1)
        self.left_toggle_btn = QToolButton()
        self.left_toggle_btn.setText('◀')
        self.left_toggle_btn.clicked.connect(self._toggle_left_panel)
        left_title_layout.addWidget(self.left_toggle_btn)
        self.left_dock.setTitleBarWidget(left_title)

        bottom_title = QWidget()
        bottom_title_layout = QHBoxLayout(bottom_title)
        bottom_title_layout.setContentsMargins(4, 2, 4, 2)
        bottom_title_layout.addWidget(QLabel('Log / Diagnostics / Measurement'))
        bottom_title_layout.addStretch(1)
        self.bottom_toggle_btn = QToolButton()
        self.bottom_toggle_btn.setText('▼')
        self.bottom_toggle_btn.clicked.connect(self._toggle_bottom_panel)
        bottom_title_layout.addWidget(self.bottom_toggle_btn)
        self.bottom_dock.setTitleBarWidget(bottom_title)

        self.left_dock.visibilityChanged.connect(self._sync_panel_toggle_buttons)
        self.bottom_dock.visibilityChanged.connect(self._sync_panel_toggle_buttons)

        self.left_edge_btn = QToolButton(self)
        self.left_edge_btn.setAutoRaise(True)
        self.left_edge_btn.setFixedWidth(18)
        self.left_edge_btn.clicked.connect(self._toggle_left_panel)
        self.left_edge_btn.show()

        self.bottom_edge_btn = QToolButton(self)
        self.bottom_edge_btn.setAutoRaise(True)
        self.bottom_edge_btn.setFixedHeight(18)
        self.bottom_edge_btn.clicked.connect(self._toggle_bottom_panel)
        self.bottom_edge_btn.show()

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.status_state_label = QLabel('State: Ready')
        self.status_next_step_label = QLabel('Next: Open BLF, then Open DBC, then Load + Decode')
        self.statusBar().addWidget(self.status_state_label)
        self.statusBar().addPermanentWidget(self.status_next_step_label, 1)
        self._sync_panel_toggle_buttons()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar('Main')
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, slot in [
            ('Open BLF', self.choose_blf),
            ('Open DBC', self.choose_dbc),
            ('Load + Decode', self.load_data),
            ('Raw Frames', self.show_raw_frames),
            ('Save Config', self.save_configuration),
            ('Load Config', self.load_configuration),
            ('Export CSV', self.export_selected_csv),
            ('Clear Plots', self.plot_panel.clear_all),
        ]:
            act = QAction(text, self)
            act.triggered.connect(slot)
            toolbar.addAction(act)
            if text in {'Load + Decode', 'Load Config'}:
                toolbar.addSeparator()

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self.plot_panel.remove_selected_series)
        QShortcut(QKeySequence('Ctrl+S'), self, activated=self.save_configuration)
        QShortcut(QKeySequence('F'), self, activated=self.plot_panel.fit_to_window)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=lambda: self.add_signals_to_plot(self.signal_tree.selected_signal_keys()))
        QShortcut(QKeySequence('Ctrl+Up'), self, activated=self.plot_panel.move_selected_up)
        QShortcut(QKeySequence('Ctrl+Down'), self, activated=self.plot_panel.move_selected_down)

    def choose_blf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Open BLF file', '', 'Vector BLF (*.blf)')
        if not path:
            return
        self.blf_path = path
        self._log(f'Selected BLF: {path}')
        self._update_measurement_tab()
        self._update_status('BLF selected', self._next_step_message())

    def choose_dbc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Open DBC file', '', 'DBC Files (*.dbc)')
        if not path:
            return
        self.dbc_path = path
        self._log(f'Selected DBC: {path}')
        self._update_measurement_tab()
        self._update_status('DBC selected', self._next_step_message())

    def _toggle_multi_axis(self, checked: bool) -> None:
        if checked:
            self.btn_stacked.setChecked(False)   # mutually exclusive
        self.plot_panel.set_multi_axis(checked)
        self._update_status('Plot mode updated', 'Continue plotting or fit the view')

    def _toggle_stacked(self, checked: bool) -> None:
        if checked:
            self.btn_multi_axis.setChecked(False)  # mutually exclusive
        self.plot_panel.set_stacked(checked)
        self._update_status('Plot mode updated', 'Continue plotting or fit the view')

    def show_raw_frames(self) -> None:
        if not self.store or not getattr(self.store, 'raw_frames', None):
            QMessageBox.information(self, 'No raw frames', 'Load and decode a BLF/DBC first.')
            return
        self._raw_frame_dialog = RawFrameDialog(self.store.raw_frames, self)
        self._raw_frame_dialog.show()
        self._raw_frame_dialog.raise_()
        self._raw_frame_dialog.activateWindow()

    def _toggle_points(self, checked: bool) -> None:
        self.plot_panel.set_show_points(checked)
        self.btn_points.setText('Hide Data Points' if checked else 'Show Data Points')
        self._update_status('Plot markers updated', 'Continue plotting, fit view, or save configuration')

    def save_configuration(self) -> None:
        config = {
            'version': self.version,
            'blf_path': self.blf_path,
            'dbc_path': self.dbc_path,
            'signals': self.plot_panel.plotted_keys(),
            'show_data_points': self.btn_points.isChecked(),
            'plot_background_color': self.plot_panel.background_color(),
            'signal_colors': self.plot_panel.series_colors(),
            'multi_axis': self.btn_multi_axis.isChecked(),
        }
        path, _ = QFileDialog.getSaveFileName(self, 'Save configuration', 'blf_viewer_config.json', 'JSON Files (*.json)')
        if not path:
            return
        try:
            Path(path).write_text(json.dumps(config, indent=2), encoding='utf-8')
            self._log(f'Saved configuration: {path}')
            self._update_status('Configuration saved', 'Load it later to reopen BLF, DBC, and plotted signals')
        except Exception as exc:
            QMessageBox.critical(self, 'Save configuration failed', str(exc))
            self._update_status('Save failed', 'Check path permissions and try again')

    def load_configuration(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Load configuration', '', 'JSON Files (*.json)')
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except Exception as exc:
            QMessageBox.critical(self, 'Load configuration failed', str(exc))
            return
        self.blf_path = data.get('blf_path')
        self.dbc_path = data.get('dbc_path')
        self._pending_plot_keys = list(data.get('signals') or [])
        self._pending_plot_colors = dict(data.get('signal_colors') or {})
        self.btn_points.setChecked(bool(data.get('show_data_points', False)))
        bg = data.get('plot_background_color')
        if bg:
            self.plot_panel.set_background_color(str(bg))
        self.btn_multi_axis.setChecked(bool(data.get('multi_axis', False)))
        self._update_measurement_tab()
        if not self.blf_path or not self.dbc_path:
            QMessageBox.warning(self, 'Incomplete configuration', 'The configuration file does not contain both BLF and DBC paths.')
            return
        self._log(f'Configuration loaded: {path}')
        self.load_data(pending_plot_keys=self._pending_plot_keys)

    def load_data(self, pending_plot_keys: list[str] | None = None) -> None:
        if not self.blf_path or not self.dbc_path:
            QMessageBox.warning(self, 'Missing file', 'Please select both a BLF file and a DBC file.')
            self._update_status('Waiting for input', self._next_step_message())
            return
        self._pending_plot_keys = list(pending_plot_keys or [])
        self.plot_panel.clear_all()
        self.signal_tree.set_payload({})
        self.diagnostics_box.clear()
        self.store = None
        self._update_measurement_tab(frames='0', decoded='0', samples='0', channels='0')
        self._log('Starting BLF load and DBC decode...')
        self._update_status('Loading and decoding...', 'Wait for decode to finish, then inspect Diagnostics and plot signals')
        self._thread = QThread(self)
        self._worker = LoadWorker(self.blf_path, self.dbc_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def add_signals_to_plot(self, keys) -> None:
        if isinstance(keys, str):
            keys = [keys]
        plotted = 0
        for key in keys or []:
            if self.add_signal_to_plot(key, fit=False):
                plotted += 1
        if plotted:
            self.plot_panel.fit_to_window()
            self._update_status(f'Plotted {plotted} signal(s)', 'Use Fit to Window, reorder, or export selected CSV')

    def add_signal_to_plot(self, key: str, fit: bool = True) -> bool:
        if not self.store:
            return False
        series = self.store.get_series(key)
        if not series:
            self._log(f'Signal not found: {key}')
            return False
        self.plot_panel.add_series(key, series)
        if fit:
            self.plot_panel.fit_to_window()
        return True

    def export_selected_csv(self) -> None:
        series_items = self.plot_panel.plotted_series()
        if not series_items:
            QMessageBox.information(self, 'No plots', 'Plot one or more signals before exporting CSV.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export selected signals', 'selected_signals.csv', 'CSV Files (*.csv)')
        if not path:
            return
        try:
            ExportService.export_series_to_csv(series_items, path)
            self._log(f'Exported CSV: {path}')
        except Exception as exc:
            QMessageBox.critical(self, 'Export failed', str(exc))

    def _on_worker_progress(self, message: str) -> None:
        self._log(message)
        self._update_status(message, 'Wait for decode to finish')

    def _on_worker_finished(self, store: SignalStore) -> None:
        self.store = store
        self.signal_tree.set_payload(store.build_tree_payload())
        self.diagnostics_box.setPlainText(store.diagnostics_text)
        self._update_measurement_tab(
            channels=store.channel_summary_text(),
            frames=f'{store.total_frames:,}',
            decoded=f'{store.decoded_frames:,}',
            samples=f'{store.total_samples:,}',
        )
        self._log('Decode finished successfully.')
        if self._pending_plot_keys:
            wanted = list(self._pending_plot_keys)
            colors = dict(self._pending_plot_colors)
            self._pending_plot_keys = []
            self.add_signals_to_plot(wanted)
            for key, color in colors.items():
                self.plot_panel.set_series_color(key, color)
            self._pending_plot_colors = {}
        self._update_status('Decode complete', 'Select signal(s) and plot them by double-click, right-click, drag, or Space.')

    def _on_worker_failed(self, error_message: str) -> None:
        self._log(f'ERROR: {error_message}')
        QMessageBox.critical(self, 'Load failed', error_message)
        self._update_status('Load failed', 'Review the log, verify BLF/DBC paths, and try again')

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
            self._thread = None

    def _on_plot_selection_changed(self, key: str) -> None:
        self._update_status(f'Selected plot: {key}', 'Delete removes selected plot rows; Ctrl+Up/Down reorders them')

    def _toggle_left_panel(self) -> None:
        self.left_dock.setVisible(not self.left_dock.isVisible())
        self._sync_panel_toggle_buttons()

    def _toggle_bottom_panel(self) -> None:
        self.bottom_dock.setVisible(not self.bottom_dock.isVisible())
        self._sync_panel_toggle_buttons()

    def _sync_panel_toggle_buttons(self) -> None:
        left_visible = self.left_dock.isVisible()
        bottom_visible = self.bottom_dock.isVisible()
        self.left_toggle_btn.setText('◀' if left_visible else '▶')
        self.bottom_toggle_btn.setText('▼' if bottom_visible else '▲')
        self.left_edge_btn.setText('◀' if left_visible else '▶')
        self.bottom_edge_btn.setText('▼' if bottom_visible else '▲')
        self._position_panel_toggle_buttons()

    def _position_panel_toggle_buttons(self) -> None:
        left_w = self.left_edge_btn.width() or 18
        left_h = max(self.left_edge_btn.sizeHint().height(), 36)
        x = 2
        y = max(80, (self.height() - left_h) // 2)
        self.left_edge_btn.setGeometry(x, y, left_w, left_h)
        self.left_edge_btn.raise_()

        btn_w = max(self.bottom_edge_btn.sizeHint().width(), 36)
        btn_h = self.bottom_edge_btn.height() or 18
        bottom_h = self.bottom_dock.height() if self.bottom_dock.isVisible() else 0
        y = self.height() - self.statusBar().height() - bottom_h - btn_h - 2
        y = max(80, y)
        x = max(40, (self.width() - btn_w) // 2)
        self.bottom_edge_btn.setGeometry(x, y, btn_w, btn_h)
        self.bottom_edge_btn.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_panel_toggle_buttons()

    def _on_background_color_changed(self, color: str) -> None:
        self._log(f'Plot background color changed: {color}')

    def _on_signal_color_changed(self, key: str, color: str) -> None:
        self._log(f'Signal color changed: {key} -> {color}')

    def _set_ready_status(self) -> None:
        self._update_status('Ready', "Click 'Open BLF' to load file. Click 'Open DBC' to load file.")

    def _update_status(self, state: str, next_step: str) -> None:
        self.status_state_label.setText(f'State: {state}')
        self.status_next_step_label.setText(f'Next: {next_step}')
        self.plot_panel.set_status_overlay(f'State: {state}', f'Next: {next_step}')

    def _next_step_message(self) -> str:
        if not self.blf_path and not self.dbc_path:
            return "Click 'Open BLF' to load file. Click 'Open DBC' to load file."
        if not self.blf_path:
            return "Click 'Open BLF' to load file."
        if not self.dbc_path:
            return "Click 'Open DBC' to load file."
        return "Click 'Load + Decode', then select signal(s) to plot."

    def _update_measurement_tab(self, channels: str = '', frames: str = '', decoded: str = '', samples: str = '') -> None:
        lines = [
            f'BLF: {self.blf_path or ""}',
            f'DBC: {self.dbc_path or ""}',
            f'Channels: {channels}',
            f'Frames: {frames}',
            f'Decoded Frames: {decoded}',
            f'Samples: {samples}',
        ]
        self.measurement_box.setPlainText('\n'.join(lines))

    def _log(self, message: str) -> None:
        self.log_box.append(message)
        try:
            with self._log_file_path.open('a', encoding='utf-8') as fh:
                fh.write(message + '\n')
        except Exception:
            pass
