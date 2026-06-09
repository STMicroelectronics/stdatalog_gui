#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    PlotLinesWidget.py
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
Multi-line time series plot widget with resampling and rolling window display.

This module implements a general-purpose line plot that can render multiple dimensions
over a fixed time window. Incoming data are buffered in per-axis queues, resampled to a
uniform number of points per timer interval, and appended to rolling y-queues that match
the x-axis sampling. The widget integrates with the common `PlotWidget` base to share
timing, axis labels, and logging/detecting signals.
"""
from collections import deque

import numpy as np
from PySide6.QtCore import Slot
import pyqtgraph as pg

from stdatalog_gui.Utils.PlotParams import LinesPlotParams
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class PlotLinesWidget(PlotWidget):
    """Rolling line plot with resampling for N-dimensional signals.

    Parameters
    ----------
    controller : QObject
        Controller used by the base `PlotWidget` to coordinate timers and signals.
    comp_name : str
        Component identifier associated with this plot.
    comp_display_name : str
        Human-readable component name for UI messages.
    plot_params : LinesPlotParams
        Plot configuration including `time_window`, `unit`, and `dimension`.
    p_id : int, optional
        Plot identifier used by the base class; defaults to 0.
    parent : QWidget | None, optional
        Parent widget.

    Attributes
    ----------
    plot_t_interval_size : int
        Number of samples plotted per timer interval after resampling.
    lines_colors : list[str]
        Color palette used to style each axis curve (cycled if needed).
    graph_curves : dict[int, pg.PlotDataItem]
        Mapping from axis index to the pyqtgraph curve item.
    _data : dict[int, deque]
        Per-axis queue collecting raw incoming samples.
    y_queue : dict[int, deque]
        Per-axis rolling window buffer shown on screen.
    current_x : float
        Current x-axis head position (seconds).
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

        # self.unit = plot_params.unit
        self.plot_params = plot_params
        self.plot_t_interval_size = int(
            self.plot_len / (plot_params.time_window / self.timer_interval)
        )

        self.lines_colors = [
            '#e6007e', '#a4c238', '#3cb4e6', '#ef4f4f', '#46b28e',
            '#e8ce0e', '#60b562', '#f99e20', '#41b3ba',
        ]
        self.graph_curves = dict()

        self.one_t_interval_resampled = dict()
        self._data = dict()  # dict of queues
        self.y_queue = dict()  # dict of queues
        self.current_x = 0

        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params: LinesPlotParams):
        """Recompute buffers and curves to reflect new plot parameters.

        Parameters
        ----------
        plot_params : LinesPlotParams
            Contains `dimension`, `time_window`, and other line plot settings.
        """
        self.plot_params = plot_params

        for i in range(self.plot_params.dimension):
            self.one_t_interval_resampled[i] = np.zeros(self.plot_t_interval_size)

        self.x_data = np.linspace(
            -(plot_params.time_window) + self.current_x,
            self.current_x,
            self.plot_len,
        )
        for i in range(self.plot_params.dimension):
            self._data[i] = deque(maxlen=200000)
            self.y_queue[i] = deque(maxlen=self.plot_len)
            self.y_queue[i].extend(np.zeros(self.plot_len))
            if len(self.graph_curves) < self.plot_params.dimension:
                self.graph_curves[i] = self.graph_widget.plot()
                self.graph_curves[i] = pg.PlotDataItem(
                    pen={
                        'color': self.lines_colors[
                            i - (len(self.lines_colors) * int(i / len(self.lines_colors)))
                        ],
                        'width': 1,
                    },
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
        """Handle external time window updates and rebuild buffers.

        Parameters
        ----------
        new_time_w : float
            The new plot time window in seconds.
        """
        self.plot_params.time_window = new_time_w
        self.update_plot_characteristics(self.plot_params)

    @Slot(bool, int)
    def s_is_logging(self, status: bool, interface: int):
        """Start/stop timer and reset state based on logging status.

        Parameters
        ----------
        status : bool
            Logging status.
        interface : int
            Interface id: 1 USB, 3 Serial, 0 SD Card.
        """
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
            if status:
                self.current_x = 0
                self.update_plot_characteristics(self.plot_params)
                self.timer.start(self.timer_interval_ms)
            else:
                self.timer.stop()

        else: # interface == 0
            print(f"Component {self.comp_name} is logging on SD Card: {status}")

    @Slot(bool)
    def s_is_detecting(self, status: bool):
        """Mirror detection status to logging to reuse the same pipeline."""
        self.s_is_logging(status, 1)

    def reset(self):
        """Reserved for future state resets specific to this plot type."""

    def resample_linear1D(self, original, targetLen):
        """Linearly resample a 1D sequence to a given length.

        Parameters
        ----------
        original : Sequence[float] | np.ndarray
            Input sequence to interpolate.
        targetLen : int
            Desired output length.

        Returns
        -------
        np.ndarray
            Interpolated array of length `targetLen`.
        """
        original = np.array(original, dtype=float)
        index_arr = np.linspace(0, len(original) - 1, num=targetLen, dtype=float)
        index_floor = np.array(index_arr, dtype=int)  # Round down
        index_ceil = index_floor + 1
        index_rem = index_arr - index_floor  # Remainder

        val1 = original[index_floor]
        val2 = original[index_ceil % len(original)]
        interp = val1 * (1.0 - index_rem) + val2 * index_rem
        assert(len(interp) == targetLen)
        return interp

    def update_plot(self):
        """Advance time, resample queued data, and refresh curve visuals."""
        self.x_data = self.x_data + self.timer_interval
        # for i in range(self.n_curves):
        for i in range(self.plot_params.dimension):
            if len(self._data[i]) > 0:  # If data queue is not empty
                # Extract all data from the queue (pop)
                one_reduced_t_interval = [self._data[i].popleft() for _i in range(len(self._data[i]))]
                # Resample extracted raw data to have the same plot_timer_interval size
                # (plot len / (time window / times interval(sec)))
                self.one_t_interval_resampled[i] = self.resample_linear1D(
                    one_reduced_t_interval, self.plot_t_interval_size
                )
                # Put resampled data into the y data queue
                self.y_queue[i].extend(self.one_t_interval_resampled[i])
            else:  # data queue is empty
                self.y_queue[i].extend(self.one_t_interval_resampled[i])
            # set extracted resampled data into the plot curve (for each axis)
            # [x and y will have the same len = (plot len / (time window / times interval(sec)))]
            self.graph_curves[i].setData(x=self.x_data, y=np.array(self.y_queue[i]))
        self.app_qt.processEvents()

    def add_data(self, data):
        """Append new raw samples for each axis to the per-axis queues.

        Parameters
        ----------
        data : Sequence[Sequence[float]]
            Iterable with one iterable per dimension, each containing new samples.
        """
        for i in range(self.plot_params.dimension):
            self._data[i].extend(data[i])
