#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_SlowTelemetriesPlotWidget.py
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
Slow telemetries composite plot widget for Motor Control.

This module defines `HSD_MC_SlowTelemetriesPlotWidget`, a container that assembles various
plot elements (gauges, labels, levels, checkboxes, and line plots) to visualize slow
telemetries exposed by the Motor Control device. The layout is loaded from a Qt Designer
`.ui` file and populated dynamically based on `MCTelemetriesPlotParams` received from the
controller.
Responsibilities:
- Load the slow telemetries UI layout.
- Instantiate and arrange individual telemetry widgets according to configuration.
- Update visibility of widgets based on enabled flags during logging.
"""

import os

from PySide6.QtCore import Slot
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui.HSD_MC_GUI
from stdatalog_gui.Utils.PlotParams import (
    PlotCheckBoxParams,
    MCTelemetriesPlotParams,
    PlotGaugeParams,
    PlotLabelParams,
    PlotLevelParams,
)
from stdatalog_gui.Widgets.Plots.AnalogGaugeWidget import AnalogGaugeWidget
from stdatalog_gui.Widgets.Plots.CheckBoxListWidget import CheckBoxListWidget
from stdatalog_gui.Widgets.Plots.LabelPlotWidget import LabelPlotWidget
from stdatalog_gui.Widgets.Plots.LevelPlotWidget import LevelPlotWidget
from stdatalog_gui.Widgets.Plots.PlotLinesWidget import PlotLinesWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class HSD_MC_SlowTelemetriesPlotWidget(PlotWidget):
    """Composite widget for MC slow telemetries.

    Parameters
    ----------
    controller : STDTDL_Controller
        Application controller coordinating data flow and UI updates.
    comp_name : str
        Component name for the telemetry source.
    comp_display_name : str
        Human-friendly display name for the component.
    plot_params : MCTelemetriesPlotParams
        Plot parameter container describing which telemetry widgets to build and enable.
    time_window : int
        Time window in seconds for line plots (not used by slow widgets but preserved).
    p_id : int, optional
        Plot identifier used by the base `PlotWidget` for indexing, by default 0.
    parent : QWidget, optional
        Optional parent widget.

    Attributes
    ----------
    graph_widgets : dict
        Mapping from telemetry name to the instantiated widget.
    plots_params : MCTelemetriesPlotParams
        Last set of parameters used to configure the widget visibility.
    plot_widget : QWidget
        Root widget loaded from the `.ui` file containing layout placeholders.
    st_enabled_list : list
        Names of enabled slow telemetries while logging is active.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        plot_params,
        time_window,
        p_id=0,
        parent=None,
    ):
        _ = time_window  # Unused for slow telemetries
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, "")

        self.graph_widget.deleteLater()
        self.plots_params = plot_params

        self.graph_widgets = {}

        QPyDesignerCustomWidgetCollection.registerCustomWidget(PlotWidget, module="PlotWidget")
        loader = QUiLoader()
        self.plot_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.HSD_MC_GUI.__file__),
                "UI",
                "slow_mc_telemetries_widget.ui",
            ),
            parent,
        )

        for i, p in enumerate(self.plots_params.plots_params_dict):
            p_dict_item = self.plots_params.plots_params_dict[p]
            # self.plots_params.plots_params_dict[p].unit = "{} [{}]".format(p,unit)
            if isinstance(p_dict_item, PlotGaugeParams):
                pw = AnalogGaugeWidget(
                    self.controller,
                    self.comp_name,
                    p,
                    p_dict_item.min_val,
                    p_dict_item.max_val,
                    p_dict_item.unit,
                    i,
                    self,
                )
                pw.setMinimumSize(200,200)
                self.graph_widgets[p] = pw
                self.plot_widget.gauges_telemetries.layout().addWidget(self.graph_widgets[p])
            elif isinstance(p_dict_item, PlotLabelParams):
                pw = LabelPlotWidget(
                    self.controller, self.comp_name, p, p_dict_item, i, self
                )
                pw.title_frame.setVisible(False)
                self.graph_widgets[p] = pw
                self.plot_widget.labels_telemetries.layout().addWidget(self.graph_widgets[p])
            elif isinstance(p_dict_item, PlotLevelParams):
                pw = LevelPlotWidget(
                    self.controller,
                    self.comp_name,
                    p,
                    p_dict_item.min_val,
                    p_dict_item.max_val,
                    1,
                    p_dict_item.unit,
                    i,
                    self,
                )
                pw.setFixedSize(200, 200)
                #hide x axis
                pw.graph_widget.getAxis('bottom').setVisible(False)
                self.graph_widgets[p] = pw
                self.plot_widget.levels_telemetries.layout().addWidget(self.graph_widgets[p])
            elif isinstance(p_dict_item, PlotCheckBoxParams):
                pw = CheckBoxListWidget(
                    self.controller, self.comp_name, p, p_dict_item.labels, i
                )
                # pw.setFixedSize(200, 250)
                self.graph_widgets[p] = pw
                self.plot_widget.checkboxes_telemetries.layout().addWidget(self.graph_widgets[p])
            else:
                pw = PlotLinesWidget(
                    self.controller, self.comp_name, p, p_dict_item, i, self
                )
                self.graph_widgets[p] = pw
                self.plot_widget.lines_telemetries.layout().addWidget(self.graph_widgets[p])

        self.contents_frame.layout().addWidget(self.plot_widget)
        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params: MCTelemetriesPlotParams):
        """Update visibility of telemetry widgets according to parameters.

        Parameters
        ----------
        plot_params : MCTelemetriesPlotParams
            The latest configuration to apply, including enabled flags per telemetry.
        """
        self.plots_params = plot_params
        if self.plots_params.enabled:
            for p in plot_params.plots_params_dict:
                p_enabled = plot_params.plots_params_dict[p].enabled
                self.graph_widgets[p].setVisible(p_enabled)
        if self.app_qt is not None:
            self.app_qt.processEvents()

    @Slot(bool)
    def s_is_logging(self, status: bool, interface: int):
        """React to logging state changes.

        When logging over USB (interfaces 1 or 3), rebuild the list of enabled slow
        telemetries to drive data routing in `add_data`.

        Parameters
        ----------
        status : bool
            True if logging starts, False if it stops.
        interface : int
            Interface identifier (1/3 indicates USB logging).
        """
        if interface == 1 or interface == 3:
            print(f"Component {self.comp_name} is logging via USB: {status}")
            if status:
                #Get number of enabled slow telemetries
                self.st_enabled_list = [
                    st
                    for st in self.plots_params.plots_params_dict
                    if self.plots_params.plots_params_dict[st].enabled
                ]
                self.update_plot_characteristics(self.plots_params)
            else:
                self.st_enabled_list = []

    def add_data(self, data):
        """Add a new data frame to the appropriate telemetry widgets.

        Parameters
        ----------
        data : list
            Frame of telemetry values in the same order as `st_enabled_list`.

        Notes
        -----
        - For checkbox-based `fault` telemetry, emits `sig_motor_fault_raised` when value
            is non-zero.
        - Gauges expect a scalar; other widgets receive small lists to fit their API.
        """
        for i, st_enabled_name in enumerate(self.st_enabled_list):
            p_dict_item = self.plots_params.plots_params_dict[st_enabled_name]
            if isinstance(p_dict_item, PlotGaugeParams):
                self.graph_widgets[st_enabled_name].add_data(data[i][0])
            else:
                if isinstance(p_dict_item, PlotCheckBoxParams) and st_enabled_name == "fault":
                    if data[i] != 0:
                        self.controller.sig_motor_fault_raised.emit()
                self.graph_widgets[st_enabled_name].add_data([data[i]])
