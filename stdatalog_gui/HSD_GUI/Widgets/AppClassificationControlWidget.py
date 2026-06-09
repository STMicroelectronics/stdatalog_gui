# ******************************************************************************
#  * @file    AppClassificationControlWidget.py
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
Classification control widget to manage learning and detection phases.

This module defines `AppClassificationControlWidget`, a small controller UI that
drives a learn-then-detect workflow for a classification application. It sends
PnPL commands to start/stop learning, shows a progress bar based on a configurable
learning duration, and toggles detection on completion. It also coordinates plot
startup/shutdown to visualize detection results.

Highlights
----------
- Starts learning via PnPL command and animates progress with a `QTimer`.
- Stops learning automatically when progress reaches 100% and enables detection.
- Toggles detection on/off, updating plots accordingly.
- Binds UI widgets (buttons, spin box, progress bar) to controller actions.
"""

import os

from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtWidgets import QFrame, QPushButton, QProgressBar, QSpinBox
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

from stdatalog_pnpl.PnPLCmd import PnPLCMDManager
from stdatalog_gui.Widgets.ComponentWidget import ComponentWidget
import stdatalog_gui
import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class AppClassificationControlWidget(ComponentWidget):
    """Controller widget for classification learning and detection.

    Parameters
    ----------
    controller : object
        Application controller exposing PnPL command sending, detection control,
        and plot start/stop APIs.
    comp_contents : list
        Component content descriptors used by the base widget.
    comp_name : str, optional
        Component identifier, by default "log_controller".
    comp_display_name : str, optional
        Title shown in the UI, by default "App Controller".
    comp_sem_type : str, optional
        Semantic type passed to the base `ComponentWidget`, by default "other".
    c_id : int, optional
        Component id for the base widget, by default 0.
    parent : QWidget | None, optional
        Parent widget.
    """
    def __init__(
        self,
        controller,
        comp_contents,
        comp_name="log_controller",
        comp_display_name="App Controller",
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
        self.is_detecting = False

        # clear all widgets in contents_widget layout (contents)
        for i in reversed(range(self.contents_widget.layout().count())):
            self.contents_widget.layout().itemAt(i).widget().deleteLater()

        self.setWindowTitle(comp_display_name)

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            AppClassificationControlWidget,
            module="AppClassificationControlWidget",
        )
        loader = QUiLoader()
        log_control_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "HSD_GUI",
                "UI",
                "app_classification_control.ui",
            )
        )
        frame_contents = log_control_widget.frame_log_control.findChild(
            QFrame,
            "frame_contents",
        )

        # Start/Stop Learning PushButton
        self.start_learning_button = frame_contents.findChild(
            QPushButton,
            "start_learning",
        )
        self.start_learning_button.clicked.connect(self.clicked_start_learning_button)

        # Start/Stop Detection
        self.start_detection_button = frame_contents.findChild(
            QPushButton,
            "start_detection",
        )
        self.start_detection_button.clicked.connect(self.clicked_start_detection_button)
        self.start_detection_button.setEnabled(False)

        # Learning Time SpinBox
        self.learning_time_spinBox = log_control_widget.frame_log_control.findChild(
            QSpinBox,
            "learning_time_spinBox",
        )
        self.learning_time_spinBox.setMaximum(600)
        self.learning_time_spinBox.setValue(15)

        # Learning progress Bar
        self.learning_progress_bar = log_control_widget.frame_log_control.findChild(
            QProgressBar,
            "learning_progress_bar",
        )

        self.learning_progres_time_ms = 100
        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.update_learning_progress_bar)
        self.learning_progress_bar_val = 0

        self.layout().setContentsMargins(0,0,0,0)
        self.contents_widget.layout().setContentsMargins(15,0,15,0)
        self.contents_widget.layout().addWidget(log_control_widget.frame_log_control)
        self.contents_widget.setVisible(True)

    @Slot()
    def clicked_start_detection_button(self):
        """Start or stop detection and toggle plot streaming.

        Behavior
        ---------
        - When not detecting, starts detection via controller and disables the
            learning button.
        - When detecting, requests a component status update, stops detection,
            and re-enables the learning button.
        """
        if not self.is_detecting:
            self.controller.start_detect()
            self.start_learning_button.setEnabled(False)
        else:
            self.controller.update_component_status("acquisition_info")
            self.controller.stop_detect()
            self.start_learning_button.setEnabled(True)

    @Slot()
    def clicked_start_learning_button(self):
        """Send the start-learning command and begin the progress countdown.

        Steps
        -----
        - Builds and sends the PnPL "start_learning" command.
        - Disables detection until learning completes.
        - Initializes and starts the progress timer based on the configured
            learning time.
        """
        start_learning_msg = PnPLCMDManager.create_command_cmd(
            "log_controller",
            "start_learning",
        )
        self.controller.send_command(start_learning_msg)
        self.start_detection_button.setEnabled(False)
        self.learning_progress_bar_val = 0
        self.start_learning_button.setEnabled(False)
        self.learning_progres_time_ms = self.learning_time_spinBox.value() * 10
        self.timer.start(self.learning_progres_time_ms)
        self.start_learning_button.setText("Learning ...")

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        """Update UI and plots according to detection state.

        Parameters
        ----------
        status : bool
            True when detection is running; False otherwise.
        """
        if status:
            self.start_detection_button.setText("Stop Detection")
            self.is_detecting = True
            self.controller.start_plots()
        else:
            self.start_detection_button.setText("Start Detection")
            self.is_detecting = False
            self.controller.stop_plots()

    def update_learning_progress_bar(self):
        """Advance the learning progress and finalize when complete.

        When the bar reaches 100%, stops the timer, sends the PnPL
        "stop_learning" command, resets the learning button, and enables
        detection before triggering an initial detect.
        """
        self.learning_progress_bar_val += 1
        self.learning_progress_bar.setValue(self.learning_progress_bar_val)
        if self.learning_progress_bar_val == 100:
            self.timer.stop()
            stop_learning_msg = PnPLCMDManager.create_command_cmd(
                "log_controller",
                "stop_learning",
            )
            self.controller.send_command(stop_learning_msg)
            self.start_learning_button.setText("Start Learning")
            self.start_learning_button.setEnabled(False)
            self.start_detection_button.setEnabled(True)
            self.controller.start_detect()
