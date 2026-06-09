#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_FastTelemetriesPlotLinesWidget.py
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
Fast telemetries lines plot widget for Motor Control.

This module defines `HSD_MC_FastTelemetriesPlotLinesWidget`, a specialized plot widget
that renders high-rate MC telemetries as scrolling line graphs. It handles dynamic
reconfiguration on time-window changes, resamples incoming data to a fixed interval size,
and draws tag markers when labeling events occur.
"""

import numpy as np
from collections import deque

from PySide6.QtCore import Slot

import pyqtgraph as pg
from stdatalog_gui.Utils.PlotParams import LinesPlotParams

from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class HSD_MC_FastTelemetriesPlotLinesWidget(PlotWidget):
    """Plot lines widget for MC fast telemetries.

    Parameters
    ----------
    controller : STDTDL_Controller
        Application controller providing signals and component status.
    comp_name : str
        Component name for the telemetry source.
    comp_display_name : str
        Human-friendly display name, used in titles/labels.
    plot_params : LinesPlotParams
        Plot configuration including dimension, units, and time window.
    p_id : int, optional
        Plot identifier for base `PlotWidget`, by default 0.
    parent : QWidget, optional
        Optional parent widget.

    Attributes
    ----------
    lines_colors : list
        Predefined color palette used cyclically for multiple curves.
    graph_curves : dict
        Map from curve index to `PlotDataItem`.
    _data : dict
        Map from curve index to a queue of incoming samples.
    y_queue : dict
        Map from curve index to the scrolling y values buffer.
    one_t_interval_resampled : dict
        Temporary resampled arrays for each curve per update interval.
    active_tags : dict
        Track tag label active state for rendering ON/OFF markers.
    tag_lines : list
        List of `InfiniteLine` items representing tag events.
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
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, plot_params.unit)

        self.controller.sig_plot_window_time_updated.connect(self.s_time_window_updated)
        self.controller.sig_tag_done.connect(self.s_tag_done)

        # self.unit = plot_params.unit
        self.plot_params = plot_params
        self.plot_t_interval_size = int(
            self.plot_len / (plot_params.time_window / self.timer_interval)
        )

        self.lines_colors = [
            '#e6007e', '#a4c238', '#3cb4e6', '#ef4f4f', '#46b28e',
            '#e8ce0e', '#60b562', '#f99e20', '#41b3ba'
        ]
        self.graph_curves = dict()

        self.one_t_interval_resampled = dict()
        self._data = dict() # dict of queues
        self.y_queue = dict() # dict of queues

        self.active_tags = dict()
        self.tag_lines = []

        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params:LinesPlotParams):
        """Apply plot configuration and initialize curves and buffers.

        Parameters
        ----------
        plot_params : LinesPlotParams
            Configuration containing dimension, units, and time window.
        """
        self.plot_params = plot_params

        for i in range(self.plot_params.dimension):
            self.one_t_interval_resampled[i] = np.zeros(self.plot_t_interval_size)

        self.x_data = np.linspace(-(plot_params.time_window), 0, self.plot_len)
        for i in range(self.plot_params.dimension):
            self._data[i] = deque(maxlen=200000)
            self.y_queue[i] = deque(maxlen=self.plot_len)
            self.y_queue[i].extend(np.zeros(self.plot_len))
            if len(self.graph_curves) < self.plot_params.dimension:
                self.graph_curves[i] = self.graph_widget.plot()
                pen_color = self.lines_colors[
                    i - (len(self.lines_colors) * int(i / len(self.lines_colors)))
                ]
                self.graph_curves[i] = pg.PlotDataItem(
                    pen={'color': pen_color, 'width': 1},
                    skipFiniteCheck=True,
                    ignoreBounds=True,
                )
                self.graph_widget.addItem(self.graph_curves[i])

        if self.app_qt is not None:
            self.app_qt.processEvents()

        self.plot_t_interval_size = int(
            self.plot_len / (plot_params.time_window / self.timer_interval)
        )

    @Slot(float)
    def s_time_window_updated(self, new_time_w):
        """Handle time window changes and rebuild plot buffers.

        Parameters
        ----------
        new_time_w : float
            New time window duration (seconds) for the plot.
        """
        self.plot_params.time_window = new_time_w
        self.update_plot_characteristics(self.plot_params)

    @Slot(bool, int) #Override PlotLinesWavWidget s_is_logging
    def s_is_logging(self, status: bool, interface: int):
        """Start/stop plot timer based on logging state.

        For USB (1/3) interfaces, clears tag lines when logging starts and restarts the
        (1: USB, 3: Serial)
        plot timer; otherwise delegates to the base implementation.
        """
        if interface == 1 or interface == 3:
            print(f"Sensor {self.comp_name} is logging via USB: {status}")
            if status:
                self.__clean_tag_lines()
                self.update_plot_characteristics(self.plot_params)
                self.timer.start(self.timer_interval_ms)
            else:
                self.timer.stop()
        else: # interface == 0
            print(f"Sensor {self.comp_name} is logging on SD Card: {status}")
            super().s_is_logging(status, interface)

    @Slot(bool)
    def s_is_detecting(self, status: bool):
        """Compatibility hook: treat detecting status as USB logging toggle."""
        self.s_is_logging(status, 1)

    def reset(self):
        """Reset the plot widget state (currently no-op)."""

    def resample_linear1D(self, original, targetLen):
        """Linearly resample a 1D array to a target length.

        Parameters
        ----------
        original : array-like
            Original samples sequence.
        targetLen : int
            Desired number of output samples.

        Returns
        -------
        numpy.ndarray
            Resampled values with length `targetLen`.
        """
        original = np.array(original, dtype=float)
        index_arr = np.linspace(0, len(original) - 1, num=targetLen, dtype=float)
        index_floor = np.array(index_arr, dtype=int) # Round down
        index_ceil = index_floor + 1
        index_rem = index_arr - index_floor # Remain

        val1 = original[index_floor]
        val2 = original[index_ceil % len(original)]
        interp = val1 * (1.0 - index_rem) + val2 * index_rem
        assert(len(interp) == targetLen)
        return interp

    def update_plot(self):
        """Scroll x-axis and set resampled data on each curve."""
        self.x_data = self.x_data + self.timer_interval
        # for i in range(self.n_curves):
        for i in range(self.plot_params.dimension):
            if len(self._data[i]) > 0: # If data queue is not empty
                # Extract all data from the queue (pop)
                one_reduced_t_interval = [
                    self._data[i].popleft() for _i in range(len(self._data[i]))
                ]
                # Resample extracted raw data to have the same plot_timer_interval size
                # (plot len / (time window / times interval(sec)))
                self.one_t_interval_resampled[i] = self.resample_linear1D(
                    one_reduced_t_interval, self.plot_t_interval_size
                )
                # Put resampled data into the y data queue
                self.y_queue[i].extend(self.one_t_interval_resampled[i])
            else: #data queue is empty
                self.y_queue[i].extend(np.zeros(len(self.one_t_interval_resampled[i])))
            # set extracted resampled data into the plot curve (for each axis)
            # [x and y will have the same len = (plot len / (time window / times interval(sec))
            self.graph_curves[i].setData(
                x=self.x_data, y=np.array(self.y_queue[i])
            )
        self.app_qt.processEvents()

    def add_data(self, data):
        """Append new samples for each curve into the input queues."""
        for i in range(self.plot_params.dimension):
            self._data[i].extend(data[i])

    @Slot()
    def s_tag_done(self, status, tag_label:str):
        """Draw ON/OFF tag markers at the current time position.

        Parameters
        ----------
        status : bool
            True when a tag starts (ON), False when it ends (OFF).
        tag_label : str
            Label to attach to the tag lines.
        """
        if status:
            if not tag_label in self.active_tags or self.active_tags[tag_label] == False:
                self.active_tags[tag_label] = True
                pen = pg.mkPen(color='#00FF00', width=1)
                tag_line = pg.InfiniteLine(
                    pos=self.x_data[-1], angle=90, movable=False, pen=pen,
                    label=tag_label + " ON"
                )
                self.graph_widget.addItem(tag_line, ignoreBounds=True)
                self.tag_lines.append(tag_line)
        else:
            if not tag_label in self.active_tags or self.active_tags[tag_label] == True:
                self.active_tags[tag_label] = False
                pen = pg.mkPen(color='#FF0000', width=1)
                tag_line = pg.InfiniteLine(
                    pos=self.x_data[-1], angle=90, movable=False, pen=pen,
                    label=tag_label + " OFF"
                )
                self.graph_widget.addItem(tag_line, ignoreBounds=True)
                self.tag_lines.append(tag_line)

    def __clean_tag_lines(self):
        """Remove existing tag lines from the graph widget."""
        for t in self.tag_lines:
            self.graph_widget.removeItem(t)
            self.tag_lines = []
