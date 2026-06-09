#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    PlotBarWidget.py
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
Base bar-plot widget used by frequency and categorical visualizations.

This module defines a reusable bar plot widget built on top of ``pyqtgraph``. It provides
buffered data handling, a timer-driven update loop, and convenience hooks for reacting to
logging/detection state changes emitted by the controller. Concrete subclasses are
expected to specialize data preparation, styling, and any additional UI elements while
relying on the common buffering and rendering logic implemented here.

Responsibilities
----------------
- Maintain a fixed-size queue of incoming samples and compute display values.
- Render a bar graph and update it periodically when logging is active.
- Expose base slot methods for logging/detection that start or stop the timer.

Notes
-----
- The widget assumes that each incoming sample contains a vector of length equal to the
    number of bars configured for the widget. Samples are averaged over the current
    buffered window to produce the bar heights at each repaint.
- The update cadence is controlled by the base ``PlotWidget`` timer and a local
    multiplier (``timer_interval_ms``), allowing sensors to buffer data between updates.
"""

from collections import deque

import numpy as np
from PySide6.QtCore import Slot, QSize
import pyqtgraph as pg

from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class PlotBarWidget(PlotWidget):
    """Reusable bar graph plot with buffered updates.

    Parameters
    ----------
    controller : QObject
        Controller used by the base ``PlotWidget`` for timing and signals.
    comp_name : str
        Component identifier associated with the data (used in logs and titles).
    comp_display_name : str
        Human-readable component name displayed on the left-axis label.
    n_bars : int
        Number of bars to display. Must match the length of each incoming sample vector.
    y0 : float
        Lower bound for the y-axis.
    y1 : float
        Upper bound for the y-axis.
    bar_width : float, optional
        Width of each bar. Default is ``1``.
    unit : str, optional
        Left-axis unit or label suffix. Default is an empty string.
    p_id : int, optional
        Plot identifier forwarded to the base class. Default is ``0``.
    parent : QWidget | None, optional
        Parent widget. Default is ``None``.

    Attributes
    ----------
    y0 : float
        Lower bound of the y-axis.
    y1 : float
        Upper bound of the y-axis.
    n_bars : int
        Number of bars displayed in the graph.
    bar_width : float
        Width of each bar.
    _data : dict[int, collections.deque]
        Mapping from channel index to a deque that buffers incoming samples. Only the
        ``0`` channel is used by this widget.
    x : numpy.ndarray
        The x positions for the bars.
    bargraph : pyqtgraph.BarGraphItem
        The actual bar-graph item added to the plot.
    timer_interval_ms : int
        Effective update interval in milliseconds (derived from the base timer).
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        n_bars,
        y0,
        y1,
        bar_width=1,
        unit="",
        p_id=0,
        parent=None,
    ):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, unit)

        self.y0 = y0
        self.y1 = y1

        self.n_bars = n_bars
        self.bar_width = bar_width

        self._data = dict()  # dict of queues
        self._data[0] = deque(maxlen=200000)

        # create list for y-axis
        y1 = np.zeros(n_bars)

        # create horizontal list i.e x-axis
        if n_bars == 1:
            self.x = np.arange(0 , 1, dtype=int)
        else:
            self.x = np.arange(0, n_bars, dtype=int)

        self.bargraph = pg.BarGraphItem(
            x=self.x,
            height=y1,
            width=self.bar_width,
            brush='#a4c238',
            pen='#1B1D23',
        )

        self.graph_widget.setYRange(self.y0, self.y1, padding=0)

        # add item to plot window
        # adding bargraph item to the plot window
        self.graph_widget.addItem(self.bargraph)

        self.graph_widget.getPlotItem().layout.setContentsMargins(10, 3, 3, 3)
        self.graph_widget.getPlotItem().setMenuEnabled(False)  # Disable right click menu
        self.graph_widget.setMinimumSize(QSize(300, 150))

        styles = {'color': '#d2d2d2', 'font-size': '12px'}
        self.graph_widget.setLabel('left', self.left_label, **styles)

        self.timer_interval_ms = self.timer_interval * 700

    def update_plot_characteristics(self, plot_params):
        """Hook for subclasses to update plot styling and limits.

        Parameters
        ----------
        plot_params : Any
            A parameter object carrying plot-specific configuration (e.g., y-range,
            bar colors, labels). The base implementation is a no-op.

        Returns
        -------
        None
        """

    @Slot(bool, int)
    def s_is_logging(self, status: bool, interface: int):
        """Start or stop the update timer when logging toggles.

        Parameters
        ----------
        status : bool
            True when logging starts; False when logging stops.
        interface : int
            Interface identifier:
            - ``1``: USB. Start/stop the timer and log a message.
            - ``3``: Serial. Start/stop the timer and log a message.
            - ``0``: SD Card. Only logs a message; the timer is not managed here.

        Returns
        -------
        None
        """
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
            if status:
                self.buffering_timer_counter = 0
                self.timer.start(self.timer_interval_ms)
            else:
                self.timer.stop()
        else: # interface == 0
            print(f"Component {self.comp_name} is logging on SD Card: {status}")

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        """Alias for logging behavior when detection mode is used.

        Parameters
        ----------
        status : bool
            Detection active state. Uses interface 1 (USB) semantics.
        
        Returns
        -------
        None
        """
        self.s_is_logging(status, 1)

    def update_plot(self):
        """Consume buffered data, compute a mean, and update bar heights.

        This method is invoked by the internal timer. When the local buffering counter is
        cleared, it consumes the entire buffered window of samples, computes the mean for
        each bar across the window, and updates the ``BarGraphItem`` accordingly. If the
        counter is not cleared, the call only advances the counter to permit additional
        sensor buffering before the next visual update.

        Notes
        -----
        - Uses a skip interval via ``buffering_timer_counter`` to allow sensor buffering.
        - Computes the mean across queued samples for each bar and updates the graph.

        Returns
        -------
        None
        """
        if self.buffering_timer_counter == 0:
            if len(self._data[0]) > 0:
                # Extract all data from the queue (pop)
                one_reduced_t_interval = [
                    self._data[0].popleft() for _i in range(len(self._data[0]))
                ]
                y_value = np.array(one_reduced_t_interval)
                y_array_mean = np.mean(y_value, axis=0)
                self.bargraph.setOpts(x=self.x, height=y_array_mean)
            self.app_qt.processEvents()
        else:
            # Increment the buffering counter
            # (skip a plot timer interval to bufferize data from sensors)
            self.buffering_timer_counter += 1

    def add_data(self, data):
        """Append a new sample to the primary queue.

        Parameters
        ----------
        data : Sequence[int | float | numpy.ndarray]
            Data payload where index ``0`` contains a vector with ``n_bars`` elements.
            The vector may be a list or a ``numpy.ndarray``.

        Returns
        -------
        None
        """
        self._data[0].append(data[0])
