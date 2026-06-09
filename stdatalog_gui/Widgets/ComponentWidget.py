#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    ComponentWidget.py
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
"""Component configuration widget for the ST DTDL GUI.

This module defines `ComponentWidget`, a comprehensive UI element used to view and
modify component properties, send commands, and visualize telemetry. It wires
controller signals to UI behavior, supports docking/undocking, and coordinates plot
visibility.

Responsibilities:
- Render per-component properties, commands, and telemetry based on DTDL content.
- Validate input values and send PnPL commands to the device.
- Reflect component status updates coming from the controller.
- Provide controls for packing/unpacking content and popping out/in the widget.

Design Notes:
- Built with PySide6 and dynamically loads its UI via `QUiLoader`.
- Avoids behavioral changes; only documentation and minor formatting when needed.
- Follows the project's 100-character line width where practical.
"""

from abc import abstractmethod
import os
from functools import partial

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QScreen, QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QSpinBox,
    QRadioButton,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFrame,
    QGridLayout,
)
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui
from stdatalog_gui.UI.styles import STDTDL_PushButton
from stdatalog_gui.Utils import UIUtils
from stdatalog_gui.Widgets.ToggleButton import ToggleButton
from stdatalog_pnpl.DTDL.device_template_model import ContentSchema, ContentType, RequestSchema, ResponseSchema
from stdatalog_pnpl.PnPLCmd import PnPLCMDManager
from stdatalog_gui.Widgets.PropertyWidget import PropertyWidget, SubPropertyWidget
from stdatalog_gui.Widgets.CommandWidget import CommandField, CommandWidget
from stdatalog_gui.Widgets.TelemetryWidget import TelemetryWidget
from stdatalog_core.HSD_utils.DataClass import TypeEnum
from stdatalog_gui.STDTDL_Controller import ComponentType

import stdatalog_gui.UI.icons 
from pkg_resources import resource_filename
icon_pop_in_img_path = resource_filename('stdatalog_gui.UI.icons', 'pop-in_18dp_E8EAED.svg')
icon_pop_out_img_path = resource_filename('stdatalog_gui.UI.icons', 'pop-out_18dp_E8EAED.svg')

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class ComponentWidget(QWidget):
    """UI widget for configuring and controlling a single component.

    Parameters
    ----------
    controller : Any
        Application controller exposing signals and device APIs.
    comp_name : str
        Component identifier.
    comp_display_name : str
        Human-readable component name.
    comp_sem_type : Any
        Semantic type (e.g., `ComponentType.SENSOR`).
    comp_contents : list
        DTDL content elements defining properties/commands/telemetry.
    c_id : int, optional
        Sequential component ID for layout/indexing (default 0).
    parent : QWidget | None, optional
        Optional parent widget.

    Attributes
    ----------
    is_docked : bool
        Whether the widget is docked in the page layout.
    is_packed : bool
        Whether content area is collapsed/packed.
    is_plot_displayed : bool | None
        Current plot visibility state.
    property_widgets : dict[str, PropertyWidget]
        Mapping from property name to property widget instances.
    command_widgets : dict[str, CommandWidget]
        Mapping from command name to command widget instances.
    contents_widget : QFrame
        Container for dynamic component controls.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        comp_sem_type,
        comp_contents,
        c_id=0,
        parent=None,
    ):
        """Initialize component widget UI and connect controller signals.

        Parameters
        ----------
        controller : Any
            Application controller reference.
        comp_name : str
            Component name.
        comp_display_name : str
            Display name for the component.
        comp_sem_type : Any
            Semantic type, see `ComponentType`.
        comp_contents : list
            DTDL content definitions for properties/commands/telemetry.
        c_id : int, optional
            Component ID (default 0).
        parent : QWidget | None, optional
            Optional parent widget.
        """
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.controller.sig_component_updated.connect(self.s_component_updated)
        self.controller.sig_logging.connect(self.s_is_logging)
        self.controller.sig_is_auto_started.connect(self.s_auto_started)
        self.controller.sig_detecting.connect(self.s_is_detecting)

        self.is_docked = True
        self.is_packed = True
        self.is_plot_displayed = None

        self.original_idx = 0
        self.c_id = c_id
        self.comp_name = comp_name
        self.comp_display_name = comp_display_name
        self.comp_sem_type = comp_sem_type
        self.comp_contents = comp_contents

        self.setWindowTitle("Connection")

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            ComponentWidget, module="ComponentWidget"
        )
        loader = QUiLoader()
        comp_config_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "component_config_widget.ui",
            ),
            parent,
        )
        self.frame_component_config = comp_config_widget.frame_component_config
        self.title_frame = comp_config_widget.frame_component_config.findChild(
            QFrame, "frame_title"
        )
        self.title_label = self.title_frame.findChild(QPushButton, "label_title")
        self.title_label.setText(comp_name.upper())
        self.title_label.setText(self.comp_display_name)
        self.title_label.clicked.connect(self.clicked_show_button)
        self.title_label.setCursor(Qt.PointingHandCursor)

        self.annotation_label = self.title_frame.findChild(QLabel, "label_annotation")
        self.annotation_label.setVisible(False)

        self.pushButton_show = self.title_frame.findChild(QPushButton, "pushButton_show")
        self.pushButton_show.clicked.connect(self.clicked_show_button)

        self.pushButton_show_plot = self.title_frame.findChild(QPushButton, "pushButton_show_plot")
        self.pushButton_show_plot.clicked.connect(self.clicked_show_plot_button)
        self.pushButton_show_plot.setVisible(False)

        icon_pop_in_pixmap = QPixmap(icon_pop_in_img_path)
        self.icon_pop_in = QIcon(icon_pop_in_pixmap)
        icon_pop_out_pixmap = QPixmap(icon_pop_out_img_path)
        self.icon_pop_out = QIcon(icon_pop_out_pixmap)
        self.pushButton_pop_out: QPushButton = self.title_frame.findChild(
            QPushButton, "pushButton_pop_out"
        )
        self.pushButton_pop_out.clicked.connect(self.clicked_pop_out_button)
        self.radioButton_enable = self.title_frame.findChild(
            QRadioButton, "radioButton_enable"
        )
        self.radioButton_enable.setVisible(False)
        self.contents_widget = comp_config_widget.frame_component_config.findChild(
            QFrame, "frame_contents"
        )

        self.contents_widget.setVisible(False)

        #Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(comp_config_widget)

        self.property_widgets = dict()
        self.command_widgets = dict()

        # Frame Properties
        component_props_frame = QFrame()
        component_props_layout = QGridLayout()
        component_props_layout.setVerticalSpacing(3)
        for i, p in enumerate(self.comp_contents):
            pc_display_name = (
                p.display_name if isinstance(p.display_name, str) else p.display_name.en
            )
            cont_type = ""
            if isinstance(p.type, ContentType):
                cont_type = p.type.name
            else:
                cont_type = [
                    x for x in p.type if x.name in ["PROPERTY", "COMMAND", "TELEMETRY"]
                ][0].name

            if cont_type == 'PROPERTY':
                if p.name != "st_ble_stream" or comp_sem_type == ComponentType.ACTUATOR:
                    widget = PropertyWidget(comp_name, comp_sem_type, p)
                    enum_values = None
                    if isinstance(p.schema, ContentSchema):
                        schema_type = p.schema.type.value.lower()
                        if p.schema.type.value == "Enum":
                            enum_values = p.schema.enum_values
                    else:
                        schema_type = p.schema

                    self.assign_callbacks(
                        controller,
                        widget,
                        schema_type,
                        p.schema.value_schema if schema_type == TypeEnum.ENUM.value else None,
                        enum_values,
                    )
                    if (
                        comp_sem_type == ComponentType.SENSOR
                        or comp_sem_type == ComponentType.ALGORITHM
                        or comp_sem_type == ComponentType.ACTUATOR
                    ) and p.name == "enable":
                        self.radioButton_enable.setVisible(True)
                        self.radioButton_enable.toggled.connect(
                            partial(self.sensor_component_enabled, widget)
                        )
                    component_props_layout.addWidget(widget, i, 0)
                    # add widget to the Property widget dictionary
                    self.property_widgets[p.name] = widget

            elif cont_type == 'COMMAND':
                req_fields = []
                resp_fields = []
                try:  # complex object schema
                    if p.request is not None or p.response is not None:
                        if p.request is not None:
                            if isinstance(p.request.schema, RequestSchema):
                                if p.request.schema.type.value == "Object":
                                    if (
                                        "fields" in p.request.schema.to_dict()
                                    ):  # more than one field in command
                                        for f in p.request.schema.fields:
                                            field_label = (
                                                f.display_name
                                                if isinstance(f.display_name, str)
                                                else f.display_name.en
                                            )
                                            if f.schema is not None:
                                                req_fields.append(
                                                    CommandField(
                                                        f.name, f.schema.value, field_label, ""
                                                    )
                                                )
                                            else:
                                                try:
                                                    schema_type = (
                                                        f.dtmi_dtdl_property_schema_2.type.value.lower()
                                                    )
                                                    req_fields.append(
                                                        CommandField(
                                                            f.name,
                                                            schema_type,
                                                            field_label,
                                                            f.dtmi_dtdl_property_schema_2.enum_values,
                                                        )
                                                    )
                                                except AttributeError:
                                                    log.error(
                                                        f"Malformed commmand field: {field_label}"
                                                    )
                                        widget = CommandWidget(
                                            self.controller,
                                            comp_name,
                                            self.comp_sem_type,
                                            p.name,
                                            p.request.name,
                                            req_fields,
                                            command_label=pc_display_name,
                                        )
                                    else:
                                        req_fields.append(
                                            CommandField(
                                                p.request.name,
                                                p.request.schema,
                                                pc_display_name,
                                                "",
                                            )
                                        )
                                        widget = CommandWidget(
                                            self.controller,
                                            comp_name,
                                            self.comp_sem_type,
                                            p.name,
                                            None,
                                            req_fields,
                                            command_label=pc_display_name,
                                        )
                                elif p.request.schema.type.value == "Enum":
                                    if "enumValues" in p.request.schema.to_dict():
                                        for e in p.request.schema.enum_values:
                                            enum_label = (
                                                e.display_name
                                                if isinstance(e.display_name, str)
                                                else e.display_name.en
                                            )
                                            req_fields.append(
                                                CommandField(
                                                    p.request.name,
                                                    TypeEnum.ENUM.value,
                                                    enum_label,
                                                    e.enum_value,
                                                )
                                            )
                                        widget = CommandWidget(
                                            self.controller,
                                            comp_name,
                                            self.comp_sem_type,
                                            p.name,
                                            None,
                                            req_fields,
                                            command_label=pc_display_name,
                                        )
                            else:
                                # log.debug("No Object, nor Enum!", p.request.schema.value)
                                field_label = (
                                    p.request.display_name
                                    if isinstance(p.request.display_name, str)
                                    else p.request.display_name.en
                                )
                                req_fields.append(
                                    CommandField(
                                        p.request.name,
                                        p.request.schema.value,
                                        field_label,
                                        "",
                                    )
                                )
                                widget = CommandWidget(
                                    self.controller,
                                    comp_name,
                                    self.comp_sem_type,
                                    p.name,
                                    None,
                                    req_fields,
                                    command_label=pc_display_name,
                                )

                            if p.response is not None:
                                if isinstance(p.response.schema, ResponseSchema):
                                    if p.response.schema.type.value == "Object":
                                        if (
                                            "fields" in p.response.schema.to_dict()
                                        ):  # more than one field in command
                                            for f in p.response.schema.fields:
                                                field_label = (
                                                    f.display_name
                                                    if isinstance(f.display_name, str)
                                                    else f.display_name.en
                                                )
                                                if f.schema is not None:
                                                    resp_fields.append(
                                                        CommandField(
                                                            f.name, f.schema.value, field_label, ""
                                                        )
                                                    )
                                                else:
                                                    try:
                                                        schema_type = (
                                                            f.dtmi_dtdl_property_schema_2.type.value.lower()
                                                        )
                                                        resp_fields.append(
                                                            CommandField(
                                                                f.name,
                                                                schema_type,
                                                                field_label,
                                                                f.dtmi_dtdl_property_schema_2.enum_values,
                                                            )
                                                        )
                                                    except AttributeError:
                                                        log.error(
                                                            f"Malformed commmand field: {field_label}"
                                                        )
                                            widget = CommandWidget(
                                                self.controller,
                                                comp_name,
                                                self.comp_sem_type,
                                                p.name,
                                                p.request.name,
                                                req_fields,
                                                p.response.name,
                                                resp_fields,
                                                pc_display_name,
                                            )
                                        else:
                                            resp_fields.append(
                                                CommandField(
                                                    p.response.name,
                                                    p.response.schema,
                                                    pc_display_name,
                                                    "",
                                                )
                                            )
                                            widget = CommandWidget(
                                                self.controller,
                                                comp_name,
                                                self.comp_sem_type,
                                                p.name,
                                                None,
                                                req_fields,
                                                None,
                                                resp_fields,
                                                pc_display_name,
                                            )
                                    elif p.response.schema.type.value == "Enum":
                                        if "enumValues" in p.response.schema.to_dict():
                                            for e in p.response.schema.enum_values:
                                                enum_label = (
                                                    e.display_name
                                                    if isinstance(e.display_name, str)
                                                    else e.display_name.en
                                                )
                                                resp_fields.append(
                                                    CommandField(
                                                        p.response.name,
                                                        TypeEnum.ENUM.value,
                                                        enum_label,
                                                        e.enum_value,
                                                    )
                                                )
                                            widget = CommandWidget(
                                                self.controller,
                                                comp_name,
                                                self.comp_sem_type,
                                                p.name,
                                                None,
                                                req_fields,
                                                None,
                                                resp_fields,
                                                pc_display_name,
                                            )
                                else:
                                    field_label = (
                                        p.response.display_name
                                        if isinstance(p.response.display_name, str)
                                        else p.response.display_name.en
                                    )
                                    resp_fields.append(
                                        CommandField(
                                            p.response.name,
                                            p.response.schema.value,
                                            field_label,
                                            "",
                                        )
                                    )
                                    widget = CommandWidget(
                                        self.controller,
                                        comp_name,
                                        self.comp_sem_type,
                                        p.name,
                                        None,
                                        req_fields,
                                        None,
                                        resp_fields,
                                        pc_display_name,
                                    )
                        else:
                            if (
                                p.response is not None
                            ):  # req is None and resp is not None
                                if isinstance(p.response.schema, ResponseSchema):
                                    if p.response.schema.type.value == "Object":
                                        if (
                                            "fields" in p.response.schema.to_dict()
                                        ):  # more than one field in command
                                            for f in p.response.schema.fields:
                                                field_label = (
                                                    f.display_name
                                                    if isinstance(f.display_name, str)
                                                    else f.display_name.en
                                                )
                                                if f.schema is not None:
                                                    resp_fields.append(
                                                        CommandField(
                                                            f.name, f.schema.value, field_label, ""
                                                        )
                                                    )
                                                else:
                                                    try:
                                                        schema_type = (
                                                            f.dtmi_dtdl_property_schema_2.type.value.lower()
                                                        )
                                                        resp_fields.append(
                                                            CommandField(
                                                                f.name,
                                                                schema_type,
                                                                field_label,
                                                                f.dtmi_dtdl_property_schema_2.enum_values,
                                                            )
                                                        )
                                                    except AttributeError:
                                                        log.error(
                                                            f"Malformed commmand field: {field_label}"
                                                        )
                                            widget = CommandWidget(
                                                self.controller,
                                                comp_name,
                                                self.comp_sem_type,
                                                p.name,
                                                None,
                                                None,
                                                p.response.name,
                                                resp_fields,
                                                pc_display_name,
                                            )
                                        else:
                                            resp_fields.append(
                                                CommandField(
                                                    p.response.name,
                                                    p.response.schema,
                                                    pc_display_name,
                                                    "",
                                                )
                                            )
                                            widget = CommandWidget(
                                                self.controller,
                                                comp_name,
                                                self.comp_sem_type,
                                                p.name,
                                                None,
                                                None,
                                                None,
                                                resp_fields,
                                                pc_display_name,
                                            )
                                    elif p.response.schema.type.value == "Enum":
                                        if "enumValues" in p.response.schema.to_dict():
                                            for e in p.response.schema.enum_values:
                                                enum_label = (
                                                    e.display_name
                                                    if isinstance(e.display_name, str)
                                                    else e.display_name.en
                                                )
                                                resp_fields.append(
                                                    CommandField(
                                                        p.response.name,
                                                        TypeEnum.ENUM.value,
                                                        enum_label,
                                                        e.enum_value,
                                                    )
                                                )
                                            widget = CommandWidget(
                                                self.controller,
                                                comp_name,
                                                self.comp_sem_type,
                                                p.name,
                                                None,
                                                None,
                                                None,
                                                resp_fields,
                                                pc_display_name,
                                            )
                                else:
                                    field_label = (
                                        p.response.display_name
                                        if isinstance(p.response.display_name, str)
                                        else p.response.display_name.en
                                    )
                                    resp_fields.append(
                                        CommandField(
                                            p.response.name,
                                            p.response.schema.value,
                                            field_label,
                                            "",
                                        )
                                    )
                                    widget = CommandWidget(
                                        self.controller,
                                        comp_name,
                                        self.comp_sem_type,
                                        p.name,
                                        None,
                                        None,
                                        None,
                                        resp_fields,
                                        pc_display_name,
                                    )
                    else:
                        widget = CommandWidget(
                            self.controller,
                            comp_name,
                            self.comp_sem_type,
                            p.name,
                            None,
                            req_fields,
                            command_label=pc_display_name,
                        )

                except AttributeError:
                    pass
                widget.setContentsMargins(0, 0, 0, 0)
                component_props_layout.addWidget(widget, i, 0)
                # add widget to the Property widget dictionary
                self.command_widgets[p.name] = widget
            elif cont_type == 'TELEMETRY':
                try:  # complex object schema
                    if p.schema.type.value == "Enum":
                        schema_type = p.schema.type.value.lower()
                        widget = TelemetryWidget(
                            self.controller,
                            comp_name,
                            comp_sem_type,
                            p.name,
                            pc_display_name,
                            p.schema.enum_values,
                            p.schema.type.value.lower(),
                            p.writable,
                        )
                    elif p.schema.type.value == "Object":
                        schema_type = p.schema.type.value.lower()
                        widget = TelemetryWidget(
                            self.controller,
                            comp_name,
                            comp_sem_type,
                            p.name,
                            pc_display_name,
                            p.schema.fields,
                            p.schema.type.value.lower(),
                            p.writable,
                        )
                except AttributeError:  # primitive type schema
                    schema_type = p.schema
                    widget = TelemetryWidget(
                        self.controller,
                        comp_name,
                        comp_sem_type,
                        p.name,
                        pc_display_name,
                        "",
                        p.schema,
                        p.writable,
                    )

                component_props_layout.addWidget(widget, i, 0)
                # add widget to the Property widget dictionary
                self.property_widgets[p.name] = widget

        component_props_frame.setLayout(component_props_layout)
        component_props_frame.setFixedHeight(component_props_layout.sizeHint().height())
        self.contents_widget.layout().addWidget(component_props_frame)

    def assign_callbacks(
        self, controller, widget, schema_type, schema_value=None, enum_values=None
    ):
        """Wire UI events to handlers based on schema type.

        Parameters
        ----------
        controller : Any
            Application controller reference.
        widget : PropertyWidget | SubPropertyWidget
            Target widget to configure.
        schema_type : str
            Schema type from `TypeEnum`.
        schema_value : Any, optional
            Optional value schema (for Enums/Objects).
        enum_values : list | None, optional
            Optional enum values list.
        """
        if schema_type == TypeEnum.STRING.value:
            widget.value.textChanged.connect(
                partial(UIUtils.validate_value, controller, widget)
            )
            widget.value.editingFinished.connect(partial(self.send_string_command, widget))
        elif schema_type == TypeEnum.DOUBLE.value or schema_type == TypeEnum.FLOAT.value:
            widget.value.textChanged.connect(
                partial(UIUtils.validate_value, controller, widget)
            )
            widget.value.editingFinished.connect(partial(self.send_double_command, widget))
        elif schema_type == TypeEnum.INTEGER.value:
            widget.value.textChanged.connect(
                partial(UIUtils.validate_value, controller, widget)
            )
            if isinstance(widget.value, QSpinBox):
                widget.value.valueChanged.connect(partial(self.send_int_command, widget))
            else:
                widget.value.editingFinished.connect(partial(self.send_int_command, widget))
        elif schema_type == TypeEnum.BOOLEAN.value:
            widget.value.toggled.connect(partial(self.boolean_prop_triggered, widget))
        elif schema_type == TypeEnum.ENUM.value:
            if schema_value.value == TypeEnum.INTEGER.value:
                widget.value.activated.connect(
                    partial(self.send_enum_number_command, widget, enum_values)
                )
            if schema_value.value == TypeEnum.STRING.value:
                widget.value.activated.connect(
                    partial(self.send_enum_string_command, widget, enum_values)
                )
        elif schema_type == TypeEnum.OBJECT.value:
            if isinstance(widget, PropertyWidget):
                if widget.has_bounds:
                    if isinstance(widget.validator, QDoubleValidator):
                        widget.value.textChanged.connect(
                            partial(UIUtils.validate_value, controller, widget)
                        )
                        widget.value.editingFinished.connect(
                            partial(self.send_double_command, widget)
                        )
                    elif isinstance(widget.validator, QIntValidator):
                        widget.value.textChanged.connect(
                            partial(UIUtils.validate_value, controller, widget)
                        )
                        widget.value.editingFinished.connect(
                            partial(self.send_int_command, widget)
                        )
                else:
                    for w in widget.value.widget.sub_widgets:
                        if isinstance(w, PropertyWidget):
                            self.assign_callbacks(controller, w, w.prop_type)
                        else:
                            self.assign_callbacks(controller, w, TypeEnum.OBJECT.value)
            elif isinstance(widget, SubPropertyWidget):
                for sw in widget.widget.sub_widgets:
                    self.assign_callbacks(controller, sw, sw.prop_type)

    @Slot()
    def clicked_browse_dt_button(self):
        """Open a file dialog to select and load a DTDL device template.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        json_filter = "JSON Device Template files (*.json *.JSON)"
        filepath = QFileDialog.getOpenFileName(filter=json_filter)
        if filepath[0]:  # Check if a file was actually selected (not cancelled)
            self.input_file_path = filepath[0]
            self.dt_value.setText(self.input_file_path)
            self.controller.load_local_device_template(self.input_file_path)

    @Slot()
    def clicked_show_button(self):
        """Toggle visibility of the component contents area.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if self.is_packed:
            self.unpack_contents_widget()
            self.is_packed = False
        else:
            self.pack_contents_widget()
            self.is_packed = True

    @Slot()
    def clicked_show_plot_button(self):
        """Toggle visibility of the plot widget associated with this component.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        if self.is_plot_displayed:
            self.hide_plot_widget()
        else:
            self.show_plot_widget()

    def hide_plot_widget(self):
        """Hide the plot widget and update control state."""
        self.controller.hide_plot_widget(self.comp_name)
        self.pushButton_show_plot.setVisible(True)
        self.pushButton_show_plot.setStyleSheet(STDTDL_PushButton.valid)
        self.is_plot_displayed = False

    def show_plot_widget(self):
        """Show the plot widget and update control state."""
        self.controller.show_plot_widget(self.comp_name)
        self.pushButton_show_plot.setVisible(True)
        self.pushButton_show_plot.setStyleSheet(STDTDL_PushButton.green)
        self.is_plot_displayed = True

    def enable_plot_control(self):
        """Enable the plot visibility toggle control."""
        self.pushButton_show_plot.setEnabled(True)

    def disable_plot_control(self):
        """Disable the plot visibility toggle control."""
        self.pushButton_show_plot.setEnabled(False)

    @Slot()
    def clicked_pop_out_button(self):
        """Pop out or re-dock the component widget depending on current state."""
        if self.is_docked:
            self.pop_out_widget()
            self.is_docked = False
        else:
            self.pop_in_widget()
            self.is_docked = True

    @Slot(int, str, dict)
    def s_component_updated(self, comp_name: str, comp_status: dict):
        """React to a component status update and refresh visible properties.

        Parameters
        ----------
        comp_name : str
            Name of the component being updated.
        comp_status : dict
            Status values for properties/contents.

        Returns
        -------
        None
        """
        if comp_name == self.comp_name:
            log.debug(f"Component: {comp_name}")
            if comp_status is not None:
                comp_type = comp_status.get("c_type")
                if comp_type is not None:
                    if (
                        comp_type == ComponentType.SENSOR.value
                        or comp_type == ComponentType.ALGORITHM.value
                        or comp_type == ComponentType.ACTUATOR.value
                    ):
                        enable = comp_status.get("enable")
                        if enable is not None:
                            if enable is True:
                                self.controller.enabled_stream_comp_set.add(comp_name)
                            else:
                                self.controller.enabled_stream_comp_set.discard(comp_name)

                            if len(self.controller.enabled_stream_comp_set) == 0:
                                self.controller.disable_start_log_button()
                            else:
                                self.controller.enable_start_log_button()

                for cont_name, cont_value in comp_status.items():
                    cont_dtdl = next(
                        (c for c in self.comp_contents if c.name == cont_name), None
                    )
                    if cont_dtdl is not None:
                        if isinstance(cont_dtdl.schema, ContentSchema):
                            if cont_dtdl.schema.type.value == "Enum":
                                value_schema = cont_dtdl.schema.value_schema
                                if value_schema.value == "string":
                                    cv = [
                                        ev
                                        for ev in cont_dtdl.schema.enum_values
                                        if ev.enum_value == str(cont_value)
                                    ]
                                else:
                                    cv = [
                                        ev
                                        for ev in cont_dtdl.schema.enum_values
                                        if ev.enum_value == cont_value
                                    ]
                                if len(cv) > 0:
                                    cv_display_name = cv[0].display_name
                                    cont_value = (
                                        cv_display_name
                                        if isinstance(cv_display_name, str)
                                        else cv_display_name.en
                                    )
                            # elif cont_dtdl.schema.type.value == "Object":
                            #     for cont_name, cont_value in comp_status[cont_name].items():
                            #         self.s_component_updated()
                    if isinstance(cont_value, dict):
                        log.debug(f" - Content: {cont_name}")
                        for key in cont_value:
                            log.debug(f"  -- {key}: {cont_value[key]}")
                            self.update_property_widget(
                                comp_name,
                                self.comp_sem_type,
                                cont_name,
                                key,
                                cont_value[key],
                            )
                    elif isinstance(cont_value, list):
                        log.warning(
                            f"Property type not supported. (comp: {comp_name}, cont:{cont_name}) "
                            "status not updated"
                        )
                    else:
                        log.debug(f'- {cont_name}: {cont_value}')
                        self.update_property_widget(
                            comp_name, self.comp_sem_type, cont_name, None, cont_value
                        )
                log.info(f"Component {comp_name} Updated correctly")
            else:
                log.warning(f"No status to update for {comp_name} Component")

    @Slot(bool, int)
    @abstractmethod
    def s_is_logging(self, status: bool, interface: int):
        """Hook for logging state changes; override in subclasses as needed.

        Parameters
        ----------
        status : bool
            Logging state.
        interface : int
            Optional interface index.

        Returns
        -------
        None
        """
        if self.controller.auto_started == False:
            # to override in inherithed components which need to react to a
            # logging state change event"""
            self.radioButton_enable.setEnabled(not status)

    @Slot(bool)
    def s_auto_started(self, status: bool):
        """
        Handle auto-start state changes to adjust UI interactivity.
        to override in inherithed components which need to react to a logging
        state change event
        """
        self.radioButton_enable.setEnabled(not status)

    @Slot(bool, int)
    @abstractmethod
    def s_is_detecting(self, status: bool):
        """
        Hook for detecting state changes; override in subclasses as needed.
        to override in inherithed components which need to react to a detecting
        state change event
        """

    def update_property_widget(
        self, comp_name, comp_sem_type, prop_name, sub_prop_name, cont_value
    ):
        """Update a property widget with the latest value from component status.

        Parameters
        ----------
        comp_name : str
            Component name.
        comp_sem_type : Any
            Semantic type (sensor/algorithm/actuator).
        prop_name : str
            Property name to update.
        sub_prop_name : str | None
            Sub-field name for object properties.
        cont_value : Any
            New value to set.

        Returns
        -------
        None
        """
        if prop_name in self.property_widgets.keys():
            w = self.property_widgets[prop_name]

            if comp_sem_type == ComponentType.SENSOR:
                if prop_name == "sensor_annotation":
                    self.__set_component_annotation(cont_value)

            if isinstance(w, PropertyWidget):
                if {w.comp_name, w.prop_name} == {comp_name, prop_name}:
                    if w.prop_type != TypeEnum.OBJECT.value:
                        self.__update_Property_widget_value(w, cont_value)
                        if w.prop_type == TypeEnum.BOOLEAN.value:
                            if prop_name == "enable" and (
                                comp_sem_type == ComponentType.SENSOR
                                or comp_sem_type == ComponentType.ALGORITHM
                                or comp_sem_type == ComponentType.ACTUATOR
                            ):
                                self.radioButton_enable.blockSignals(True)
                                self.radioButton_enable.setChecked(cont_value)
                                self.radioButton_enable.blockSignals(False)
                    else:
                        if w.has_bounds:
                            if sub_prop_name == "min":
                                w.validator.setBottom(cont_value)
                            elif sub_prop_name == "max":
                                w.validator.setTop(cont_value)
                            elif sub_prop_name == "val":
                                self.__update_Property_widget_value(w, cont_value)
                        else:
                            for ww in w.value.widget.sub_widgets:
                                if isinstance(ww, PropertyWidget):
                                    if ww.field_name == sub_prop_name:
                                        if isinstance(cont_value, ContentSchema):
                                            print(cont_value)
                                        else:
                                            self.__update_Property_widget_value(ww, cont_value)
                                else:
                                    if ww.prop_name[-1] == sub_prop_name:
                                        for sp in ww.widget.sub_widgets:
                                            self.__update_Property_widget_value(
                                                sp, cont_value[sp.field_name]
                                            )

    def __update_Property_widget_value(self, widget, value):
        """Set a widget's value according to its property type and formatting rules."""
        if widget.prop_type == TypeEnum.STRING.value:
            widget.value.setText(value)
        elif (
            widget.prop_type == TypeEnum.INTEGER.value
            or widget.prop_type == TypeEnum.DOUBLE.value
            or widget.prop_type == TypeEnum.FLOAT.value
        ):
            if isinstance(widget.value, QSpinBox):
                widget.value.setValue(value)
            else:
                if (
                    widget.prop_type == TypeEnum.DOUBLE.value
                    or widget.prop_type == TypeEnum.FLOAT.value
                ):
                    if widget.decimal_places is not None:
                        widget.value.setText(str(round(value, widget.decimal_places)))
                    else:
                        widget.value.setText(str(value))
                else:
                    widget.value.setText(str(value))
        elif widget.prop_type == TypeEnum.ENUM.value:
            item_id = 0
            for i in range(widget.value.count()):
                if widget.value.itemText(i) == str(value):
                    item_id = i
            widget.value.setCurrentIndex(item_id)

        elif widget.prop_type == TypeEnum.BOOLEAN.value:
            try:
                widget.value.blockSignals(True)
                if isinstance(widget.value, ToggleButton):
                    widget.value.setCheckState(
                        Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
                    )
                    widget.value.start_transition(value)
                else:
                    widget.value.setChecked(value)
                widget.value.blockSignals(False)
            except Exception:
                pass
        elif widget.prop_type == TypeEnum.OBJECT.value:
            if widget.has_bounds:
                widget.value.blockSignals(True)
                widget.value.setText(str(value))
                widget.value.blockSignals(False)
        else:
            log.warning("Unrecognized Property Type")

    def send_string_command(self, widget: PropertyWidget):
        """Send a PnPL string property command and trigger status refresh."""
        json_string = PnPLCMDManager.create_set_property_cmd(
            widget.comp_name,
            widget.prop_name,
            widget.value.text()
            if widget.field_name is None
            else {widget.field_name: widget.value.text()},
        )
        self.controller.send_command(json_string)
        if widget.comp_sem_type == ComponentType.SENSOR:
            comp_sensor_name = widget.comp_name.split('_')[0]
            for cn in list(self.controller.components_dtdl.keys()):
                if comp_sensor_name in cn:
                    self.controller.update_component_status(cn, ComponentType.SENSOR)
        else:
            self.controller.update_component_status(widget.comp_name, widget.comp_sem_type)

    def send_int_command(self, widget: PropertyWidget, value=None):
        """Send a PnPL integer property command and trigger status refresh."""
        int_value = int(value) if value is not None else int(widget.value.text())
        json_string = PnPLCMDManager.create_set_property_cmd(
            widget.comp_name,
            widget.prop_name,
            int_value if widget.field_name is None else {widget.field_name: int_value},
        )
        self.controller.send_command(json_string)
        if widget.comp_sem_type == ComponentType.SENSOR:
            comp_sensor_name = widget.comp_name.split('_')[0]
            for cn in list(self.controller.components_dtdl.keys()):
                if comp_sensor_name in cn:
                    self.controller.update_component_status(cn, ComponentType.SENSOR)
        else:
            self.controller.update_component_status(widget.comp_name, widget.comp_sem_type)

    def send_double_command(self, widget: PropertyWidget):
        """Send a PnPL double/float property command and trigger status refresh."""
        json_string = PnPLCMDManager.create_set_property_cmd(
            widget.comp_name,
            widget.prop_name,
            float(widget.value.text())
            if widget.field_name is None
            else {widget.field_name: float(widget.value.text())},
        )
        self.controller.send_command(json_string)
        if widget.comp_sem_type == ComponentType.SENSOR:
            comp_sensor_name = widget.comp_name.split('_')[0]
            for cn in list(self.controller.components_dtdl.keys()):
                if comp_sensor_name in cn:
                    self.controller.update_component_status(cn, ComponentType.SENSOR)
        else:
            self.controller.update_component_status(widget.comp_name, widget.comp_sem_type)

    def sensor_component_enabled(self, widget: PropertyWidget, status):
        """Reflect enable state changes while respecting current logging state."""
        get_logging_status = getattr(self.controller, "get_logging_status", None)
        if get_logging_status is not None and callable(get_logging_status):
            is_logging = self.controller.get_logging_status()
            if not is_logging:
                widget.value.setChecked(status)
        else:
            widget.value.setChecked(status)

    def boolean_prop_triggered(self, widget: PropertyWidget, status):
        """Handle boolean property toggles and keep the enable radio in sync."""
        if widget.prop_name == "enable" and self.radioButton_enable.isVisible():
            self.radioButton_enable.blockSignals(True)
            self.radioButton_enable.setChecked(status)
            self.radioButton_enable.blockSignals(False)
        self.send_bool_command(widget, status)

    def send_bool_command(self, widget: PropertyWidget, status):
        """Send a PnPL boolean property command and trigger status refresh."""
        json_string = PnPLCMDManager.create_set_property_cmd(
            widget.comp_name,
            widget.prop_name,
            status if widget.field_name is None else {widget.field_name: status},
        )
        self.controller.send_command(json_string)
        if widget.comp_sem_type == ComponentType.SENSOR:
            comp_sensor_name = widget.comp_name.split('_')[0]
            for cn in list(self.controller.components_dtdl.keys()):
                if comp_sensor_name in cn:
                    self.controller.update_component_status(cn, ComponentType.SENSOR)
        else:
            self.controller.update_component_status(widget.comp_name, widget.comp_sem_type)

    def send_enum_number_command(self, widget: PropertyWidget, enum_values, index):
        """Send a PnPL enum (numeric) property command and trigger status refresh."""
        int_value = enum_values[index].enum_value
        json_string = PnPLCMDManager.create_set_property_cmd(
            widget.comp_name, widget.prop_name, int_value
        )
        self.controller.send_command(json_string)
        if widget.comp_sem_type == ComponentType.SENSOR:
            comp_sensor_name = widget.comp_name.split('_')[0]
            for cn in list(self.controller.components_dtdl.keys()):
                if comp_sensor_name in cn:
                    self.controller.update_component_status(cn, ComponentType.SENSOR)
        else:
            self.controller.update_component_status(widget.comp_name, widget.comp_sem_type)

    def send_enum_string_command(self, widget: PropertyWidget, enum_values, index):
        """Send a PnPL enum (string) property command and trigger status refresh."""
        str_value = enum_values[index].enum_value
        json_string = PnPLCMDManager.create_set_property_cmd(
            widget.comp_name, widget.prop_name, str_value
        )
        self.controller.send_command(json_string)
        if widget.comp_sem_type == ComponentType.SENSOR:
            comp_sensor_name = widget.comp_name.split('_')[0]
            for cn in list(self.controller.components_dtdl.keys()):
                if comp_sensor_name in cn:
                    self.controller.update_component_status(cn, ComponentType.SENSOR)
        else:
            self.controller.update_component_status(widget.comp_name, widget.comp_sem_type)

    def closeEvent(self, event):
        """Ensure the widget is re-docked when the window is closed.
        
        Parameters
        ----------
        event : QCloseEvent
            Close event triggering the handler.
            (Unused parameter, kept for signature consistency)
            
        Returns
        -------
        None
        """
        _ = event  # Unused parameter
        self.pop_in_widget()
        self.is_docked = True

    def pop_out_widget(self):
        """Undock the widget, convert to a dialog window, and center on screen."""
        self.pushButton_pop_out.setIcon(self.icon_pop_in)
        self.original_idx = self.parent.layout().indexOf(self)
        self.setWindowFlags(Qt.Dialog | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        center = QScreen.availableGeometry(QApplication.primaryScreen()).center()
        geo = self.frameGeometry()
        geo.moveCenter(center)
        self.move(geo.topLeft())
        self.show()
        self.unpack_contents_widget()
        self.is_packed = False

    def pop_in_widget(self):
        """Re-dock the widget back into its original layout position."""
        self.pushButton_pop_out.setIcon(self.icon_pop_out)
        self.setWindowFlags(Qt.Widget)
        self.parent.layout().insertWidget(self.original_idx, self)

    def unpack_contents_widget(self):
        """Expand the contents area to reveal component controls."""
        self.contents_widget.setVisible(True)

    def pack_contents_widget(self):
        """Collapse the contents area to hide component controls."""
        self.contents_widget.setVisible(False)

    def __set_component_annotation(self, note):
        """Display an annotation note for the component header.

        Parameters:
        - note (str): Annotation text.

        Returns:
        - None
        """
        self.annotation_label.setText(note)
        self.annotation_label.setVisible(True)
