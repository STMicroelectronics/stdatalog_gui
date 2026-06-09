#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    TelemetryWidget.py
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
Telemetry widgets for presenting and updating DTDL-based properties in real time.

This module defines Qt widgets that render telemetry values according to DTDL schemas
used by the ST DTDL GUI. It builds simple editors for primitive types and composes
sub-widgets for object schemas, while listening to a controller signal to update UI
state when telemetry messages arrive.

Responsibilities:
- Render a property row with a label and an appropriate editor/control.
- Support primitive types (string, integer, double/float, boolean) and enums.
- Handle DTDL object schemas via nested `SubTelemetryWidget` compositions.
- Update UI in response to `sig_telemetry_received` from the controller.
"""

import os
import json
from json import JSONDecodeError
from PySide6.QtWidgets import (
    QLabel,
    QRadioButton,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QComboBox,
    QFrame,
    QGridLayout,
)
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui
from stdatalog_core.HSD_utils.DataClass import TypeEnum

class SubTelemetryWidget(QWidget):
    """Container for object-type telemetry sub-properties.

    Renders a titled sub-section that contains `TelemetryWidget` instances for each
    primitive sub-field of an object schema. Nested objects should be handled by the
    parent composition logic if needed.

    Parameters
    ----------
    comp_name : str
        Component name that owns the telemetry.
    object_name : str
        The name of the object to which the sub-fields belong.
    prop_name : str
        The display name/title for this sub-property group.
    fields : list
        The DTDL fields composing the object schema.
    is_writable : bool
        Whether the telemetry value is writable (affects UI enablement).
    parent : QWidget | None, optional
        Optional parent widget.
    """

    def __init__(
        self,
        comp_name,
        object_name,
        prop_name,
        fields,
        is_writable,
        parent=None,
    ):
        super().__init__(parent)
        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            SubTelemetryWidget, module="SubTelemetryWidget"
        )
        loader = QUiLoader()
        self.comp_name = comp_name
        self.object_name = object_name
        comp_config_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "component_config_widget.ui",
            ),
            parent,
        )
        title_frame = comp_config_widget.frame_component_config.findChild(
            QFrame, "frame_title"
        )

        title_label = title_frame.findChild(QPushButton, "label_title")
        title_label.setText(prop_name.upper())
        self.annotation_label = title_frame.findChild(QLabel, "label_annotation")
        self.annotation_label.setVisible(False)
        pushButton_show = title_frame.findChild(QPushButton, "pushButton_show")
        pushButton_show.setVisible(False)
        pushButton_pop_out = title_frame.findChild(QPushButton, "pushButton_pop_out")
        pushButton_pop_out.setVisible(False)
        radioButton_enable = title_frame.findChild(QRadioButton, "radioButton_enable")
        radioButton_enable.setVisible(False)
        self.contents_widget = comp_config_widget.frame_component_config.findChild(
            QFrame, "frame_contents"
        )

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(comp_config_widget)

        component_props_frame = QFrame()
        component_props_layout = QGridLayout()

        sub_widgets = []
        for i, f in enumerate(fields):
            schema_type = f.schema.value
            field_name = f.name
            field_dname = (
                f.display_name if isinstance(f.display_name, str) else f.display_name.en
            )
            sub_widget = TelemetryWidget(
                self.controller,
                comp_name,
                "None",
                self.object_name,
                field_dname,
                "",
                schema_type,
                is_writable,
                field_name,
                parent,
            )
            sub_widgets.append(sub_widget)
            component_props_layout.addWidget(sub_widget, i, 0)
        self.widget = MultiTelemetryWidget(sub_widgets)

        component_props_frame.setLayout(component_props_layout)
        self.contents_widget.layout().addWidget(component_props_frame)

class TelemetryWidget(QWidget):
    """Render a telemetry row and update on incoming messages.

    Based on the DTDL property schema, this widget creates a suitable editor/control and
    subscribes to the controller's `sig_telemetry_received` signal to update the value
    when telemetry arrives.

    Parameters
    ----------
    controller : QObject
        Controller exposing the signal `sig_telemetry_received(str)`.
    comp_name : str
        Name of the component that owns this property.
    comp_sem_type : Any
        Semantic type of the component (sensor/algorithm/etc.).
    prop_name : str
        Property name (or group name for objects).
    label : str
        Display label associated with the property.
    value : Any
        Initial value or enum entries (for enum types).
    prop_type : str
        DTDL schema type value (string, integer, double/float, boolean, enum, object).
    is_writable : bool
        Whether the property can be edited.
    field_name : str | None, optional
        For object sub-fields, identify the specific field this instance represents.
    parent : QWidget | None, optional
        Optional parent widget.

    Attributes
    ----------
    has_bounds : bool
        When legacy min/max/val object pattern is detected, indicates bound enforcement.
    label : QLabel
        The label shown before the editor/control.
    value : QWidget
        Editor/control corresponding to the property type.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_sem_type,
        prop_name,
        label,
        value,
        prop_type,
        is_writable,
        field_name=None,
        parent=None,
    ):
        super().__init__(parent)
        self.controller = controller
        self.controller.sig_telemetry_received.connect(self.s_telemetry_received)

        self.prop_type = prop_type
        self.comp_name = comp_name
        self.comp_sem_type = comp_sem_type
        self.prop_name = prop_name
        self.field_name = field_name #for (SubProperties) DTDL Object fields
        self.has_bounds = False
        self.label = QLabel(label)
        self.label.setFixedWidth(150)
        if self.prop_type == TypeEnum.STRING.value:
            self.value = QLineEdit(value)
        elif (
            self.prop_type == TypeEnum.DOUBLE.value or self.prop_type == TypeEnum.FLOAT.value
        ):
            self.validator = QDoubleValidator()
            self.value = QLineEdit(value)
            self.value.setValidator(self.validator)
        elif self.prop_type == TypeEnum.INTEGER.value:
            self.validator = QIntValidator()
            self.value = QLineEdit(value)
            self.value.setValidator(self.validator)
        elif self.prop_type == TypeEnum.BOOLEAN.value:
            self.value = QRadioButton(value)
        elif self.prop_type == TypeEnum.ENUM.value:
            self.value = QComboBox()
            for v in value:
                self.value.addItem(
                    v.display_name if isinstance(v.display_name, str) else v.display_name.en
                )
            self.value.setStyleSheet(
                "QComboBox::down-arrow { background-color : rgb(36, 40, 48); }"
            )
        elif self.prop_type == TypeEnum.OBJECT.value:
            keys = []
            for v in value:
                keys.append(v.name)
            if set(["max", "min", "val"]) == set(keys):
                if (
                    value[0].schema.value == TypeEnum.DOUBLE.value
                    or value[0].schema.value == TypeEnum.FLOAT.value
                ):
                    self.validator = QDoubleValidator(0, 1000, self)
                    self.value = QLineEdit("0")
                    self.has_bounds = True
                    self.value.setValidator(self.validator)
                elif value[0].schema.value == TypeEnum.INTEGER.value:
                    self.validator = QIntValidator(0, 1000, self)
                    self.value = QLineEdit("0")
                    self.has_bounds = True
                    self.value.setValidator(self.validator)
            else:
                self.value = SubTelemetryWidget(
                    comp_name, self.prop_name, label, value, is_writable, self
                )
        else:
            self.value = QLineEdit("UNKNOWN")

        self.setContentsMargins(20, 3, 0, 0)
        layout = QHBoxLayout(self)

        layout.setContentsMargins(20, 0, 20, 0)
        if (self.prop_type != TypeEnum.OBJECT.value or self.has_bounds):
            layout.addWidget(self.label)
        if not is_writable:  # if writable is None or False --> property is read-only
            self.value.setEnabled(False)
        layout.addWidget(self.value)

    def s_telemetry_received(self, pnpl_telemetry):
        """Handle telemetry messages and update the UI control accordingly.

        Parameters
        ----------
        pnpl_telemetry : str
            Raw telemetry payload. Expected to be a JSON string that decodes to a
            dictionary in the shape `{comp_name: {prop_name: value}}`.

        Notes
        -----
        - For combo boxes, sets the current index.
        - For radio buttons, assigns the raw value to the widget's `value` attribute
          as in the original implementation; behavior preserved.
        - For line edits, sets the text to the string representation of the value.
        """
        print(f"TelemetryWidget - INFO - Telemetry message: {pnpl_telemetry}")
        if len(pnpl_telemetry) > 0 and pnpl_telemetry != "\r\n":
            try:
                telemetry_dict = json.loads(pnpl_telemetry)
                if self.prop_name in telemetry_dict[self.comp_name]:
                    if isinstance(self.value, QComboBox):
                        self.value.setCurrentIndex(telemetry_dict[self.comp_name][self.prop_name])
                    elif isinstance(self.value, QRadioButton):
                        self.value.value = telemetry_dict[self.comp_name][self.prop_name]
                    elif isinstance(self.value, QLineEdit):
                        self.value.setText(str(telemetry_dict[self.comp_name][self.prop_name]))
            except JSONDecodeError:
                pass

class MultiTelemetryWidget:
    """Lightweight container tracking a list of telemetry sub-widgets.

    Parameters
    ----------
    widget_list : list[QWidget]
        Child widgets representing the object's sub-fields.

    Attributes
    ----------
    sub_widgets : list[QWidget]
        Stored list of sub-widgets for access by parents/controllers.
    """

    def __init__(self, widget_list) -> None:
        self.sub_widgets = widget_list
