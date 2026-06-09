#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    LabelPlotWidget.py
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
Label-style plot widget that displays a single numeric value with unit.

This widget loads a small UI layout and updates a value label at a fixed cadence while
logging is active. It derives from `PlotWidget`, clearing inherited plot elements while
preserving timers, signals, and common attributes.

Responsibilities:
- Load the UI fragment for a labeled value display and attach it to the container.
- Update the rendered value based on incoming samples.
- Start/stop the internal update timer when logging toggles.
"""

import os

from PySide6.QtWidgets import QLabel, QFrame
from PySide6.QtCore import Slot
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui
from stdatalog_gui.Utils.PlotParams import PlotLevelParams
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class LabelPlotWidget(PlotWidget):
    """Compact label/value widget for scalar telemetry.

    Parameters
    ----------
    controller : QObject
        Controller object used by the base `PlotWidget` for timing/signals.
    comp_name : str
        Component identifier associated with this widget.
    comp_display_name : str
        Human-readable component name drawn in the label.
    plot_params : PlotLevelParams
        Parameters describing the value bounds and unit.
    p_id : int, optional
        Plot/widget identifier used by the base implementation.
    parent : QWidget | None, optional
        Optional parent widget.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        plot_params: PlotLevelParams,
        p_id=0,
        parent=None,
    ):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent)

        # Clear PlotWidget inherited graphic elements (keeping attributes, functions, signals)
        for i in reversed(range(self.contents_frame.layout().count())):
            self.contents_frame.layout().itemAt(i).widget().setParent(None)

        QPyDesignerCustomWidgetCollection.registerCustomWidget(PlotWidget, module="PlotWidget")
        loader = QUiLoader()
        self.plot_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "plot_label_widget.ui",
            ),
            parent,
        )

        self.plot_params = plot_params
        self.min_val = plot_params.min_val
        self.max_val = plot_params.max_val
        self.value = None

        self.frame_plot = self.plot_widget.findChild(QFrame,"frame_plot")

        self.label_widget = self.frame_plot.findChild(QLabel, "label")
        self.label_widget.setText(comp_display_name)
        self.value_widget = self.frame_plot.findChild(QLabel, "value")
        self.value_widget.setText("")
        self.value_widget.setFixedWidth(100)
        self.unit_widget = self.frame_plot.findChild(QLabel, "unit")
        self.unit_widget.setText(f"[{self.plot_params.unit}]")

        self.timer_interval_ms = self.timer_interval * 700

        self.contents_frame.layout().addWidget(self.plot_widget)

    @Slot(bool)
    def s_is_logging(self, status: bool, interface: int):
        """Start/stop periodic updates when logging toggles.

        Parameters
        ----------
        status : bool
            True when logging starts, False when it stops.
        interface : int
            1=USB, 3=Serial trigger the periodic updates; 0=SD Card prints a message.
        """
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
            if status:
                self.timer.start(self.timer_interval_ms)
            else:
                self.value = None
                self.timer.stop()

        else: # interface == 0
            print(f"Component {self.comp_name} is logging on SD Card: {status}")

    def update_plot(self):
        """Update the UI label with the latest value and request a repaint."""
        if self.value is not None:
            self.value_widget.setText(str(self.value[0]))
        self.update()

    def add_data(self, data):
        """Store the latest sample for display on the next update.

        Parameters
        ----------
        data : Sequence[int | float]
            Expected to contain the numeric value at index 0.
        """
        self.value = data[0]
