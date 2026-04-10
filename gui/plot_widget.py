from __future__ import annotations

from dataclasses import dataclass
from itertools import cycle
from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import QAction, QBrush, QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QGridLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.signal_store import SignalSeries
from gui.signal_tree import SignalTreeWidget


@dataclass(slots=True)
class PlottedSignal:
    key: str
    series: SignalSeries
    curve: Any
    color: str
    axis: Any = None
    view_box: Any = None


class PlotPanel(QWidget):
    selectionChanged = Signal(str)
    signalDropped = Signal(list)
    backgroundColorChanged = Signal(str)
    signalColorChanged = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: dict[str, PlottedSignal] = {}
        self._current_key: str | None = None
        self._cursor_label_base = 'Cursor: move mouse over plot'
        self._show_points = False
        self._multi_axis = False
        self._stacked_mode = False
        self._extra_axes: list[tuple[Any, Any]] = []
        self._stacked_plots: list[pg.PlotItem] = []
        self._stacked_vlines: list[pg.InfiniteLine] = []
        self._proxy = None
        self._color_cycle = cycle([
            '#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00',
            '#a65628', '#f781bf', '#17becf', '#bcbd22', '#1f77b4',
        ])
        self._background_color = '#000000'
        self.setAcceptDrops(True)

        # ── Normal / multi-axis plot ──────────────────────────────────────
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self._legend = self.plot.addLegend()
        self.plot.setLabel('bottom', 'Time (seconds)')
        self.plot.setBackground(self._background_color)
        self._install_plot_background_menu()

        self.plot_host = QWidget()
        _host_layout = QGridLayout(self.plot_host)
        _host_layout.setContentsMargins(0, 0, 0, 0)
        _host_layout.addWidget(self.plot, 0, 0)

        self.overlay_label = QLabel()
        self.overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overlay_label.setWordWrap(True)
        self.overlay_label.setStyleSheet(
            'QLabel { color: white; font-size: 20px; font-weight: 600; '
            'background-color: rgba(0,0,0,110); padding: 18px; border-radius: 8px; }'
        )
        _host_layout.addWidget(self.overlay_label, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── Stacked plot (GraphicsLayoutWidget) ──────────────────────────
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setBackground(self._background_color)

        # ── View switcher ─────────────────────────────────────────────────
        self.view_stack = QStackedWidget()
        self.view_stack.addWidget(self.plot_host)   # index 0 – normal
        self.view_stack.addWidget(self.glw)          # index 1 – stacked

        # ── Status / hint labels ──────────────────────────────────────────
        self.drop_hint = QLabel(
            'Drag signal(s) here, double-click them, or right-click and choose Plot selected signal(s)'
        )
        self.cursor_label = QLabel(self._cursor_label_base)
        self.drop_hint.hide()
        self.cursor_label.hide()

        # ── Cursor lines (normal / multi-axis) ────────────────────────────
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(width=1))
        self.h_line = pg.InfiniteLine(angle=0,  movable=False, pen=pg.mkPen(width=1))
        self.plot.addItem(self.v_line, ignoreBounds=True)
        self.plot.addItem(self.h_line, ignoreBounds=True)

        # ── Signal table ──────────────────────────────────────────────────
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['Signal', 'Cursor Value', 'Unit', 'Samples'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._emit_selection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_menu)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.table_panel = QWidget()
        _tbl_layout = QVBoxLayout(self.table_panel)
        _tbl_layout.setContentsMargins(0, 0, 0, 0)
        _tbl_layout.addWidget(self.table, stretch=1)
        self._apply_panel_background()

        # ── Root layout ───────────────────────────────────────────────────
        _root = QVBoxLayout(self)
        _root.setContentsMargins(4, 4, 4, 4)
        _root.addWidget(self.view_stack, stretch=1)
        _root.addWidget(self.drop_hint)
        _root.addWidget(self.cursor_label)

        self._setup_mouse_proxy()
        self._update_empty_state_ui()

    # ── Drag / drop ───────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(SignalTreeWidget.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(SignalTreeWidget.MIME_TYPE):
            event.ignore()
            return
        payload = bytes(event.mimeData().data(SignalTreeWidget.MIME_TYPE)).decode('utf-8')
        keys = [p.strip() for p in payload.splitlines() if p.strip()]
        if keys:
            self.signalDropped.emit(keys)
            event.acceptProposedAction()
        else:
            event.ignore()

    # ── Public setters ────────────────────────────────────────────────────

    def set_show_points(self, show: bool) -> None:
        self._show_points = bool(show)
        # Bug 2 fix: applies to ALL plotted signals (PlotDataItem supports symbols)
        for plotted in self._items.values():
            self._apply_curve_style(plotted)

    def set_multi_axis(self, enabled: bool) -> None:
        self._multi_axis = bool(enabled)
        self._rebuild_curves(preserve_selection=True)
        self.fit_to_window()

    def set_stacked(self, enabled: bool) -> None:
        """Toggle INCA/CANdb-style stacked layout (one row per signal, shared X)."""
        self._stacked_mode = bool(enabled)
        self._rebuild_curves(preserve_selection=True)
        self.fit_to_window()

    def add_series(self, key: str, series: SignalSeries, color: str | None = None) -> None:
        if key in self._items:
            return
        color = color or next(self._color_cycle)
        self._items[key] = PlottedSignal(key=key, series=series, curve=None, color=color)
        if self._current_key is None:
            self._current_key = key
        self._rebuild_curves(preserve_selection=True)
        self._update_empty_state_ui()
        self.fit_to_window()

    # ── Internal: clear all rendered items ────────────────────────────────

    def _clear_rendered_items(self) -> None:
        # Disconnect resize hook before clearing
        try:
            self.plot.plotItem.vb.sigResized.disconnect(self._update_multi_axis_views)
        except Exception:
            pass

        try:
            self.plot.plotItem.clear()
        except Exception:
            pass

        for plotted in self._items.values():
            plotted.curve = None
            plotted.axis = None
            plotted.view_box = None

        for axis, vb in self._extra_axes:
            try:
                self.plot.plotItem.scene().removeItem(axis)
            except Exception:
                pass
            try:
                self.plot.plotItem.scene().removeItem(vb)
            except Exception:
                pass
        self._extra_axes.clear()

        try:
            if self._legend is not None:
                self.plot.plotItem.scene().removeItem(self._legend)
        except Exception:
            pass
        self._legend = self.plot.addLegend()

        self.plot.showAxis('right', False)
        self.plot.getAxis('right').setLabel('')
        self.plot.setLabel('left', 'Value')
        self.plot.getAxis('left').setWidth(55)

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(width=1))
        self.h_line = pg.InfiniteLine(angle=0,  movable=False, pen=pg.mkPen(width=1))
        self.plot.addItem(self.v_line, ignoreBounds=True)
        self.plot.addItem(self.h_line, ignoreBounds=True)

        # Clear stacked items
        self._stacked_vlines.clear()
        self._stacked_plots.clear()
        try:
            self.glw.clear()
        except Exception:
            pass

    # ── Internal: rebuild ─────────────────────────────────────────────────

    def _rebuild_curves(self, preserve_selection: bool = False) -> None:
        selected = self.selected_keys() if preserve_selection else []
        self._clear_rendered_items()

        if not self._items:
            self._refresh_table()
            self._update_empty_state_ui()
            return

        if self._stacked_mode:
            self.view_stack.setCurrentIndex(1)
            self._rebuild_stacked()
        else:
            self.view_stack.setCurrentIndex(0)
            self._rebuild_overlay()

        self._set_axis_label(self._current_key)
        self._refresh_table()
        self._update_empty_state_ui()
        if selected:
            self._restore_selection(selected)
        self._setup_mouse_proxy()

    def _rebuild_overlay(self) -> None:
        """Normal or multi-axis: all signals on one PlotWidget, extra axes to the left."""
        for idx, key in enumerate(self._items):
            plotted = self._items[key]

            if self._multi_axis and idx > 0:
                # ── BUG 1 FIX ──
                # Use PlotDataItem (not PlotCurveItem) so symbol kwargs work.
                # sigResized is connected below so geometry is maintained on resize.
                axis = pg.AxisItem('left')
                vb   = pg.ViewBox()
                self.plot.plotItem.scene().addItem(vb)
                self.plot.plotItem.scene().addItem(axis)
                axis.linkToView(vb)
                vb.setXLink(self.plot.plotItem.vb)
                curve = pg.PlotDataItem()       # <-- was PlotCurveItem
                vb.addItem(curve)
                plotted.curve     = curve
                plotted.axis      = axis
                plotted.view_box  = vb
                self._extra_axes.append((axis, vb))
            else:
                curve = self.plot.plot([], [], name=key)
                plotted.curve    = curve
                plotted.axis     = self.plot.getAxis('left')
                plotted.view_box = None

            self._apply_curve_style(plotted)
            try:
                self._legend.addItem(plotted.curve, key)
            except Exception:
                pass

        if self._extra_axes:
            # Connect once; disconnect happens in _clear_rendered_items
            self.plot.plotItem.vb.sigResized.connect(self._update_multi_axis_views)
            # Defer initial geometry until widget is painted
            QTimer.singleShot(10, self._update_multi_axis_views)

    def _rebuild_stacked(self) -> None:
        """
        Bug 4: INCA/CANdb-style stacked layout.
        Each signal occupies its own row.  All plots share the X axis.
        Only the bottom row shows X tick labels.
        Left axis of each row is labelled with signal name + unit.
        """
        order = list(self._items.keys())
        n = len(order)
        ref_plot: pg.PlotItem | None = None

        for idx, key in enumerate(order):
            plotted = self._items[key]
            series  = plotted.series

            p: pg.PlotItem = self.glw.addPlot(row=idx, col=0)
            p.showGrid(x=True, y=True, alpha=0.25)
            p.setMenuEnabled(False)

            # Left Y-axis label (signal name + unit)
            ylabel = series.signal_name
            if series.unit:
                ylabel += f'\n({series.unit})'
            p.setLabel('left', ylabel, color=plotted.color)
            p.getAxis('left').setTextPen(pg.mkPen(plotted.color))
            p.getAxis('left').setWidth(70)
            p.showAxis('right', False)
            p.showAxis('top',   False)

            # X axis: ticks only on bottom row
            if idx < n - 1:
                p.getAxis('bottom').setStyle(showValues=False)
                p.getAxis('bottom').setLabel('')
                p.getAxis('bottom').setHeight(0)
            else:
                p.setLabel('bottom', 'Time (seconds)')

            # Link all rows to the first (shared X panning/zoom)
            if ref_plot is None:
                ref_plot = p
            else:
                p.setXLink(ref_plot)

            curve = pg.PlotDataItem()
            p.addItem(curve)
            plotted.curve    = curve
            plotted.axis     = p.getAxis('left')
            plotted.view_box = p.vb

            self._apply_curve_style(plotted)

            # Per-row vertical cursor line
            vl = pg.InfiniteLine(angle=90, movable=False,
                                 pen=pg.mkPen(color='#888', width=1))
            p.addItem(vl, ignoreBounds=True)
            self._stacked_vlines.append(vl)
            self._stacked_plots.append(p)

    # ── Curve style ───────────────────────────────────────────────────────

    def _apply_curve_style(self, plotted: PlottedSignal) -> None:
        """
        Bug 2 fix: PlotDataItem.setData accepts all kwargs including symbol.
        This works identically for the main plot, extra ViewBoxes, and stacked rows.
        """
        if plotted.curve is None:
            return
        ts = np.asarray(plotted.series.timestamps, dtype=np.float64)
        vs = np.asarray(plotted.series.values,     dtype=np.float64)
        kwargs: dict = {
            'pen':     pg.mkPen(color=plotted.color, width=2.8),
            'connect': 'finite',
        }
        if self._show_points:
            kwargs.update({
                'symbol':     'o',
                'symbolSize':  5,
                'symbolBrush': plotted.color,
                'symbolPen':   pg.mkPen(color=plotted.color, width=1.2),
            })
        else:
            kwargs['symbol'] = None
        plotted.curve.setData(ts, vs, **kwargs)

    # ── Multi-axis geometry (called via sigResized) ───────────────────────

    def _update_multi_axis_views(self) -> None:
        """
        Bug 1 fix: position floating ViewBoxes + axes to the LEFT of main plot.
        Called on sigResized so geometry stays correct after window resize.
        """
        if not self._extra_axes:
            return
        rect = self.plot.plotItem.vb.sceneBoundingRect()
        if rect.width() < 10:                       # widget not yet painted
            QTimer.singleShot(20, self._update_multi_axis_views)
            return
        axis_width = 55
        for idx, (axis, vb) in enumerate(self._extra_axes, start=1):
            vb.setGeometry(rect)
            vb.linkedViewChanged(self.plot.plotItem.vb, vb.XAxis)
            x = rect.left() - axis_width * idx
            axis.setGeometry(QRectF(x, rect.top(), axis_width, rect.height()))

    # ── Mouse proxy management ────────────────────────────────────────────

    def _setup_mouse_proxy(self) -> None:
        if self._proxy is not None:
            try:
                self._proxy.disconnect()
            except Exception:
                pass
            self._proxy = None

        scene = (
            self.glw.scene()
            if (self._stacked_mode and self._stacked_plots)
            else self.plot.scene()
        )
        self._proxy = pg.SignalProxy(
            scene.sigMouseMoved, rateLimit=60, slot=self._mouse_moved
        )

    # ── Mouse cursor ──────────────────────────────────────────────────────

    def _mouse_moved(self, event: tuple) -> None:
        if not self._items:
            return
        pos = event[0]

        if self._stacked_mode:
            for i, p in enumerate(self._stacked_plots):
                if p.sceneBoundingRect().contains(pos):
                    mp = p.vb.mapSceneToView(pos)
                    x  = mp.x()
                    for vl in self._stacked_vlines:
                        vl.setPos(x)
                    self._update_table_values(x)
                    self.cursor_label.setText(f'Cursor t={x:.6f}')
                    return
        else:
            if not self.plot.sceneBoundingRect().contains(pos):
                return
            mp   = self.plot.plotItem.vb.mapSceneToView(pos)
            x, y = mp.x(), mp.y()
            self.v_line.setPos(x)
            self.h_line.setPos(y)
            self._update_table_values(x)
            self.cursor_label.setText(f'Cursor t={x:.6f}, y={y:.6f}')

    def _update_table_values(self, x: float) -> None:
        """Update Cursor Value column for ALL signals (Bug 2 scope fix)."""
        row_lookup: dict[str, int] = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                row_lookup[str(item.data(Qt.ItemDataRole.UserRole))] = row
        for key, plotted in self._items.items():
            idx = self._nearest_index(plotted.series.timestamps, x)
            if idx is None:
                continue
            value = plotted.series.raw_values[idx]
            row   = row_lookup.get(key)
            if row is not None:
                cell = self.table.item(row, 1)
                if cell is not None:
                    cell.setText(str(value))
        self.table.resizeColumnsToContents()

    # ── Fit to window ─────────────────────────────────────────────────────

    def fit_to_window(self) -> None:
        if not self._items:
            if not self._stacked_mode:
                self.plot.enableAutoRange()
                self.plot.autoRange()
            return

        all_ts = [ts for it in self._items.values() for ts in it.series.timestamps]
        if not all_ts:
            return
        x_min, x_max = min(all_ts), max(all_ts)
        if x_min == x_max:
            x_max += 1.0

        if self._stacked_mode:
            for i, (key, plotted) in enumerate(self._items.items()):
                if i >= len(self._stacked_plots):
                    break
                p = self._stacked_plots[i]
                p.setXRange(x_min, x_max, padding=0.02)
                vals = [v for v in plotted.series.values if v == v]
                if vals:
                    y_min, y_max = min(vals), max(vals)
                    pad = (y_max - y_min) * 0.05 if y_min != y_max else (1.0 if y_min == 0 else abs(y_min) * 0.05)
                    p.setYRange(y_min - pad, y_max + pad, padding=0)
        elif self._multi_axis:
            self.plot.setXRange(x_min, x_max, padding=0.02)
            for idx, (key, plotted) in enumerate(self._items.items()):
                vals = [v for v in plotted.series.values if v == v]
                if not vals:
                    continue
                y_min, y_max = min(vals), max(vals)
                pad = (y_max - y_min) * 0.05 if y_min != y_max else (1.0 if y_min == 0 else abs(y_min) * 0.05)
                target = self.plot.plotItem.vb if (idx == 0 or plotted.view_box is None) else plotted.view_box
                target.setYRange(y_min - pad, y_max + pad, padding=0)
            self._update_multi_axis_views()
        else:
            self.plot.setXRange(x_min, x_max, padding=0.02)
            numeric = [v for it in self._items.values() for v in it.series.values if v == v]
            if numeric:
                y_min, y_max = min(numeric), max(numeric)
                pad = (y_max - y_min) * 0.05 if y_min != y_max else (1.0 if y_min == 0 else abs(y_min) * 0.05)
                self.plot.setYRange(y_min - pad, y_max + pad, padding=0)

    # ── Color / background ────────────────────────────────────────────────

    def set_series_color(self, key: str, color: str) -> None:
        if key not in self._items:
            return
        self._items[key].color = color
        self._apply_curve_style(self._items[key])
        self._refresh_table()
        self._set_axis_label(self._current_key)
        self.signalColorChanged.emit(key, color)

    def series_colors(self) -> dict[str, str]:
        return {k: v.color for k, v in self._items.items()}

    def set_background_color(self, color: str) -> None:
        self._background_color = color
        self.plot.setBackground(color)
        self.glw.setBackground(color)
        self._apply_panel_background()
        self.backgroundColorChanged.emit(color)

    def background_color(self) -> str:
        return self._background_color

    # ── Overlay (empty state) ─────────────────────────────────────────────

    def set_status_overlay(self, state: str, next_step: str) -> None:
        if self._items:
            self.overlay_label.hide()
            return
        text = f"{state}\n{next_step}".strip()
        self.overlay_label.setText(text)
        self.overlay_label.setVisible(bool(text))

    def _update_empty_state_ui(self) -> None:
        has_items = bool(self._items)
        self.overlay_label.setVisible((not has_items) and bool(self.overlay_label.text()))
        self.drop_hint.setVisible(has_items)
        self.cursor_label.setVisible(has_items)
        if has_items and self._stacked_mode:
            self.view_stack.setCurrentIndex(1)
        else:
            self.view_stack.setCurrentIndex(0)

    # ── Axis label ────────────────────────────────────────────────────────

    def _set_axis_label(self, key: str | None) -> None:
        if self._stacked_mode:
            return   # each row already has its own label
        if not key or key not in self._items:
            self.plot.setLabel('left', 'Value')
            return
        series = self._items[key].series
        label  = series.signal_name + (f' ({series.unit})' if series.unit else '')
        self.plot.setLabel('left', label, color=self._items[key].color)
        self.plot.getAxis('left').setTextPen(pg.mkPen(self._items[key].color))
        if self._multi_axis:
            for axis_key in list(self._items.keys())[1:]:
                plotted = self._items[axis_key]
                if plotted.axis is not None and plotted.axis is not self.plot.getAxis('left'):
                    lbl = plotted.series.signal_name + (
                        f' ({plotted.series.unit})' if plotted.series.unit else ''
                    )
                    plotted.axis.setLabel(lbl, color=plotted.color)
                    plotted.axis.setTextPen(pg.mkPen(plotted.color))
                    plotted.axis.setWidth(55)

    # ── Table ─────────────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self._items))
        for row, (key, plotted) in enumerate(self._items.items()):
            signal_item  = QTableWidgetItem(key)
            signal_item.setData(Qt.ItemDataRole.UserRole, key)
            cursor_item  = QTableWidgetItem('')
            unit_item    = QTableWidgetItem(plotted.series.unit)
            samples_item = QTableWidgetItem(str(len(plotted.series.timestamps)))
            brush = QBrush(QColor(plotted.color))
            for item in (signal_item, cursor_item, unit_item, samples_item):
                item.setForeground(brush)
            self.table.setItem(row, 0, signal_item)
            self.table.setItem(row, 1, cursor_item)
            self.table.setItem(row, 2, unit_item)
            self.table.setItem(row, 3, samples_item)
        self.table.resizeColumnsToContents()

    def _emit_selection(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if not item:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            self._current_key = str(key)
            self._set_axis_label(self._current_key)
            self.selectionChanged.emit(str(key))

    # ── Series management ─────────────────────────────────────────────────

    def remove_series(self, key: str) -> None:
        if key not in self._items:
            return
        self._items.pop(key)
        if self._current_key == key:
            self._current_key = next(iter(self._items), None)
        self._rebuild_curves(preserve_selection=False)
        self._set_axis_label(self._current_key)
        self._update_empty_state_ui()
        self.fit_to_window()

    def remove_selected_series(self) -> None:
        for key in list(self.selected_keys()):
            self._items.pop(str(key), None)
        self._current_key = next(iter(self._items), None)
        self._rebuild_curves(preserve_selection=False)
        self._set_axis_label(self._current_key)
        self._update_empty_state_ui()
        self.fit_to_window()

    def clear_all(self) -> None:
        self._items.clear()
        self._clear_rendered_items()
        self.table.setRowCount(0)
        self._current_key = None
        self.plot.setLabel('left', 'Value')
        self.cursor_label.setText(self._cursor_label_base)
        self._update_empty_state_ui()
        self.plot.enableAutoRange()
        self.plot.autoRange()

    def move_selected_up(self)   -> None: self._move_selected(-1)
    def move_selected_down(self) -> None: self._move_selected(1)

    def _move_selected(self, direction: int) -> None:
        keys  = self.selected_keys()
        if not keys:
            return
        order = list(self._items.keys())
        if direction < 0:
            for key in keys:
                idx = order.index(key)
                if idx > 0 and order[idx - 1] not in keys:
                    order[idx - 1], order[idx] = order[idx], order[idx - 1]
        else:
            for key in reversed(keys):
                idx = order.index(key)
                if idx < len(order) - 1 and order[idx + 1] not in keys:
                    order[idx + 1], order[idx] = order[idx], order[idx + 1]
        self._items = {k: self._items[k] for k in order}
        self._rebuild_curves(preserve_selection=True)
        self._restore_selection(keys)

    def selected_keys(self) -> list[str]:
        keys: list[str] = []
        seen: set[str]  = set()
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), 0)
            if not item:
                continue
            key = item.data(Qt.ItemDataRole.UserRole)
            if key and str(key) not in seen:
                seen.add(str(key))
                keys.append(str(key))
        if not keys:
            row = self.table.currentRow()
            if row >= 0:
                item = self.table.item(row, 0)
                if item:
                    key = item.data(Qt.ItemDataRole.UserRole)
                    if key:
                        keys.append(str(key))
        return keys

    def plotted_series(self) -> list[SignalSeries]:
        return [item.series for item in self._items.values()]

    def plotted_keys(self) -> list[str]:
        return list(self._items.keys())

    def _restore_selection(self, keys: list[str]) -> None:
        self.table.clearSelection()
        key_set = set(keys)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) in key_set:
                self.table.selectRow(row)

    # ── Context menus ─────────────────────────────────────────────────────

    def _show_table_menu(self, position) -> None:
        selected_keys = self.selected_keys()
        row  = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        key  = item.data(Qt.ItemDataRole.UserRole) if item else None
        if key and str(key) not in selected_keys:
            selected_keys = [str(key)]
        if not selected_keys:
            return
        menu = QMenu(self.table)
        if len(selected_keys) == 1:
            act = QAction('Change signal color...', self.table)
            act.triggered.connect(lambda: self._choose_color_for_key(str(selected_keys[0])))
            menu.addAction(act)
        for label, slot in [
            ('Move selected up',   self.move_selected_up),
            ('Move selected down', self.move_selected_down),
        ]:
            a = QAction(label, self.table); a.triggered.connect(slot); menu.addAction(a)
        rm_label = ('Remove selected signals' if len(selected_keys) > 1
                    else 'Remove selected signal')
        rm = QAction(rm_label, self.table)
        rm.triggered.connect(self.remove_selected_series)
        menu.addAction(rm)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _install_plot_background_menu(self) -> None:
        pi   = getattr(self.plot, 'plotItem', None)
        menu = getattr(pi, 'ctrlMenu', None)
        if menu is not None:
            menu.addSeparator()
            act = QAction('Set Plot Background Color...', menu)
            act.triggered.connect(self._choose_plot_background_color)
            menu.addAction(act)
        else:
            self.plot.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.plot.customContextMenuRequested.connect(self._show_plot_menu)

    def _choose_color_for_key(self, key: str) -> None:
        if key not in self._items:
            return
        chosen = QColorDialog.getColor(QColor(self._items[key].color), self, 'Choose signal color')
        if chosen.isValid():
            self.set_series_color(key, chosen.name())

    def _choose_plot_background_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._background_color), self, 'Choose plot background color')
        if chosen.isValid():
            self.set_background_color(chosen.name())

    def _show_plot_menu(self, position) -> None:
        menu = QMenu(self.plot)
        act  = QAction('Set Plot Background Color...', self.plot)
        act.triggered.connect(self._choose_plot_background_color)
        menu.addAction(act)
        menu.exec(self.plot.mapToGlobal(position))

    def _apply_panel_background(self) -> None:
        bg = self._background_color
        self.table_panel.setStyleSheet(f'''
            QWidget {{ background-color: {bg}; }}
            QLabel  {{ background-color: {bg}; color: white; }}
            QTableWidget {{
                background-color: {bg};
                alternate-background-color: {bg};
                gridline-color: #333333;
                color: white;
                selection-background-color: #2d4f7c;
            }}
            QHeaderView::section {{
                background-color: {bg}; color: white; border: 1px solid #333333;
            }}
        ''')

    # ── Nearest-sample lookup ─────────────────────────────────────────────

    @staticmethod
    def _nearest_index(values, target: float) -> int | None:
        if not len(values):
            return None
        arr  = np.asarray(values, dtype=np.float64)
        lo, hi = 0, len(arr) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid] < target:
                lo = mid + 1
            else:
                hi = mid
        if lo == 0:
            return 0
        before = lo - 1
        return lo if abs(arr[lo] - target) < abs(arr[before] - target) else before
