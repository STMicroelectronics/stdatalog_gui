#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    AnomalyDetectorWidget.py
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
Anomaly detection output widget built on top of `ClassifierOutputWidget`.

This widget displays the predicted anomaly class (and optional confidence) using the
rendering primitives prepared by `ClassifierOutputWidget`. It consumes batched data
from an internal queue, updates the highlighted class image, and refreshes the text
labels accordingly.

Responsibilities:
- Render anomaly classes with active/inactive images and styles.
- Optionally show class confidence as a percentage.
- Consume the newest sample from the queue on each update and repaint.
"""

from PySide6.QtWidgets import QLabel

from stdatalog_gui.Widgets.Plots.ClassifierOutputWidget import ClassifierOutputWidget

class AnomalyDetectorWidget(ClassifierOutputWidget):
    """Display anomaly detection results with optional confidence.

    Parameters
    ----------
    controller : QObject
        Application/controller object managing signals and timing.
    comp_name : str
        Component identifier associated with this output.
    comp_display_name : str
        Human-readable component name displayed in the UI.
    anomaly_classes : dict
        Mapping defining classes; semantics align with `ClassifierOutputWidget`.
        Typically maps class names to image resources used for active/inactive states.
    ai_tool : Any, optional
        Reference to the AI tool or runtime associated with this output.
    with_signal : bool, optional
        Whether to show a signal indicator, if supported by the base widget.
    with_confidence : bool, optional
        When True, displays class confidence as a percentage value.
    p_id : int, optional
        Plot/widget identifier used by the base implementation.
    parent : QWidget | None, optional
        Optional parent widget.
    left_label : str | None, optional
        Optional left-side label forwarded to the base class.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        anomaly_classes,
        ai_tool=None,
        with_signal=False,
        with_confidence=False,
        p_id=0,
        parent=None,
        left_label=None,
    ):
        super().__init__(
            controller,
            comp_name,
            comp_display_name,
            anomaly_classes,
            ai_tool,
            with_signal,
            with_confidence,
            p_id,
            parent,
            left_label,
        )
        self.timer_interval = 0.2

        self.ai_tool_category_label.setText("Anomaly Detection")

    def update_plot(self):
        """Consume new data from the queue and update UI accordingly.

        Notes
        -----
        - Expects the internal queue to provide items shaped like `(class_id, conf)`
            when `with_confidence` is True, otherwise `(class_id, _)`.
        - Highlights the predicted class, dims others, and updates confidence text.
        """
        if len(self._data[0]) > 0:
            # Extract all data from the queue (pop)
            one_reduced_t_interval = [self._data[0].popleft() for _i in range(len(self._data[0]))]
            ort = one_reduced_t_interval[0][0]
            if self.with_confidence:
                confidence = one_reduced_t_interval[0][1]
                self.class_confidence_value.setText(
                    str(round((confidence * 100.0), 2)) + " %"
                )
            class_id = int(ort)
            class_names = list(self.output_class_widget.keys())
            class_name = class_names[class_id]
            for cn in class_names:
                if cn == class_name:
                    self.output_class_widget[cn].out_class_image.setPixmap(
                        self.output_class_pixmaps[cn][0]
                    )
                    self.output_class_widget[cn].setEnabled(True)
                    self.output_class_widget[cn].findChild(
                        QLabel, "out_class_name"
                    ).setStyleSheet(
                        "color: #a4c238; font-size: 30px;"
                    )
                else:
                    self.output_class_widget[cn].out_class_image.setPixmap(
                        self.output_class_pixmaps[cn][1]
                    )
                    self.output_class_widget[cn].setEnabled(False)
                    self.output_class_widget[cn].findChild(
                        QLabel, "out_class_name"
                    ).setStyleSheet(
                        "color: #383D48; font-size: 20px;"
                    )
        self.app_qt.processEvents()
