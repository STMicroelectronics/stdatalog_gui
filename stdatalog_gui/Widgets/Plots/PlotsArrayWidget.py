#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    PlotsArrayWidget.py
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
"""
Container for arranging multiple plot widgets with optional horizontal/vertical layout.

This module provides `PlotsArrayWidget`, a composite widget that organizes multiple plot
types into a single view. It loads UI fragments via `QUiLoader`, renders a title with a
pop-out button, and creates sub-plot widgets (`AnalogGaugeWidget`, `LabelPlotWidget`,
`LevelPlotWidget`, `PlotLinesWidget`, or `CheckBoxListWidget`) based on PlotParams
definitions supplied at construction time.

Data Routing:
- For components tagged `slow_mc`, incoming data is delivered to enabled subplots in
    order.
- For `fast_mc`, the first element of the incoming data is strided by the number of
    enabled telemetries and dispatched to each enabled subplot.
"""

from collections import deque
import os

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
    QListWidget,
    QListView,
    QListWidgetItem,
    QAbstractItemView,
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui
from stdatalog_gui.Widgets.Plots.AnalogGaugeWidget import AnalogGaugeWidget
from stdatalog_gui.Widgets.Plots.LabelPlotWidget import LabelPlotWidget
from stdatalog_gui.Widgets.Plots.LevelPlotWidget import LevelPlotWidget
from stdatalog_gui.Widgets.Plots.PlotLinesWidget import PlotLinesWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget, PlotLabel
from stdatalog_gui.Utils.PlotParams import PlotLabelParams, PlotLevelParams, \
    PlotGaugeParams, PlotCheckBoxParams, LinesPlotParams
from stdatalog_gui.Widgets.Plots.CheckBoxListWidget import CheckBoxListWidget

class PlotsArrayWidget(PlotWidget):
    """Composite plot container that builds and arranges multiple sub-plots.

    Parameters
    ----------
    controller : QObject
        Controller used by the base class for timing and signals.
    comp_name : str
        Component identifier associated with this plot group.
    comp_display_name : str
        Human-readable name used in the title.
    out_plots : dict[str, PlotParams]
        Mapping from sub-plot name to its plot parameter object. The parameter type
        determines which sub-plot class is instantiated.
    p_id : int, optional
        Plot identifier for the base class. Default is 0.
    parent : QWidget | None, optional
        Parent widget.
    left_label : str | None, optional
        Label for the x-axis passed to the base class.
    orientation : str, optional
        'h' for horizontal arrangement, otherwise vertical. Default is 'h'.

    Attributes
    ----------
    out_plots_widget : dict[str, QWidget]
        Mapping from sub-plot name to the instantiated sub-plot widget.
    timer_interval_ms : int
        Timer period in milliseconds derived from the base timer interval.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        out_plots,
        p_id=0,
        parent=None,
        left_label=None,
        orientation="h",
    ):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, left_label)

        self.orientation = orientation
        # Clear PlotWidget inherited graphic elements
        # (mantaining all attributes, functions and signals)
        for i in reversed(range(self.layout().count())):
            self.layout().itemAt(i).widget().setParent(None)

        self._data = dict()  # dict of queues
        self._data[0] = deque(maxlen=200000)

        self.out_plots = out_plots
        self.out_plots_widget = {}

        # New Customized Graphic layout
        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            PlotsArrayWidget, module="PlotsArrayWidget"
        )
        self.loader = QUiLoader()
        self.plot_widget = self.loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "plots_array_output.ui",
            ),
            parent,
        )
        self.title_frame = self.plot_widget.findChild(QFrame, "frame_title")
        contents_frame = self.plot_widget.findChild(QFrame, "frame_contents")

        if self.orientation == "h":
            # self.sub_plot_list = FlowContainer(self)
            self.sub_plot_list = QHBoxLayout(self)
            contents_frame.setLayout(self.sub_plot_list)
            # contents_frame.layout().addWidget(self.sub_plot_list)
        else:
            self.sub_plot_list = QVBoxLayout(self)
            contents_frame.setLayout(self.sub_plot_list)

        pushButton_pop_out = self.title_frame.findChild(
            QPushButton, "pushButton_pop_out"
        )
        pushButton_pop_out.clicked.connect(self.clicked_pop_out_button)

        title_label = PlotLabel(f"{self.comp_display_name}")
        title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.title_frame.layout().addWidget(title_label)

        sp_id = 0
        for pw in self.out_plots:
            sub_plot = SubPlotFrame(pw, sp_id, self)
            contents_frame.layout().addWidget(sub_plot)
            sp_id += 1
        self.timer_interval_ms = self.timer_interval * 700
        self.layout().addWidget(self.plot_widget)

    @Slot(bool)
    def s_is_detecting(self, status: bool):
        """Start/stop updates for all subplots when detection toggles.

        Parameters
        ----------
        status : bool
            True to start periodic updates; False to stop.
        """
        if status:
            self.buffering_timer_counter = 0
            self.timer.start(self.timer_interval_ms)
        else:
            self.timer.stop()

    def add_data(self, data):
        """Route incoming data to enabled subplots, respecting component type.

        Parameters
        ----------
        data : Sequence
            For `slow_mc`, a flat sequence with one entry per enabled sub-plot.
            For `fast_mc`, a tuple/list whose first element contains a sequence of
            samples for all enabled telemetries that will be strided and dispatched.
        """
        if "slow_mc" in self.comp_name:
            data_idx = 0
            for p_id in range(len(self.out_plots)):
                if self.out_plots[list(self.out_plots.keys())[p_id]].enabled:
                    sub_plot = self.out_plots_widget[list(self.out_plots.keys())[p_id]]
                    sub_plot.add_data(data[data_idx])
                    data_idx = data_idx + 1

        elif "fast_mc" in self.comp_name:
            enabled_cnt = 0
            for p_id in range(len(self.out_plots)):
                if self.out_plots[list(self.out_plots.keys())[p_id]].enabled:
                    enabled_cnt = enabled_cnt + 1

            current_enabled_tele = 0
            for p_id in range(len(self.out_plots)):
                if self.out_plots[list(self.out_plots.keys())[p_id]].enabled:
                    sub_plot = self.out_plots_widget[list(self.out_plots.keys())[p_id]]
                    sub_plot.add_data(data[0][current_enabled_tele::enabled_cnt])
                    current_enabled_tele = current_enabled_tele + 1

    def update_plot_characteristics(self, plot_params):
        """No-op placeholder; sub-plots manage their own plot characteristics."""

class SubPlotFrame(QWidget):
    """UI frame that holds a labeled sub-plot widget.

    The frame loads a small UI fragment, sets the sub-plot title, and instantiates the
    appropriate plot widget according to the PlotParams type provided by the parent
    `PlotsArrayWidget`.

    Parameters
    ----------
    pw : str
        Sub-plot name/key used to look up parameters.
    sp_id : int
        Sub-plot identifier used when constructing plot widgets.
    parent_wdgt : PlotsArrayWidget
        The parent container providing controller, comp names, and loader.
    """

    def __init__(self, pw, sp_id, parent_wdgt: PlotsArrayWidget):
        super().__init__()
        self.parent_wdgt = parent_wdgt
        plot_params = self.parent_wdgt.out_plots[pw]
        sub_plot_ui_widget = self.parent_wdgt.loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "sub_plot.ui",
            ),
            self.parent_wdgt,
        )
        sub_plot_frame_contents = sub_plot_ui_widget.findChild(QFrame, "frame_contents")
        sub_plot_name = sub_plot_frame_contents.findChild(QLabel, "sub_plot_name")
        sub_plot_name.setStyleSheet("color: #6e778d; font-size: 20px;")
        sub_plot_name.setText(pw)
        sub_plot_widget = sub_plot_frame_contents.findChild(QWidget, "sub_plot_widget")
        comp_name = self.parent_wdgt.comp_name
        comp_display_name = self.parent_wdgt.comp_display_name
        if isinstance(plot_params, PlotGaugeParams):
            sub_plot = AnalogGaugeWidget(
                self.parent_wdgt.controller,
                self.parent_wdgt.comp_name,
                self.parent_wdgt.comp_display_name,
                plot_params.min_val,
                plot_params.max_val,
                plot_params.unit,
                sp_id,
                self.parent_wdgt,
            )
            sub_plot.setMinimumSize(200, 200)
        elif isinstance(plot_params, PlotLabelParams):
            sub_plot = LabelPlotWidget(
                self.parent_wdgt.controller,
                comp_name,
                pw,
                plot_params,
                sp_id,
                self.parent_wdgt,
            )
            sub_plot.title_frame.setVisible(False)
            sub_plot_name.setVisible(False)
        elif isinstance(plot_params, PlotLevelParams):
            sub_plot = LevelPlotWidget(
                self.parent_wdgt.controller,
                comp_name,
                comp_display_name,
                plot_params.min_val,
                plot_params.max_val,
                1,
                plot_params.unit,
                sp_id,
                self.parent_wdgt,
            )
            sub_plot.setFixedSize(200, 200)
            #hide x axis
            sub_plot.graph_widget.getAxis('bottom').setVisible(False)
        elif isinstance(plot_params, PlotCheckBoxParams):
            sub_plot = CheckBoxListWidget(
                self.parent_wdgt.controller,
                comp_name,
                comp_display_name,
                plot_params.labels,
                sp_id,
            )
            sub_plot.setFixedSize(200, 200)
        else:

            sub_plot = PlotLinesWidget(
                self.parent_wdgt.controller,
                self.parent_wdgt.comp_name,
                self.parent_wdgt.comp_display_name,
                plot_params if isinstance(plot_params, LinesPlotParams) else LinesPlotParams(
                    pw,
                    plot_params.enabled,
                    dimension=1,
                    time_window=30,
                    unit=plot_params.unit,
                ),
                sp_id,
                self.parent_wdgt,
            )
            sub_plot.setFixedSize(1200, 200)
        sub_plot_widget.layout().addWidget(sub_plot)
        self.parent_wdgt.out_plots_widget[pw] = sub_plot

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(sub_plot_ui_widget)
        sub_plot_widget.setContentsMargins(0, 0, 0, 0)

class FlowContainer(QListWidget):
    """Flow-style list widget to arrange subplots with wrapping.

    This class is currently unused in favor of direct `QHBoxLayout`/`QVBoxLayout` but
    remains available for alternative layout strategies that need item-level wrapping
    behavior.
    """

    def __init__(self, parent_wdgt):
        super().__init__()
        self.parent_wdgt = parent_wdgt
        self.viewport().setBackgroundRole(QPalette.Window)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        # prevent user repositioning
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setSpacing(4)
        self.setItemAlignment(Qt.AlignmentFlag.AlignCenter)

    def addSubPlot(self, sub_plot, sp_id, parent_wdgt):
        """Add a `SubPlotFrame` for the given subplot key and id.

        Parameters
        ----------
        sub_plot : str
            Sub-plot name/key to resolve from the parent widget.
        sp_id : int
            Sub-plot identifier.
        parent_wdgt : PlotsArrayWidget
            Parent container providing context and the loader.
        """
        item = QListWidgetItem(sub_plot)
        item.setFlags(item.flags() & ~(Qt.ItemIsSelectable | Qt.ItemIsEnabled))
        self.addItem(item)
        frame = SubPlotFrame(sub_plot, sp_id, parent_wdgt)
        item.setSizeHint(frame.sizeHint())
        self.setItemWidget(item, frame)
        frame.setStyleSheet("background-color: rgb(39, 44, 54);")
