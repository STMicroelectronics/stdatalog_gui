#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_FastTelemetriesPlotWidget.py
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
Fast telemetries composite plot widget for Motor Control.

This module defines `HSD_MC_FastTelemetriesPlotWidget`, which arranges one or more
`HSD_MC_FastTelemetriesPlotLinesWidget` instances to visualize high-rate MC
telemetries such as phase currents (I) and voltages (V). It handles dynamic enabling of
subplots and routes incoming interleaved samples to the appropriate sub-widgets with
scaling factors provided by the controller.
"""
from PySide6.QtCore import Slot

from stdatalog_gui.Utils.PlotParams import MCTelemetriesPlotParams
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget
from stdatalog_gui.HSD_MC_GUI.Widgets.HSD_MC_FastTelemetriesPlotLinesWidget import HSD_MC_FastTelemetriesPlotLinesWidget

class HSD_MC_FastTelemetriesPlotWidget(PlotWidget):
    """Composite widget for MC fast telemetries.

    Parameters
    ----------
    controller : STDTDL_Controller
        Application controller coordinating data and configuration.
    comp_name : str
        Component name for the fast telemetry source.
    comp_display_name : str
        Human-friendly component label.
    plot_params : MCTelemetriesPlotParams
        Parameters describing which fast telemetries to show and their units.
    time_window : int
        Time window in seconds used to derive plotting interval.
    p_id : int, optional
        Plot identifier for base `PlotWidget`, by default 0.
    parent : QWidget, optional
        Optional parent widget.

    Attributes
    ----------
    graph_widgets : dict
        Mapping from telemetry key to the corresponding plot lines widget.
    plots_params : MCTelemetriesPlotParams
        Latest configuration governing visibility and scaling.
    ft_enabled_list : list
        Names of enabled fast telemetries while logging is active.
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
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, "")

        self.plot_t_interval_size = int(
            self.plot_len / (time_window / self.timer_interval)
        )

        self.graph_curves = dict()
        self.one_t_interval_resampled = dict()

        self.graph_widget.deleteLater()

        self.plots_params = plot_params

        self.graph_widgets = {}

        for i, p in enumerate(plot_params.plots_params_dict):
            unit = self.plots_params.plots_params_dict[p].unit
            self.plots_params.plots_params_dict[p].unit = f"{p} [{unit}]"
            pw = HSD_MC_FastTelemetriesPlotLinesWidget(
                self.controller,
                self.plots_params.plots_params_dict[p].comp_name,
                p,
                plot_params.plots_params_dict[p],
                i,
                self,
            )
            self.graph_widgets[p] = pw

            # Clear PlotWidget inherited graphic elements (keeping attributes, functions, signals)
            for i in reversed(range(pw.layout().count())):
                pw.layout().itemAt(i).widget().setParent(None)

            self.contents_frame.layout().addWidget(self.graph_widgets[p].graph_widget)
            self.contents_frame.layout().setSpacing(6)

        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params: MCTelemetriesPlotParams):
        """Update per-telemetry visibility according to provided parameters.

        Parameters
        ----------
        plot_params : MCTelemetriesPlotParams
            The latest configuration containing enabled flags per telemetry.
        """
        self.plots_params = plot_params
        for p in plot_params.plots_params_dict:
            p_enabled = plot_params.plots_params_dict[p].enabled
            self.graph_widgets[p].graph_widget.setVisible(p_enabled)

        if self.app_qt is not None:
            self.app_qt.processEvents()

    @Slot(bool)
    def s_is_logging(self, status: bool, interface: int):
        """Respond to logging changes and refresh enabled fast telemetry list."""
        if interface == 1 or interface == 3:
            print(f"Component {self.comp_name} is logging via USB: {status}")
            if status:
                # Get number of enabled fast telemetries
                self.ft_enabled_list = [
                    ft
                    for ft in self.plots_params.plots_params_dict
                    if self.plots_params.plots_params_dict[ft].enabled
                ]
                self.update_plot_characteristics(self.plots_params)
            else:
                self.ft_enabled_list = []

    def update_plot(self):
        """Delegate periodic plot updates to base class implementation."""
        super().update_plot()

    def add_data(self, data):
        """Route and scale incoming interleaved samples to sub-widgets.

        Parameters
        ----------
        data : list
            A frame of interleaved samples. Per-telemetry series are extracted using
            stride slicing based on the number of enabled fast telemetries.

        Notes
        -----
        - Telemetries with name containing "I" are scaled by `current_scaler`.
        - Telemetries with name containing "V" are scaled by `voltage_scaler`.
        """
        for i, ft_enabled_name in enumerate(self.ft_enabled_list):
            if "I" in ft_enabled_name:
                self.graph_widgets[ft_enabled_name].add_data(
                    [
                        data[0][i :: len(self.ft_enabled_list)] * self.plots_params.current_scaler
                    ]
                )
            elif "V" in ft_enabled_name:
                self.graph_widgets[ft_enabled_name].add_data(
                    [
                        data[0][i :: len(self.ft_enabled_list)] * self.plots_params.voltage_scaler
                    ]
                )

    def get_num_enabled_fast_tele(self):
        """Return the number of fast telemetries currently enabled."""
        enabled_cnt = 0
        for _, p in enumerate(self.plots_params.plots_params_dict):
            if self.plots_params.plots_params_dict[p].enabled:
                enabled_cnt += 1
        return enabled_cnt
