#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    CheckBoxListWidget.py
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
List of checkboxes to reflect categorical telemetry/activity status.

This widget derives from `PlotWidget` and displays a vertical list of disabled checkboxes
that indicate which class/index is currently active based on incoming data. Index 0 is
treated as a fallback or "none" state and is enabled when no other index is active.

Responsibilities:
- Clear inherited `PlotWidget` UI and build a compact vertical list of checkboxes.
- Update the active checkbox according to latest data, reverting to index 0 when idle.
- Integrate with the logging timer exposed by the base class.
"""

from PySide6.QtWidgets import QCheckBox, QVBoxLayout
from PySide6.QtCore import Signal, Slot

from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class CheckBoxListWidget(PlotWidget):
    """Vertical list of checkboxes indicating the active class/index.

    Parameters
    ----------
    controller : QObject
        Controller or application object used by the base `PlotWidget`.
    comp_name : str
        Component identifier for this widget.
    comp_display_name : str
        Human-readable component name.
    labels_list : list[str]
        Labels for each checkbox in order. Index 0 is treated as the default/idle state.
    left_label : str | None, optional
        Optional label forwarded to `PlotWidget`.
    p_id : int, optional
        Numeric identifier used by the base implementation.
    parent : QWidget | None, optional
        Optional parent widget.

    Signals
    -------
    valueChanged(int)
        Emitted when value changes (not used directly by this implementation).
    """

    valueChanged = Signal(int)

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        labels_list,
        left_label=None,
        p_id=0,
        parent=None,
    ):
        super().__init__(
            controller, comp_name, comp_display_name, p_id, parent, left_label
        )

        # Clear PlotWidget inherited graphic elements (keeping attributes, functions, signals)
        for i in reversed(range(self.layout().count())):
            self.layout().itemAt(i).widget().setParent(None)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        self.layout().setSpacing(3)

        self.checkBoxList = []
        self.l_data = 0
        self.prev_data = -1
        self.labels_list = labels_list

        main_layout = QVBoxLayout()
        for _, label in enumerate(self.labels_list):
            cb = QCheckBox(str(label))
            cb.setEnabled(False)
            self.checkBoxList.append(cb)
            self.layout().addWidget(cb)

    @Slot(bool, int)
    def s_is_logging(self, status: bool, interface: int):
        """Start/stop the update timer based on logging interface/status.

        Parameters
        ----------
        status : bool
            True when logging starts; False when it stops.
        interface : int
            Interface identifier. 1=USB, 3=Serial, 0=SD Card (printed only).
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
            print(F"Component {self.comp_name} is logging on SD Card: {status}")

    def update_plot(self):
        """Update checkbox states according to the latest `l_data` value.

        Notes
        -----
        - When `l_data` is non-zero and changed, set that index checked and clear index 0.
        - When `l_data` is zero and changed, clear all indexes and set index 0 checked.
        """
        if self.l_data != 0:
            if self.l_data != self.prev_data:
                data = self.l_data
                self.checkBoxList[int(data)].setChecked(True)
                self.checkBoxList[0].setChecked(False)
        else:
            if self.l_data != self.prev_data:
                for idx in range(len(self.labels_list)):
                    self.checkBoxList[int(idx)].setChecked(False)
                self.checkBoxList[0].setChecked(True)
        self.prev_data = self.l_data
        self.update()

    def add_data(self, data):
        """Set the latest value from an incoming sample.

        Parameters
        ----------
        data : Sequence[int | float]
            Expected to contain a primary index/value at position 0.
        """
        self.l_data = data[0]
