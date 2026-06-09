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
outputs as heatmaps. It currently draws a single target heatmap ("Target 1") with either a
4x4 or 8x8 resolution based on the provided `PlotParams`.

Highlights
----------
- Clears base plot visuals while preserving base class wiring and signals.
- Configures a `PlotHeatmapWidget` with default rotation and compact layout.
- Supports dynamic update of heatmap characteristics when plot parameters change.
- Parses incoming data according to an optional `output_format` mapping; falls back to fixed
    indexing when a format is not provided.
"""

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout

from stdatalog_gui.Utils.PlotParams import PlotParams
from stdatalog_gui.Widgets.Plots.PlotHeatmapWidget import PlotHeatmapWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

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
        self.RESOLUTION_4x4 = 0
        self.RESOLUTION_8x8 = 1

        # Clear PlotWidget-inherited frames, preserving attributes, functions, and signals.
        for i in reversed(range(self.layout().count())):
            self.contents_frame.layout().itemAt(i).widget().setParent(None)

        # Select heatmap resolution: 0 -> 4x4, 1 -> 8x8.
        heatmaps_shape = (
            (4, 4) if plot_params.resolution == self.RESOLUTION_4x4 else (8, 8)
        )

        # Create Target 1 heatmap with default rotation, compact header hidden.
        self.t1_out = PlotHeatmapWidget(
            controller,
            comp_name,
            comp_display_name,
            heatmaps_shape,
            plot_label="Target 1",
            p_id=p_id,
            parent=self,
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
            New plotting parameters; `resolution` selects 4x4 or 8x8 and may carry
            an updated `output_format` mapping.
        """
        heatmaps_shape = (
            (4, 4) if plot_params.resolution == self.RESOLUTION_4x4 else (8, 8)
        )
        self.t1_out.update_plot_characteristics(heatmaps_shape)
        # self.t2_out.update_plot_characteristics(heatmaps_shape)
        self.plot_params = plot_params
        self.output_format = self.plot_params.output_format

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
            - `target_status.start_id`
            - `nof_outputs` (stride)
        - Otherwise, defaults to an 8-value stride with distance at index 4 and status
            at index 3 relative to the stride.
        """
        if self.output_format:
            start_t1_dist_id = self.output_format.get("target_distance").get(
                "start_id"
            )
            start_t1_status_id = self.output_format.get("target_status").get(
                "start_id"
            )
            out_data_step = self.output_format.get("nof_outputs")
            t1_data = data[0][start_t1_dist_id::out_data_step]
            t1_status_mask = data[0][start_t1_status_id::out_data_step]
        else:
            start_t1_dist_id = 4
            # Extract target matrices with fixed stride
            t1_data = data[0][start_t1_dist_id::8]
            t1_status_mask = data[0][start_t1_dist_id - 1::8]
            # #NOTE! Demo Sensor converge
            # start_t1_dist_id = 1
            # #extract targets matrices
            # t1_data = data[0][start_t1_dist_id::2]
            # t1_status_mask = data[0][start_t1_dist_id-1::2]
        # Forward parsed data to the Target 1 heatmap
        self.heatmaps["target1"].add_data((t1_data, t1_status_mask))
