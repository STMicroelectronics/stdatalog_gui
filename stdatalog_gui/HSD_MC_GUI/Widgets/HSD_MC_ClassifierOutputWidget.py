#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_ClassifierOutputWidget.py
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
Motor Control AI classifier output widget.

This module defines `HSD_MC_ClassifierOutputWidget`, a specialized plot widget that
displays AI classification outcomes for Motor Control demos. It builds a tiled layout of
class cards with images, highlights the currently detected class, optionally shows the
signal value and confidence, and manages minimal state-machine logic to smooth visual
transitions between classes.
"""

from collections import deque
import os
import struct
from enum import Enum

import numpy as np
from PySide6.QtCore import Qt, QPoint, Slot
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWebSockets import QWebSocket
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotLabel

class MCClassifierState(Enum):
    """
    Enumeration of internal states for Motor Control classifier output display.
    
    Attributes
    ----------
    MC_CLASSIFIER_INIT_RAMP_STATE : int
        Initial ramp-up state for smoothing.
    MC_CLASSIFIER_MONITOR_STATE : int
        Monitoring state awaiting stable classification.
    MC_CLASSIFIER_SHOW_CLASS_STATE : int
        State for showing the detected class.
    MC_CLASSIFIER_SAFE_CONDITION_STATE : int
        State for handling safe condition before resuming detection.
    """
    MC_CLASSIFIER_INIT_RAMP_STATE = 0
    MC_CLASSIFIER_MONITOR_STATE = 1
    MC_CLASSIFIER_SHOW_CLASS_STATE = 2
    MC_CLASSIFIER_SAFE_CONDITION_STATE = 3

class ActionType(Enum):
    """
    Enumeration of possible action types for Motor Control classifier demos.
    
    Attributes
    ----------
    NoChangeState : int
        Indicates no change in state.
    ShowSpeed : int
        Indicates a request to show speed.
    """
    ChangeState = 0
    ShowSpeed = 1

class ApplicationState(Enum):
    """
    Enumeration of possible application states for Motor Control classifier demos.
    
    Attributes
    ----------
    DefaultState : int
        The default or idle state of the application.
    BeltState : int
        State representing belt operation.
    MagnetState : int
        State representing magnet operation.
    VibrationState : int
        State representing vibration operation.
    RecoveryState : int
        State representing recovery operation.
    """
    DefaultState = 0
    BeltState = 1
    MagnetState = 2
    VibrationState = 3
    RecoveryState = 4

class HSD_MC_ClassifierOutputWidget(PlotWidget):
    """Widget rendering AI classification results with optional confidence display.

    Parameters
    ----------
    controller : STDTDL_Controller
        Application controller that drives timing and provides signals.
    comp_name : str
        Component name for the classifier output source.
    comp_display_name : str
        Title displayed in the widget header.
    out_classes : dict
        Mapping of output class label -> image path.
    mc_demo_images : dict, optional
        Optional mapping of demo state name -> image path for extra UI, unused by default.
    ai_tool : dict, optional
        Mapping of AI tool display name -> image path; when provided, a "Powered by" panel
        is shown with tool branding.
    with_signal : bool, optional
        Whether to show the raw signal value section.
    with_confidence : bool, optional
        Whether to show the confidence section.
    p_id : int, optional
        Plot identifier used by `PlotWidget`, by default 0.
    parent : QWidget, optional
        Optional parent widget.
    left_label : str, optional
        Optional left-side label in `PlotWidget`.

    Attributes
    ----------
    output_class_widget : dict
        Per-class card widget loaded from `.ui`, keyed by class label.
    output_class_pixmaps : dict
        Tuple of (enabled_pixmap, disabled_pixmap) keyed by class label.
    with_signal : bool
        Whether signal value area is visible.
    with_confidence : bool
        Whether confidence area is visible.
    timer_interval_ms : int
        Update period for visualization timer.
    sm_state : MCClassifierState
        Internal simple state machine for display smoothing.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        out_classes,
        mc_demo_images=None,
        ai_tool=None,
        with_signal=False,
        with_confidence=True,
        p_id=0,
        parent=None,
        left_label=None,
    ):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, left_label)

        # Clear PlotWidget inherited graphic elements
        # (mantaining all attributes, functions and signals)
        for i in reversed(range(self.layout().count())):
            self.layout().itemAt(i).widget().setParent(None)

        self._data = dict() # dict of queues
        self._data[0] = deque(maxlen=200000)

        self.parent_widget = parent

        self.out_classes = out_classes
        self.demo_images = mc_demo_images
        self.ai_tool = ai_tool
        self.output_class_widget = {}
        self.output_class_pixmaps = {}
        self.demo_class_widget = {}
        self.demo_class_pixmaps = {}

        self.with_signal = with_signal
        self.with_confidence = with_confidence

        self.is_settings_displayed = True
        self.timer_interval = 1
        self.is_plotting_out = True

        self.init_ramp_cnt = 0
        self.init_ramp_thr = 0
        self.plot_class_id = 0
        self.safe_condition_cnt = 0
        self.prev_detected_class_id = 0
        self.show_detected_class_cnt = 0
        self.show_detected_class_thr = 2
        self.safe_condition_thr = 30

        self.current_detected_class_id = 0
        self.safe_condition = False
        self.over_temperature = False
        self.sm_state = MCClassifierState.MC_CLASSIFIER_INIT_RAMP_STATE

        # New Customized Graphic layout
        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            HSD_MC_ClassifierOutputWidget, module="ClassifierOutputWidget"
        )
        loader = QUiLoader()
        self.plot_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "mc_classifier_output_widget.ui",
            ),
            parent,
        )
        title_frame = self.plot_widget.findChild(QFrame,"frame_title")
        self.frame_powered_by_ai = self.plot_widget.findChild(QFrame, "frame_powered_by_ai")
        self.contents_frame = self.plot_widget.findChild(QFrame,"frame_contents")
        frame_output_classes = self.plot_widget.findChild(QFrame,"frame_output_classes")
        # frame_states = self.plot_widget.findChild(QFrame,"frame_states")
        recovery_frame = self.plot_widget.findChild(QFrame,"recovery_frame")
        self.recovery_button = recovery_frame.findChild(QPushButton,"recovery_button")
        self.recovery_button.setEnabled(False)
        self.recovery_button.clicked.connect(self.clicked_fix_motor_fault_button)
        self.pushButton_plot_settings = title_frame.findChild(
            QPushButton,
            "pushButton_plot_settings"
        )

        self.frame_application_states = self.plot_widget.findChild(
            QFrame,
            "frame_application_states"
        )
        self.frame_application_states.setVisible(False)

        self.out_info = self.contents_frame.findChild(QFrame,"out_class_info_frame")

        self.out_class_signal_frame = self.out_info.findChild(QFrame, "out_class_signal_frame")
        self.class_signal_value = self.out_info.findChild(QLabel,"out_class_signal_value")
        if not with_signal:
            self.out_class_signal_frame.setVisible(False)
            if not with_confidence:
                self.out_info.setVisible(False)
            else:
                self.out_info.setVisible(True)

        self.out_class_confidence_frame = self.out_info.findChild(
            QFrame,
            "out_class_confidence_frame"
        )
        self.class_confidence_value = self.out_info.findChild(QLabel,"out_class_confidence_value")
        if not with_confidence:
            self.out_class_confidence_frame.setVisible(False)
            if not with_signal:
                self.out_info.setVisible(False)
            else:
                self.out_info.setVisible(True)

        if self.ai_tool is not None:
            self.pushButton_close_settings = self.frame_powered_by_ai.findChild(
                QPushButton, "pushButton_close_settings"
            )
            self.pushButton_close_settings.clicked.connect(self.clicked_close_settings)

            self.pushButton_plot_settings.setVisible(True)
            self.pushButton_plot_settings.clicked.connect(self.clicked_plot_settings_button)

            ai_tool_name = list(ai_tool.keys())[0]
            ai_tool_name_label = self.frame_powered_by_ai.findChild(QLabel,"ai_tool_name")
            ai_tool_name_label.setText(ai_tool_name)
            self.ai_tool_category_label = self.frame_powered_by_ai.findChild(
                QLabel,
                "ai_tool_category"
            )
            self.ai_tool_category_label.setText("Classification")
            ai_tool_pixmap = QPixmap(self.ai_tool[ai_tool_name])
            ai_tool_image:QLabel = self.frame_powered_by_ai.findChild(
                QLabel, "ai_tool_image"
            )
            ai_tool_image.setPixmap(ai_tool_pixmap)
        else:
            self.frame_powered_by_ai.setVisible(False)

        title_label = PlotLabel(f"{self.comp_display_name}")
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        title_frame.layout().addWidget(title_label)

        for output_class in self.out_classes:
            self.output_class_widget[output_class] = loader.load(
                os.path.join(
                    os.path.dirname(stdatalog_gui.__file__),
                    "UI",
                    "output_class_widget.ui",
                ),
                parent,
            )
            class_name = self.output_class_widget[output_class].findChild(QLabel,"out_class_name")
            class_name.setText(output_class)
            if output_class != "ISPU": # NOTE Done for ISPU CES2023 Demo purposes
                self.output_class_widget[output_class].out_class_name.setStyleSheet(
                    "color: #383D48; font-size: 20px;"
                )
            else:
                self.output_class_widget[output_class].out_class_name.setStyleSheet(
                    "color: #3cb4e6; font-size: 20px;"
                )
            class_pixmap = QPixmap(self.out_classes[output_class])
            class_image:QLabel = self.output_class_widget[output_class].findChild(
                QLabel, "out_class_image"
            )
            enabled_pixmap = class_pixmap
            disabled_pixmap = self.setOpacity(class_pixmap, 0.1)
            self.output_class_pixmaps[output_class] = (enabled_pixmap, disabled_pixmap)
            if output_class != "ISPU": # NOTE Done for ISPU CES2023 Demo purposes
                class_image.setPixmap(disabled_pixmap)
            else:
                class_image.setPixmap(enabled_pixmap)

            frame_output_classes.layout().addWidget(self.output_class_widget[output_class])

        # for demo_images in self.demo_images:
        #     self.demo_class_widget[demo_images] = loader.load(os.path.join(os.path.dirname(stdatalog_gui.__file__),"UI","output_class_widget.ui"), parent)
        #     class_name = self.demo_class_widget[demo_images].findChild(QLabel,"out_class_name")
        #     class_name.setText(demo_images)
        #     if demo_images != "ISPU": #NOTE Done for ISPU CES2023 Demo purposes
        #         self.demo_class_widget[demo_images].out_class_name.setStyleSheet("color: #383D48; font-size: 20px;")
        #     else:
        #         self.demo_class_widget[demo_images].out_class_name.setStyleSheet("color: #3cb4e6; font-size: 20px;")
        #     class_pixmap = QPixmap(self.demo_images[demo_images])
        #     class_image:QLabel = self.demo_class_widget[demo_images].findChild(QLabel,"out_class_image")
        #     enabled_pixmap = class_pixmap
        #     disabled_pixmap = self.setOpacity(class_pixmap, 0.1)
        #     self.demo_class_pixmaps[demo_images] = (enabled_pixmap, disabled_pixmap)
        #     if demo_images != "ISPU": #NOTE Done for ISPU CES2023 Demo purposes
        #         class_image.setPixmap(disabled_pixmap)
        #     else:
        #         class_image.setPixmap(enabled_pixmap)

        #     frame_states.layout().addWidget(self.demo_class_widget[demo_images])

        self.timer_interval_ms = self.timer_interval * 700
        self.layout().addWidget(self.plot_widget)

    # WebSocket DEBUG
    # def on_connected(self):
    #     print("Connected to server")
    # def on_message_received(self, message):
    #     print(f"Received message: {message}")

    def send_message(self, message):
        """Send a text message over the internal WebSocket (if connected)."""
        self.socket.sendTextMessage(message)

    def setOpacity(self, pixmap:QPixmap, perc):
        """Return a copy of `pixmap` with a given opacity applied.

        Parameters
        ----------
        pixmap : QPixmap
            Original image.
        perc : float
            Opacity value in [0, 1], where 0 is fully transparent.

        Returns
        -------
        QPixmap
            New pixmap with opacity applied.
        """
        new_pix = QPixmap(pixmap.size())
        new_pix.fill(Qt.transparent)
        painter = QPainter(new_pix)
        painter.setOpacity(perc)
        painter.drawPixmap(QPoint(), pixmap)
        painter.end()
        return new_pix

    def update_plot_characteristics(self, plot_params):
        """Update widget characteristics for new plot parameters (reserved)."""

    @Slot(bool)
    def s_is_detecting(self, status: bool):
        """Start/stop timer while detecting mode is toggled."""
        if status:
            if not self.timer.isActive():
                self.timer.start(self.timer_interval_ms)
        else:
            if self.timer.isActive():
                self.timer.stop()

    @Slot()
    def s_is_logging(self, status: bool):
        """Start/stop timer while logging mode is toggled."""
        if status:
            if not self.timer.isActive():
                self.timer.start(self.timer_interval_ms)
        else:
            if self.timer.isActive():
                self.timer.stop()

    def update_plot(self):
        """Process queued outputs and update class highlighting and confidence.

        Expects queued entries as arrays, where the first element is the predicted class
        id, and the following bytes encode a 32-bit float confidence value.
        """
        if len(self._data[0]) > 0:
            if not self.is_plotting_out:
                self.is_plotting_out = True
            # Extract all data from the queue (pop)
            one_reduced_t_interval = [self._data[0].popleft() for _i in range(len(self._data[0]))]
            one_reduced_t_interval_int = one_reduced_t_interval[0].astype(np.int32)
            predicted_class = one_reduced_t_interval_int[0]

            probability_byte = one_reduced_t_interval_int[1:]
            prob_bytes_result = struct.pack('<4B', *probability_byte)
            prediction_probability = struct.unpack('<f', prob_bytes_result)[0]

            #predicted_class = int(one_reduced_t_interval[0][0])
            #prediction_probability = one_reduced_t_interval[0][1]

            if self.with_confidence:
                confidence = prediction_probability
                self.class_confidence_value.setText(str(round((confidence * 100.0), 2)) + " %")

            # run classifier sm
            self.classifier_sm(predicted_class)
        else:
            if self.is_plotting_out:
                for cn in list(self.output_class_widget.keys()):
                    self.output_class_widget[cn].out_class_image.setPixmap(
                        self.output_class_pixmaps[cn][1]
                    )
                    self.output_class_widget[cn].setEnabled(False)
                    self.output_class_widget[cn].findChild(
                        QLabel,"out_class_name").setStyleSheet("color: #383D48; font-size: 20px;")
                self.is_plotting_out = False
                if self.with_confidence:
                    self.class_confidence_value.setText("--- %")
        self.app_qt.processEvents()

    def add_data(self, data):
        """Append a new output frame to the processing queue."""
        self._data[0].append(data[0])

    def plot_classifier_class(self, class_id):
        """Highlight the given class and dim all others.

        Parameters
        ----------
        class_id : int
            Index of the class to highlight, based on `out_classes` ordering.
        """
        class_names = list(self.output_class_widget.keys())
        class_name = class_names[class_id]
        for cn in class_names:
            if cn == class_name:
                self.output_class_widget[cn].out_class_image.setPixmap(
                    self.output_class_pixmaps[cn][0]
                )
                self.output_class_widget[cn].setEnabled(True)
                self.output_class_widget[cn].findChild(QLabel, "out_class_name").setStyleSheet(
                    "color: #a4c238; font-size: 30px;"
                )
            else:
                self.output_class_widget[cn].out_class_image.setPixmap(
                    self.output_class_pixmaps[cn][1]
                )
                self.output_class_widget[cn].setEnabled(False)
                self.output_class_widget[cn].findChild(QLabel, "out_class_name").setStyleSheet(
                    "color: #383D48; font-size: 20px;"
                )

    def classifier_sm(self, class_id):
        """Minimal state machine to stabilize class display transitions.

        Parameters
        ----------
        class_id : int
            Detected class id from the AI output.
        """
        self.safe_condition = False
        self.prev_detected_class_id = self.current_detected_class_id
        self.current_detected_class_id = class_id

        if self.sm_state == MCClassifierState.MC_CLASSIFIER_INIT_RAMP_STATE:
            #Set normal condition during motor init ramp
            self.plot_class_id = 0
            if self.init_ramp_cnt >= self.init_ramp_thr:
                #go to monitor condition
                self.sm_state = MCClassifierState.MC_CLASSIFIER_MONITOR_STATE
                self.init_ramp_cnt = 0
            self.init_ramp_cnt += 1

        elif self.sm_state == MCClassifierState.MC_CLASSIFIER_MONITOR_STATE:

            if self.prev_detected_class_id == self.current_detected_class_id:
                self.show_detected_class_cnt +=1
                if self.show_detected_class_cnt >= self.show_detected_class_thr:
                    self.show_detected_class_cnt = 0
                    self.plot_class_id = self.current_detected_class_id
            else:
                self.show_detected_class_cnt = 0

            self.plot_classifier_class(self.plot_class_id)

    def disableAllClassificationWidget(self):
        """Disable and dim all classification cards."""
        class_names = list(self.output_class_widget.keys())
        for cn in class_names:
            self.output_class_widget[cn].out_class_image.setPixmap(self.output_class_pixmaps[cn][1])
            self.output_class_widget[cn].setEnabled(False)
            self.output_class_widget[cn].findChild(QLabel, "out_class_name").setStyleSheet(
                "color: #383D48; font-size: 20px;"
            )

    def disableAllWidget(self):
        """Disable all UI elements managed by this widget."""
        self.disableAllClassificationWidget()

    @Slot()
    def clicked_plot_settings_button(self):
        """Toggle visibility of the Powered-by-AI settings panel."""
        self.is_settings_displayed = not self.is_settings_displayed
        if self.is_settings_displayed:
            self.frame_powered_by_ai.setVisible(True)
        else:
            self.frame_powered_by_ai.setVisible(False)

    @Slot()
    def clicked_close_settings(self):
        """Hide the Powered-by-AI settings panel."""
        self.is_settings_displayed = False
        self.frame_powered_by_ai.setVisible(False)

    def clicked_fix_motor_fault_button(self):
        """Reset recovery UI counters and disable the recovery button."""
        self.recovery_button.setEnabled(False)
        self.safe_condition_cnt = 0
