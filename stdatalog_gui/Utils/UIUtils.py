#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    UIUtils.py
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
UI validation utilities for widgets across the GUI.

This module provides helper functions to validate text input values for different widget
types and to update their visual state accordingly. It centralizes style changes and
error tracking via the application controller.

Responsibilities:
- Validate values using the widget's assigned Qt validator.
- Apply valid/invalid styles to `QLineEdit`/`QSpinBox` consistently.
- Notify the controller to add/remove configuration errors tied to a widget id.
"""
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QSpinBox

from stdatalog_gui.UI.styles import STDTDL_LineEdit, STDTDL_SpinBox
from stdatalog_gui.Widgets.CommandWidget import CommandWidget
from stdatalog_gui.Widgets.PropertyWidget import PropertyWidget
from stdatalog_gui.Widgets.TelemetryWidget import TelemetryWidget

@staticmethod
def validate_value(controller, widget, text_value):
    """Validate an input value and update widget styles and controller errors.

    Parameters
    ----------
    controller : Any
        Application/controller instance that exposes `add_error_in_configuration` and
        `remove_error_in_configuration` for tracking configuration errors.
    widget : QWidget | PropertyWidget | TelemetryWidget | CommandWidget
        The widget whose value is being validated. For `PropertyWidget`,
        `TelemetryWidget`, or `CommandWidget`, their internal `validator` and `value`
        fields are used; for raw Qt widgets, `validator()` is invoked.
    text_value : str
        The input string to validate.

    Returns
    -------
    bool
        True if the value is acceptable according to the assigned validator; False
        otherwise.

    Side Effects
    ------------
    - Applies valid/invalid styles to the target widget.
    - Adds or removes the corresponding error entry from the controller.
    """
    if (
        isinstance(widget, PropertyWidget)
        or isinstance(widget, TelemetryWidget)
        or isinstance(widget, CommandWidget)
    ):
        validation_res = widget.validator.validate(text_value,0)
        widget_id = f"{widget.comp_name}.{widget.prop_name}"
        widget = widget.value
    else:
        validation_res = widget.validator().validate(text_value,0)
        widget_id = widget.__str__()

    if isinstance(validation_res, tuple):
        validation_res = validation_res[0]

    if validation_res == QValidator.State.Acceptable:
        if isinstance(widget, QSpinBox):
            widget.setStyleSheet(STDTDL_SpinBox.valid)
        else:
            widget.setStyleSheet(STDTDL_LineEdit.valid)
        controller.remove_error_in_configuration(widget_id)
        return True
    else:
        if isinstance(widget, QSpinBox):
            widget.setStyleSheet(STDTDL_SpinBox.invalid)
        else:
            widget.setStyleSheet(STDTDL_LineEdit.invalid)
        controller.add_error_in_configuration(widget_id)
        return False
