# ******************************************************************************
#  * @file    HSDPlotPOWWidget.py
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
Power/voltage/current plotting widget for the HSD GUI.

This module defines `HSDPlotPOWWidget`, a composite widget that displays voltage,
current, and power telemetry using multiple line plots. Each metric is rendered by an
internal `HSDPlotLinesWidget`. The widget configures per-plot units, manages visibility
based on plot parameters, and forwards streaming data to the appropriate sub-plot.

Highlights
----------
- Leverages the base `PlotWidget` wiring while replacing the default graph region with
    metric-specific line plots.
- Applies formatted units to sub-plots (e.g., "Voltage [V]").
- Updates sub-plot visibility and layout spacing on parameter changes.
"""
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotLinesWidget import HSDPlotLinesWidget

class HSDPlotPOWWidget(PlotWidget):
    """
    Composite plotting widget for power-related telemetry.

    Parameters
    ----------
    controller : object
        Application controller used by the base `PlotWidget`.
    comp_name : str
        Component name (unique identifier for the plot source).
    comp_display_name : str
        Human-friendly display name for the plot container.
    plot_params : object
        Plot parameters containing `plots_params_dict` entries for each metric.
    p_id : int, optional
        Plot identifier used by the base class, by default 0.
    parent : QWidget | None, optional
        Parent widget, by default `None`.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        plot_params,
        p_id=0,
        parent=None,
    ):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, "")

        self.graph_curves = dict()
        self.one_t_interval_resampled = dict()

        self.graph_widget.deleteLater()

        self.plots_params = plot_params

        self.graph_widgets = {}

        for i, p in enumerate(plot_params.plots_params_dict):
            unit = self.plots_params.plots_params_dict[p].unit
            self.plots_params.plots_params_dict[p].unit = f"{p} [{unit}]"
            pw = HSDPlotLinesWidget(
                self.controller,
                self.plots_params.plots_params_dict[p].comp_name,
                p,
                plot_params.plots_params_dict[p],
                i,
                self,
            )
            self.graph_widgets[p] = pw

            # Clear PlotWidget inherited graphic elements (preserves attributes,
            # functions and signals)
            for i in reversed(range(pw.layout().count())):
                pw.layout().itemAt(i).widget().setParent(None)

            self.contents_frame.layout().addWidget(self.graph_widgets[p].graph_widget)
            self.contents_frame.layout().setSpacing(6)

        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params):
        """
        Update visibility of power/voltage/current sub-plots.

        Parameters
        ----------
        plot_params : object
            Plot parameters with `plots_params_dict` entries controlling which
            sub-plots are enabled.
        """
        self.plots_params = plot_params
        for p in plot_params.plots_params_dict:
            p_enabled = plot_params.plots_params_dict[p].enabled
            self.graph_widgets[p].graph_widget.setVisible(p_enabled)

        if self.app_qt is not None:
            self.app_qt.processEvents()

    def update_plot(self):
        """
        Forward update to the base plot implementation.
        """
        super().update_plot()

    def add_data(self, data):
        """
        Route incoming telemetry samples to the appropriate sub-plots.

        Parameters
        ----------
        data : Sequence
            Data vector ordered as: Voltage, Voltage(VShunt), Current, Power.
        """
        self.graph_widgets["Voltage"].add_data([data[0]])
        self.graph_widgets["Voltage(VShunt)"].add_data([data[1]])
        self.graph_widgets["Current"].add_data([data[2]])
        self.graph_widgets["Power"].add_data([data[3]])
