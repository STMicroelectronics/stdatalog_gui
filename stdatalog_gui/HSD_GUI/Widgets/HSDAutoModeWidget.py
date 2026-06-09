# ******************************************************************************
#  * @file    HSDAutoModeWidget.py
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
Automatic logging mode control widget for scheduled acquisitions.

This module defines `HSDAutoModeWidget`, a GUI component that exposes an
"Automatic Mode" for repeated start/stop logging cycles. It wires a toggle to
enable/disable automode, connects spin boxes for timing parameters (number of
acquisitions, start delay, logging period, idle period), and updates a status
title to show a live countdown for the current phase.

Highlights
----------
- Enables/disables automode via a `ToggleButton`, reflecting the state in the
    controller.
- Displays and validates timing ranges through info labels/tooltips populated
    from property metadata (min/max) when available.
- Shows a live, per-second countdown for phases: waiting to start, logging,
    and idle between logging cycles.
- Responds to controller signals to keep the UI in sync with automode status.

Notes
-----
- This widget does not implement automode logic itself; it delegates to the
    application controller and only manages UI state and feedback.
"""

import os

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QFrame, QSpinBox, QLabel
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

from stdatalog_gui.Widgets.ToggleButton import ToggleButton

import stdatalog_gui
from stdatalog_gui.Widgets.ComponentWidget import ComponentWidget

class HSDAutoModeWidget(ComponentWidget):
    """Widget that exposes and monitors the device automatic logging mode.

    Parameters
    ----------
    controller : object
        Application controller exposing automode enablement, status signals,
        and property access.
    comp_contents : list
        Component content descriptors used to bind widgets to properties and
        build tooltips with value ranges.
    comp_name : str, optional
        Component identifier, by default "automode".
    comp_display_name : str, optional
        Title shown in the UI header, by default "Automatic Mode".
    comp_sem_type : str, optional
        Semantic type passed to the base `ComponentWidget`, by default "other".
    c_id : int, optional
        Component id for the base widget, by default 0.
    parent : QWidget | None, optional
        Parent widget if embedded.
    """

    def __init__(
        self,
        controller,
        comp_contents,
        comp_name="automode",
        comp_display_name="Automatic Mode",
        comp_sem_type="other",
        c_id=0,
        parent=None,
    ):
        super().__init__(
            controller,
            comp_name,
            comp_display_name,
            comp_sem_type,
            comp_contents,
            c_id,
            parent,
        )

        self.controller.sig_is_waiting_auto_start.connect(self.is_waiting_auto_start)
        self.controller.sig_is_waiting_idle.connect(self.is_idle_auto_start)
        self.controller.sig_is_auto_started_inner.connect(self.is_auto_started_inner)

        self.app = self.controller.qt_app
        self.is_packed = False
        self.is_logging = False
        self.parent_widget = parent

        # clear all widgets in contents_widget layout (contents)
        for i in reversed(range(self.contents_widget.layout().count())):
            self.contents_widget.layout().itemAt(i).widget().deleteLater()

        self.setWindowTitle(comp_display_name)

        self.elapsed_time = 0
        self.digital_clock_timer = QTimer()
        self.digital_clock_timer.timeout.connect(self.update_time)

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            HSDAutoModeWidget,
            module="AutoModeWidget",
        )
        loader = QUiLoader()
        auto_mode_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "HSD_GUI",
                "UI",
                "auto_mode_widget.ui",
            )
        )
        self.frame_contents = auto_mode_widget.frame_auto_mode.findChild(
            QFrame,
            "frame_contents",
        )

        frame_enabled = self.frame_contents.findChild(QFrame,"frame_enabled")
        self.toggle_button = ToggleButton()
        frame_enabled.layout().addWidget(self.toggle_button)
        self.toggle_button.toggled.connect(self.toggle_button_toggled)

        nof_acq_info = self.frame_contents.findChild(QLabel, "nof_acq_info")
        idle_period_info = self.frame_contents.findChild(QLabel, "idle_period_info")
        log_period_info = self.frame_contents.findChild(QLabel, "log_period_info")
        start_delay_info = self.frame_contents.findChild(QLabel, "start_delay_info")

        nof_acq_value = self.frame_contents.findChild(QSpinBox, "nof_acq_value")
        self.idle_period_value: QSpinBox = self.frame_contents.findChild(
            QSpinBox,
            "idle_period_value",
        )
        self.log_period_value: QSpinBox = self.frame_contents.findChild(
            QSpinBox,
            "log_period_value",
        )
        self.start_delay_value: QSpinBox = self.frame_contents.findChild(
            QSpinBox,
            "start_delay_value",
        )

        for pw in self.property_widgets:

            range_value_str = ""
            property_widget = self.property_widgets[pw]
            min_val = property_widget.min_value
            max_val = property_widget.max_value
            if min_val is not None:
                range_value_str += "Min: " + str(min_val)
            if max_val is not None:
                if min_val is not None:
                    range_value_str += ", Max: " + str(max_val)
                else:
                    range_value_str += "Max: " + str(max_val)

            if pw == "enabled":
                self.property_widgets[pw].value = self.toggle_button
                self.assign_callbacks(controller, self.property_widgets[pw], "boolean")
            elif pw == "nof_acquisitions":
                self.property_widgets[pw].value = nof_acq_value
                nof_acq_info.setVisible(True)
                if min_val is not None or max_val is not None:
                    nof_acq_info.setToolTip(range_value_str)
                self.assign_callbacks(controller, self.property_widgets[pw], "integer")
            elif pw == "start_delay_s" or pw == "start_delay_ms":
                self.property_widgets[pw].value = self.start_delay_value
                if min_val is not None or max_val is not None:
                    start_delay_info.setVisible(True)
                    start_delay_info.setToolTip(range_value_str)
                else:
                    start_delay_info.setVisible(False)
                self.assign_callbacks(controller, self.property_widgets[pw], "integer")
            elif pw == "logging_period_s" or pw == "datalog_time_length":
                self.property_widgets[pw].value = self.log_period_value
                if min_val is not None or max_val is not None:
                    log_period_info.setVisible(True)
                    log_period_info.setToolTip(range_value_str)
                else:
                    log_period_info.setVisible(False)
                self.assign_callbacks(controller, self.property_widgets[pw], "integer")
            elif pw == "idle_period_s" or pw == "idle_time_length":
                if min_val is not None or max_val is not None:
                    idle_period_info.setVisible(True)
                    idle_period_info.setToolTip(range_value_str)
                else:
                    idle_period_info.setVisible(False)
                self.property_widgets[pw].value = self.idle_period_value
                self.assign_callbacks(controller, self.property_widgets[pw], "integer")

        automode_status = (
            self.controller.get_component_status(comp_name).get(comp_name).get("enabled")
        )
        self.controller.set_automode_enabled(
            automode_status if automode_status is not None else False
        )
        self.is_waiting_idle = False

        self.contents_widget.layout().addWidget(auto_mode_widget.frame_auto_mode)
        self.contents_widget.setVisible(True)

    @Slot(bool)
    def s_is_logging(self, status:bool, interface:int):
        """Enable/disable content frame and update title styling during logging.

        Parameters
        ----------
        status : bool
            True when logging is active; False otherwise.
        interface : int
            Active interface identifier supplied by the controller.

        Notes
        -----
        - When logging starts and automode is enabled, the title bar turns a
            darker green to signal the active state. When logging stops, the
            default style is restored and the countdown is stopped.
        """
        self.frame_contents.setEnabled(not status)
        if status and self.property_widgets["enabled"].value.checkState() == Qt.CheckState.Checked:
            self.title_frame.setStyleSheet("background-color: rgb(51, 71, 51);")
        else:
            self.title_frame.setStyleSheet("background-color: rgb(39, 44, 54);")
            self.digital_clock_timer.stop()
            self.title_label.setText("Automatic Mode")

    def toggle_button_toggled(self, status):
        """Propagate automode toggle changes to the controller.

        Parameters
        ----------
        status : bool
            True to enable automode; False to disable it.
        """
        self.controller.set_automode_enabled(status)

    def format_time(self, seconds):
        """Format seconds as HH:MM:SS.

        Parameters
        ----------
        seconds : int
            Number of seconds to format.

        Returns
        -------
        str
            Time string formatted as ``HH:MM:SS``.
        """
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_time(self):
        """Update the countdown title according to automode phase.

        Behavior
        ---------
        - If waiting to start logging, shows "LOG START in" countdown.
        - If logging and also waiting for idle, shows "IDLE" countdown.
        - If logging and not waiting for idle, shows "LOGGING" countdown.
        - If neither logging nor waiting, stops the timer and resets the title.
        """
        if self.is_waiting_logging:
            self.elapsed_time -= 1
            time_str = self.format_time(self.elapsed_time)
            self.title_label.setText(f"Automatic Mode ---> LOG START in: {time_str}")
        else:
            if self.is_logging:
                if self.is_waiting_idle:
                    self.elapsed_time -= 1
                    time_str = self.format_time(self.elapsed_time)
                    self.title_label.setText(f"Automatic Mode ---> IDLE: {time_str}")
                else:
                    self.elapsed_time -= 1
                    time_str = self.format_time(self.elapsed_time)
                    self.title_label.setText(f"Automatic Mode ---> LOGGING: {time_str}")
            else:
                if self.is_waiting_idle:
                    self.elapsed_time -= 1
                    time_str = self.format_time(self.elapsed_time)
                    self.title_label.setText(f"Automatic Mode ---> IDLE: {time_str}")
                else:
                    self.digital_clock_timer.stop()
                    self.title_label.setText("Automatic Mode")

    def is_waiting_auto_start(self, status):
        """Notify the widget that the system is waiting to start logging.

        Sets the countdown to the configured start delay and, when entering the
        waiting state, begins updating the timer every second.

        Parameters
        ----------
        status : bool
            True to enter waiting-to-start state; False to exit it.
        """
        self.elapsed_time = self.start_delay_value.value()
        self.is_waiting_logging = status
        if status:
            self.digital_clock_timer.start(1000)

    def is_idle_auto_start(self, status):
        """Notify the widget that the system is in idle between logs.

        Parameters
        ----------
        status : bool
            True to enter idle state and start countdown; False to exit it.
        """
        self.elapsed_time = self.idle_period_value.value()
        self.is_waiting_idle = status
        if status:
            self.digital_clock_timer.start(1000)

    def is_auto_started_inner(self, status):
        """Notify the widget that an automatic logging window has started.

        Parameters
        ----------
        status : bool
            True when the automode logging window begins; False when it ends.
        """
        self.elapsed_time = self.log_period_value.value()
        self.is_logging = status
        self.digital_clock_timer.start(1000)
