# ******************************************************************************
#  * @file    HSDPlotToFWidget.py
#  * @author  SRA
# ******************************************************************************
# * @attention
# *
# * Copyright (c) 2022 STMicroelectronics.
# * All rights reserved.
# *
# * This software is licensed under terms that can be found in the LICENSE file
# * in the root directory of this software component.
# * If no LICENSE file comes with this software, it is provided AS-IS.
# *
# *
# ******************************************************************************
#
"""
Time-of-Flight (ToF) heatmap plotting widget for HSD GUI.

This module defines `HSDPlotToFWidget`, a specialized plot widget that renders ToF sensor
outputs as heatmaps. It currently draws a single target heatmap ("Target 1") and supports
all VL53L9 resolution enums through a shared resolution-to-shape mapping.

Highlights
----------
- Clears base plot visuals while preserving base class wiring and signals.
- Configures a `PlotHeatmapWidget` with default rotation and compact layout.
- Supports dynamic update of heatmap characteristics when plot parameters change.
- Parses incoming data according to an optional `output_format` mapping where `target_status` is optional.
- Falls back to fixed legacy indexing only when a format is not provided.
"""

from PySide6.QtCore import QEvent, Qt, Slot
from PySide6.QtGui import QScreen
from collections import deque
import operator
import sys

from PySide6.QtWidgets import QApplication, QBoxLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedLayout, QTabWidget, QVBoxLayout
import numpy as np

import stdatalog_core.HSD_utils.logger as logger
from stdatalog_core.HSD.output_format import (
    OutputFormatDecoder,
    VL53L9_RAW_DATA_DISCLAIMER,
    get_compiled,
)
from stdatalog_gui.Utils.PlotParams import PlotParams
from stdatalog_gui.Widgets.Plots.PlotHeatmapWidget import PlotHeatmapWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import CustomPGPlotWidget, PlotLabel, PlotWidget

log = logger.get_logger(__name__)

MAX_DETAIL_COLS = 8
MAX_DETAIL_ROWS = 8

class HistogramFrame(QFrame):
    def __init__(self, owner):
        super().__init__(owner)
        self.icon_pop_in = owner.icon_pop_in
        self.icon_pop_out = owner.icon_pop_out
        self.is_docked = True

    def toggle_pop_out(self):
        if self.is_docked:
            self._dock_parent = self.parentWidget()
            self._dock_layout = self._dock_parent.layout()
            self._dock_index = self._dock_layout.indexOf(self)
            if isinstance(self._dock_layout, QGridLayout):
                self._dock_grid_position = self._dock_layout.getItemPosition(self._dock_index)
            self.pop_out_button.setIcon(self.icon_pop_in)
            self.pop_out_button.setToolTip("Pop in")
            self.setWindowFlags(Qt.Dialog | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
            geometry = self.frameGeometry()
            geometry.moveCenter(QScreen.availableGeometry(QApplication.primaryScreen()).center())
            self.move(geometry.topLeft())
            self.show()
        else:
            self.pop_out_button.setIcon(self.icon_pop_out)
            self.pop_out_button.setToolTip("Pop out")
            self.setParent(self._dock_parent, Qt.Widget)
            if self._dock_layout.indexOf(self) < 0:
                if isinstance(self._dock_layout, QGridLayout):
                    self._dock_layout.addWidget(self, *self._dock_grid_position)
                elif isinstance(self._dock_layout, (QBoxLayout, QStackedLayout)):
                    self._dock_layout.insertWidget(self._dock_index, self)
                else:
                    self._dock_layout.addWidget(self)
            self.show()
        self.is_docked = not self.is_docked

    def closeEvent(self, event):
        if not self.is_docked:
            self.toggle_pop_out()
            event.ignore()
            return
        super().closeEvent(event)

class HSDPlotToFWidget(PlotWidget):
    """
    Plot widget for ToF heatmaps (single target display).

    Parameters
    ----------
    controller : object
        Application controller used by the base `PlotWidget`.
    comp_name : str
        Component name (unique identifier for the plot source).
    comp_display_name : str
        Human-friendly display name for the plot.
    plot_params : PlotParams
        Plot configuration, including ToF grid `resolution` and `output_format` mapping.
    p_id : int, optional
        Plot identifier used by the base class, by default 0.
    parent : QWidget | None, optional
        Parent widget, by default `None`.

    Notes
    -----
    The widget creates a single `PlotHeatmapWidget` (Target 1) and hides the internal
    title frame for a tighter UI. A placeholder for a second target is kept as commented
    code for future extension.
    """

    DISTANCE_VALUE_MASK = 0x7FFF

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        plot_params,
        p_id=0,
        parent=None,
    ):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent)
        self.active_tags = dict()
        self.plot_params = plot_params
        self.output_format = self.plot_params.output_format
        self.heatmaps = {}

        # Clear PlotWidget-inherited frames, preserving attributes, functions, and signals.
        for i in reversed(range(self.layout().count())):
            self.contents_frame.layout().itemAt(i).widget().setParent(None)

        self.heatmaps_shape = self.__heatmap_shape_from_resolution_string(plot_params.resolution)
        self.decoder = self.__schema_decoder() if isinstance(self.output_format, str) else None

        # Create Target 1 heatmap with default rotation, compact header hidden.
        self.t1_out = PlotHeatmapWidget(
            controller,
            comp_name,
            comp_display_name,
            self.heatmaps_shape,
            plot_label="Target 1",
            p_id=p_id,
            parent=self,
            compact_controls=self.decoder is not None,
            legacy_validity_mask=isinstance(self.output_format, dict),
        )
        self.t1_out.set_detail_mode(
            self.heatmaps_shape[0] <= MAX_DETAIL_ROWS and self.heatmaps_shape[1] <= MAX_DETAIL_COLS
        )
        self.t1_out.set_default_rotation(2)
        self.t1_out.title_frame.setVisible(False)
        # self.t2_out = PlotHeatmapWidget(
        #   controller, comp_name, comp_display_name,
        #   heatmaps_shape, plot_label= "Target 2",
        #   p_id = p_id, parent=self
        # )
        self.heatmaps["target1"] = self.t1_out
        # self.heatmaps["target2"] = self.t2_out
        self.t1_out.setMinimumWidth(540)

        heatmaps_frame = QFrame()
        wdg_layout = QHBoxLayout()
        wdg_layout.addWidget(self.t1_out)
        # wdg_layout.addWidget(self.t2_out)
        heatmaps_frame.setLayout(wdg_layout)
        self.contents_frame.layout().addWidget(heatmaps_frame)
        self._schema_views = {}
        self._history = {}
        if self.decoder is not None:
            self._build_schema_views(heatmaps_frame)

    def _build_schema_views(self, first_heatmap):
        first_heatmap.setParent(None)
        for index in reversed(range(self.contents_frame.layout().count())):
            item = self.contents_frame.layout().takeAt(index)
            if item.widget() is not first_heatmap:
                item.widget().setParent(None)
        self._schema_views.clear()
        self._history.clear()
        self._schema_curves = {}
        if self.output_format == "schema_vl53l9_v1":
            disclaimer_container = QFrame(self)
            disclaimer_layout = QHBoxLayout(disclaimer_container)
            disclaimer_layout.setContentsMargins(8, 8, 8, 8)
            disclaimer = QLabel(VL53L9_RAW_DATA_DISCLAIMER, disclaimer_container)
            disclaimer.setObjectName("vl53l9_raw_data_disclaimer")
            disclaimer.setWordWrap(True)
            disclaimer.setStyleSheet(
                "QLabel { background: #3b321d; color: #f4d58d; border: 1px solid #8a6d2f; "
                "border-radius: 4px; padding: 8px; font-weight: 600; }"
            )
            disclaimer_layout.addWidget(disclaimer)
            self.contents_frame.layout().addWidget(disclaimer_container)
        containers = {}
        first = True
        for leaf in self.decoder.compiled.leaves:
            for mode in leaf.visualization:
                if mode.value == "hidden":
                    continue
                key = (leaf.path, mode.value)
                if mode.value == "heatmap":
                    if first:
                        view = self.t1_out
                        container = first_heatmap
                        first = False
                    else:
                        view = PlotHeatmapWidget(
                            self.controller, self.comp_name, self.comp_display_name,
                            self.heatmaps_shape, plot_label=leaf.path, p_id=self.p_id, parent=self,
                            compact_controls=True,
                        )
                        view.set_detail_mode(
                            self.heatmaps_shape[0] <= MAX_DETAIL_ROWS and self.heatmaps_shape[1] <= MAX_DETAIL_COLS
                        )
                        view.set_default_rotation(2)
                        container = QFrame(self)
                        container_layout = QHBoxLayout(container)
                        container_layout.setContentsMargins(0, 0, 0, 0)
                        view.layout().setContentsMargins(0, 9, 0, 0)
                        container_layout.addWidget(view)
                    title = leaf.path.replace("_", " ").replace(".", " / ").title()
                    if leaf.unit:
                        title += f" ({leaf.unit})"
                    view.title_frame.setVisible(True)
                    title_label = view.title_frame.findChild(PlotLabel)
                    title_label.p_label = title
                    title_label.update()
                    view.graph_widget.setLabel("bottom", "")
                    if leaf.role != "distance":
                        view.heatmap_levels = None
                elif mode.value in ("line", "histogram"):
                    view = CustomPGPlotWidget(self)
                    view.setLabel("left", leaf.path)
                    view.setBackground("#1b1d23")
                    view.showGrid(x=True, y=True)
                    view.getPlotItem().setMenuEnabled(False)
                    view.getAxis("left").setWidth(60)
                    container = view
                    if mode.value == "line":
                        container = QFrame(self)
                        container.setObjectName("schema_line_frame")
                        container.setStyleSheet(
                            "#schema_line_frame { background: rgb(41, 45, 56); border-radius: 5px; }"
                        )
                        line_layout = QHBoxLayout(container)
                        line_layout.setContentsMargins(0, 0, 0, 0)
                        line_layout.setSpacing(0)
                        title_frame = QFrame(container)
                        title_frame.setFixedWidth(43)
                        title_frame.setStyleSheet("background: rgb(39, 44, 54);")
                        title_layout = QVBoxLayout(title_frame)
                        title_layout.setContentsMargins(4, 6, 8, 6)
                        title = leaf.path.replace("_", " ").replace(".", " / ").title()
                        if leaf.unit:
                            title += f" ({leaf.unit})"
                        title_label = PlotLabel(title, title_frame)
                        title_label.setMinimumWidth(18)
                        title_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignHCenter)
                        plot_frame = QFrame(container)
                        plot_frame.setObjectName("schema_line_plot_frame")
                        plot_frame.setStyleSheet(
                            "#schema_line_plot_frame { border: 2px solid rgb(27, 29, 35); "
                            "border-radius: 5px; }"
                        )
                        plot_layout = QHBoxLayout(plot_frame)
                        plot_layout.setContentsMargins(9, 9, 9, 9)
                        plot_layout.addWidget(view)
                        line_layout.addWidget(title_frame)
                        line_layout.addWidget(plot_frame, 1)
                        view.setLabel("left", "")
                        self._history[key] = deque(maxlen=300)
                        self._schema_curves[key] = view.plot(pen={"color": "#e6007e", "width": 1})
                    else:
                        container = HistogramFrame(self)
                        container.setObjectName("schema_histogram_frame")
                        container.setStyleSheet(
                            "#schema_histogram_frame { background: rgb(41, 45, 56); border-radius: 5px; }"
                        )
                        histogram_layout = QHBoxLayout(container)
                        histogram_layout.setContentsMargins(6, 0, 6, 0)
                        histogram_layout.setSpacing(0)
                        title_frame = QFrame(container)
                        title_frame.setFixedWidth(41)
                        title_frame.setStyleSheet("background: rgb(39, 44, 54);")
                        title_layout = QVBoxLayout(title_frame)
                        title_layout.setContentsMargins(4, 6, 8, 6)
                        title_layout.setSpacing(6)
                        title = leaf.path.replace("_", " ").replace(".", " / ").title()
                        title = f"{title} Histogram" + (f" ({leaf.unit})" if leaf.unit else "")
                        container.pop_out_button = QPushButton(title_frame)
                        container.pop_out_button.setFixedSize(18, 18)
                        container.pop_out_button.setIcon(container.icon_pop_out)
                        container.pop_out_button.setToolTip("Pop out")
                        container.pop_out_button.clicked.connect(container.toggle_pop_out)
                        title_layout.addWidget(
                            container.pop_out_button, 0, Qt.AlignmentFlag.AlignHCenter
                        )
                        title_label = PlotLabel(title, title_frame)
                        title_label.setMinimumWidth(18)
                        title_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignHCenter)
                        plot_frame = QFrame(container)
                        plot_frame.setObjectName("schema_histogram_plot_frame")
                        plot_frame.setStyleSheet(
                            "#schema_histogram_plot_frame { border: 2px solid rgb(27, 29, 35); "
                            "border-radius: 5px; }"
                        )
                        plot_layout = QHBoxLayout(plot_frame)
                        plot_layout.setContentsMargins(32, 12, 32, 12)
                        plot_layout.addWidget(view)
                        histogram_layout.addWidget(title_frame)
                        histogram_layout.addWidget(plot_frame, 1)
                        view.setLabel("left", "")
                else:
                    view = QLabel(self)
                    view.setWordWrap(True)
                    container = view
                self._schema_views[key] = view
                containers[key] = container
        layout = self.decoder.compiled.layout
        if layout is None:
            tabs = QTabWidget(self)
            tabs.setUsesScrollButtons(True)
            for key, container in containers.items():
                tabs.addTab(container, f"{key[0]}: {key[1]}")
            self.contents_frame.layout().addWidget(tabs)
            return
        used = set()
        main_grid = self._schema_grid(layout.rows, containers, used)
        self._schema_main_grid = main_grid
        self._schema_main_height = 0
        self._schema_groups = []
        main_grid.installEventFilter(self)
        self.contents_frame.layout().addWidget(main_grid, 1)
        for section in layout.sections:
            group = QGroupBox(section.label, self)
            group.setCheckable(True)
            group.setChecked(section.expanded)
            self._schema_groups.append(group)
            group_layout = QVBoxLayout(group)
            group_layout.addWidget(self._schema_grid(section.rows, containers, used, section.row_height))
            values = QFrame(group)
            values_layout = QGridLayout(values)
            values_layout.setContentsMargins(4, 4, 4, 4)
            values_layout.setSpacing(8)
            value_count = 0
            for path in section.paths:
                for key, container in containers.items():
                    if key not in used and (key[0] == path or key[0].startswith(f"{path}.")):
                        name = key[0].removeprefix(f"{section.label.lower().replace(' ', '_')}.")
                        field = QFrame(values)
                        field.setStyleSheet("QFrame { background: #272c36; border-radius: 4px; }")
                        field_layout = QVBoxLayout(field)
                        field_layout.setContentsMargins(9, 5, 9, 5)
                        field_layout.setSpacing(2)
                        heading = QLabel(name.replace("_", " ").replace(".", " / ").title(), field)
                        heading.setWordWrap(True)
                        heading.setStyleSheet("color: #aebbc6; font-size: 11px;")
                        field_layout.addWidget(heading)
                        container.setProperty("schema_value", True)
                        container.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 600;")
                        field_layout.addWidget(container)
                        values_layout.addWidget(field, value_count // 3, value_count % 3)
                        value_count += 1
                        used.add(key)
            if value_count:
                scroller = QScrollArea(group)
                scroller.setWidgetResizable(True)
                scroller.setFrameShape(QFrame.Shape.NoFrame)
                scroller.setMinimumHeight(180)
                scroller.setMaximumHeight(260)
                scroller.setWidget(values)
                group_layout.addWidget(scroller)
            group.toggled.connect(lambda checked, widgets=tuple(
                group_layout.itemAt(index).widget() for index in range(group_layout.count())
            ): [widget.setVisible(checked) for widget in widgets])
            group.toggled.connect(lambda checked, grid=main_grid: grid.setMinimumHeight(self._schema_main_height if checked else 0))
            for index in range(group_layout.count()):
                group_layout.itemAt(index).widget().setVisible(section.expanded)
            self.contents_frame.layout().addWidget(group)
        for key, container in containers.items():
            if key not in used:
                self.contents_frame.layout().addWidget(container)

    def eventFilter(self, watched, event):
        if (watched is getattr(self, "_schema_main_grid", None)
                and event.type() == QEvent.Type.Resize
                and not any(group.isChecked() for group in self._schema_groups)):
            self._schema_main_height = event.size().height()
        return super().eventFilter(watched, event)

    def _schema_grid(self, rows, containers, used, row_height=0):
        grid_frame = QFrame(self)
        grid = QGridLayout(grid_frame)
        column_count = max((column.column + column.span for row in rows for column in row.columns), default=0)
        for index in range(column_count):
            stretch = 11 if self.output_format == "schema_vl53l9_v1" and column_count == 3 and index == 2 else 10
            grid.setColumnStretch(index, stretch)
        for row in rows:
            if row_height:
                grid.setRowMinimumHeight(row.row, row_height)
            for column in row.columns:
                options = []
                for path in column.resolved_paths:
                    leaf_path, separator, mode = path.partition(":")
                    key = next((key for key in containers if key[0] == leaf_path and (not separator or key[1] == mode)), None)
                    if key is not None:
                        options.append(key)
                        used.add(key)
                if not options:
                    continue
                cell = QFrame(grid_frame)
                cell_layout = QVBoxLayout(cell)
                if self.output_format == "schema_vl53l9_v1" and column_count == 3 and column.column == 2:
                    cell_layout.setContentsMargins(4, 9, 4, 9)
                if len(options) > 1:
                    selector = QTabWidget(cell)
                    for key in options:
                        label = key[0].replace("_", " ").replace(".", " / ").title()
                        selector.addTab(containers[key], label)
                    cell_layout.addWidget(selector)
                else:
                    cell_layout.addWidget(containers[options[0]])
                    if row_height and options[0][1] == "line":
                        self._schema_views[options[0]].setMinimumHeight(row_height)
                span = column_count - column.column if len(row.columns) == 1 and row_height else column.span
                grid.addWidget(cell, row.row, column.column, column.row_span, span)
        return grid_frame

    def _update_schema_views(self, decoded):
        comparisons = {"eq": operator.eq, "ne": operator.ne, "lt": operator.lt,
                       "lte": operator.le, "gt": operator.gt, "gte": operator.ge}
        for leaf in self.decoder.compiled.leaves:
            values = np.asarray(decoded[leaf.path])
            if leaf.validity is not None:
                valid = comparisons[leaf.validity.op](np.asarray(decoded[leaf.validity.ref]), leaf.validity.value)
                values = np.where(valid, values, 0)
            for mode in leaf.visualization:
                key = (leaf.path, mode.value)
                view = self._schema_views.get(key)
                if view is None:
                    continue
                if mode.value == "heatmap":
                    view._data.clear()
                    view.add_data(values)
                    view.update_plot()
                elif mode.value == "histogram":
                    counts, edges = np.histogram(values, bins=32)
                    view.clear()
                    view.plot(edges[:-1], counts, stepMode="left", fillLevel=0)
                elif mode.value == "line":
                    self._history[key].append(values.item())
                    self._schema_curves[key].setData(list(self._history[key]))
                else:
                    view.setText(str(values.tolist()) if view.property("schema_value") else f"{leaf.path}: {values.tolist()}")
                if mode.value in ("histogram", "line") and sys.platform == 'darwin' and QApplication.platformName() == 'cocoa':
                    view.viewport().update()

    @staticmethod
    def _resize_heatmap(view, shape):
        detail_mode = shape[0] <= MAX_DETAIL_ROWS and shape[1] <= MAX_DETAIL_COLS
        if not detail_mode and view.full_detail_mode:
            view.set_detail_mode(False)
        view.update_plot_characteristics(shape)
        if detail_mode and not view.full_detail_mode:
            view.set_detail_mode(True)

    @Slot(bool, int)  # Override PlotLinesWavWidget s_is_logging
    def s_is_logging(self, status: bool, interface: int):
        """
        React to logging start/stop while preserving base-class behavior.

        Parameters
        ----------
        status : bool
            True if logging is starting, False if stopping.
        interface : int
            Link/interface index. If equal to 1, prints a USB logging message.
        """
        if interface == 1:
            print(f"Sensor {self.comp_name} is logging via USB: {status}")
        super().s_is_logging(status, interface)

    def update_plot_characteristics(self, plot_params: PlotParams):
        """
        Update heatmap resolution and internal configuration.

        Parameters
        ----------
        plot_params : PlotParams
            New plotting parameters; `resolution` selects the output matrix shape and may
            carry an updated `output_format` mapping.
        """
        heatmaps_shape = self.__heatmap_shape_from_resolution_string(plot_params.resolution)
        if heatmaps_shape == self.heatmaps_shape and plot_params.output_format == self.output_format:
            if self.decoder is not None and self.decoder.payload_size_bytes != plot_params.dimension:
                raise ValueError(
                    f"{self.output_format} expects {self.decoder.payload_size_bytes} bytes, "
                    f"device declares {plot_params.dimension}"
                )
            self.plot_params = plot_params
            return
        decoder = self.__schema_decoder(plot_params, heatmaps_shape) if isinstance(plot_params.output_format, str) else None
        if decoder is not None and self.decoder is not None and plot_params.output_format == self.output_format:
            for key, view in self._schema_views.items():
                if isinstance(view, PlotHeatmapWidget):
                    self._resize_heatmap(view, heatmaps_shape)
                elif key[1] == "line":
                    self._schema_curves[key].setData([], [])
                elif key[1] == "histogram":
                    view.clear()
                if isinstance(view, CustomPGPlotWidget) and sys.platform == 'darwin' and QApplication.platformName() == 'cocoa':
                    view.viewport().update()
            self.heatmaps_shape = heatmaps_shape
            self.plot_params = plot_params
            self.decoder = decoder
            for history in self._history.values():
                history.clear()
            return
        self.t1_out.legacy_validity_mask = isinstance(plot_params.output_format, dict)
        self._resize_heatmap(self.t1_out, heatmaps_shape)
        self.heatmaps_shape = heatmaps_shape
        # self.t2_out.update_plot_characteristics(heatmaps_shape)
        self.plot_params = plot_params
        self.output_format = self.plot_params.output_format
        self.decoder = decoder
        if self.decoder is not None:
            self._build_schema_views(self.t1_out.parentWidget())
        elif self._schema_views:
            self.t1_out.setParent(None)
            for index in reversed(range(self.contents_frame.layout().count())):
                self.contents_frame.layout().takeAt(index).widget().setParent(None)
            frame = QFrame(self)
            QHBoxLayout(frame).addWidget(self.t1_out)
            self.contents_frame.layout().addWidget(frame)
            self._schema_views.clear()
            self._history.clear()

    def add_data(self, data):
        """
        Parse ToF data and forward target heatmap values to the child widget.

        Parameters
        ----------
        data : Sequence
            Iterable with channel data; expects `data[0]` to be a flat numeric array.

        Notes
        -----
        - When `self.output_format` is available, it uses:
            - `target_distance.start_id`
            - `nof_outputs` (stride)
            - `target_status.start_id` (optional)
        - When `self.output_format` is a string, it interprets the format according to
            a mapped output format description file. e.g. if self.output_format is "schema_vl53l9_v1",
            it will look for "schema_vl53l9_v1.json" to interpret the data.
        - Otherwise, defaults to an 8-value stride with distance at index 4 and status
            at index 3 relative to the stride.
        """
        if data is None or len(data) == 0:
            return

        # Old legacy handling for dictionary-based output_format
        if isinstance(self.output_format, dict):
            if self.output_format:
                target_distance = self.output_format.get("target_distance")
                if not isinstance(target_distance, dict):
                    log.warning("Invalid ToF output_format: missing target_distance object")
                    return

                start_t1_dist_id = target_distance.get("start_id")
                out_data_step = self.output_format.get("nof_outputs")
                if (
                    start_t1_dist_id is None
                    or out_data_step is None
                    or not isinstance(out_data_step, int)
                    or out_data_step <= 0
                ):
                    log.warning(
                        "Invalid ToF output_format metadata: start_id=%s, nof_outputs=%s",
                        start_t1_dist_id,
                        out_data_step,
                    )
                    return

                t1_data = (
                    np.asarray(data[0][start_t1_dist_id::out_data_step])
                    & self.DISTANCE_VALUE_MASK
                )

                target_status = self.output_format.get("target_status")
                if isinstance(target_status, dict):
                    start_t1_status_id = target_status.get("start_id")
                    if start_t1_status_id is not None:
                        t1_status_mask = data[0][start_t1_status_id::out_data_step]
                        self.heatmaps["target1"].add_data((t1_data, t1_status_mask))
                        return

                self.heatmaps["target1"].add_data((t1_data,))
                return

            start_t1_dist_id = 4
            # Extract target matrices with fixed stride
            t1_data = (
                np.asarray(data[0][start_t1_dist_id::8]) & self.DISTANCE_VALUE_MASK
            )
            t1_status_mask = data[0][start_t1_dist_id - 1::8]
            # #NOTE! Demo Sensor converge
            # start_t1_dist_id = 1
            # #extract targets matrices
            # t1_data = data[0][start_t1_dist_id::2]
            # t1_status_mask = data[0][start_t1_dist_id-1::2]
            # Forward parsed data to the Target 1 heatmap
            self.heatmaps["target1"].add_data((t1_data, t1_status_mask))

        # Structured string mapped output_format handling.
        else:
            if self.output_format is None or not isinstance(self.output_format, str):
                log.warning(
                    "Invalid structured string ToF output_format: %s", self.output_format
                )
                return
            else:
                payload = (
                    bytes(data[0]) if isinstance(data[0], (bytes, bytearray, memoryview))
                    else np.asarray(data[0], dtype=np.uint8).tobytes()
                )
                size = self.decoder.payload_size_bytes
                if len(payload) % size:
                    log.warning("Discarded incomplete ToF update: %s bytes (sample size %s)", len(payload), size)
                    return
                for offset in range(0, len(payload), size):
                    decoded = self.decoder.decode(payload[offset:offset + size])
                    self._latest_schema_sample = decoded
                    self._update_schema_views(decoded)

    def __schema_decoder(self, plot_params=None, heatmaps_shape=None):
        plot_params = plot_params or self.plot_params
        heatmaps_shape = heatmaps_shape or self.heatmaps_shape
        if heatmaps_shape is None:
            raise ValueError("Schema-backed ToF requires a resolution label")
        compiled = get_compiled(plot_params.output_format, heatmaps_shape)
        if compiled.payload_size_bytes != plot_params.dimension:
            raise ValueError(
                f"{plot_params.output_format} expects {compiled.payload_size_bytes} bytes, "
                f"device declares {plot_params.dimension}"
            )
        return OutputFormatDecoder(compiled)

    def __heatmap_shape_from_resolution_string(self, resolution_string):
        if not resolution_string:
            return None
        cols, rows = map(int, resolution_string.split('x'))
        return rows, cols
