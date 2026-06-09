#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    CommandWidget.py
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
Command Widget and helpers for sending PnPL commands and uploading files.

This module provides a Qt widget used to render dynamic command UIs for DTDL/PnPL
components. It supports two main scenarios:

- Generic commands with request/response fields, automatically mapped to suitable
    Qt editors (line edits, radio buttons, combo boxes) based on the DTDL type.
- File-upload commands (e.g., MLC and ISPU use cases) where the user is prompted to
    browse for one or more files before sending the command. For AI sensors, an
    intermediate loading window is shown and device components are refreshed when the
    upload completes.

The widget uses the project UI template `send_command_widget.ui` loaded at runtime via
`QUiLoader` to keep presentation separated from logic. It coordinates with a
controller providing device-level operations such as `send_command`, `upload_file`,
`upload_mlc_ucf_file`, and `upload_ispu_ucf_file`.

Typical usage:

1. Construct the widget by passing the controller, component/command metadata, and
    request/response field descriptors.
2. For non-file commands, the widget builds a JSON command payload through
    `PnPLCMDManager.create_command_cmd(...)` and forwards it to the controller.
3. For file commands, the widget handles file selection and invokes the appropriate
    controller upload function. AI-related uploads trigger a short loading dialog and a
    delayed refresh of other affected components.

No business logic is changed by this widget; it merely offers a convenient and
consistent UI. All public methods include thorough docstrings with Parameters/Returns
sections using the style already used in the project.
"""

from dataclasses import dataclass
from functools import partial
import json
import os

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
    QFileDialog,
    QApplication,
)
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtCore import QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection
from stdatalog_pnpl.PnPLCmd import PnPLCMDManager
import stdatalog_gui
from stdatalog_gui.UI.styles import STDTDL_PushButton
from stdatalog_gui.Widgets.LoadingWindow import LoadingWindow
from stdatalog_core.HSD_utils.DataClass import TypeEnum

UCF_AND_JSON_FILE_FILTER = (
    "Supported files (*.ucf *.UCF *.json *.JSON);;"
    "UCF Configuration files (*.ucf *.UCF);;"
    "JSON files (*.json *.JSON)"
)

class CommandField:
    """Simple container describing a single command field.

    Parameters
    ----------
    f_name : str
        Field name as expected by the device command schema.
    f_type : str | int
        DTDL-like type identifier (mapped from `TypeEnum` values).
    f_label : str
        Human-friendly label to be shown in the UI.
    f_value : Any
        Default value or enumeration value index/text.

    Notes
    -----
    This class is intentionally lightweight (not a dataclass) to reflect the
    structure coming from the PnPL/DTDL description.
    """

    def __init__(self, f_name, f_type, f_label, f_value):
        self.f_name = f_name
        self.f_type = f_type
        self.f_label = f_label
        self.f_value = f_value

@dataclass
class MLC_CmdValues:
    """Identifiers for MLC file-upload command fields.

    Attributes
    ----------
    mlc_config : str
        Key used to store/load the MLC configuration file (ucf,json) path in `loaded_file_path`.
    """

    mlc_config: str = "mlc_config"

@dataclass
class ISPU_CmdValues:
    """Identifiers for ISPU file-upload command fields.

    Attributes
    ----------
    ispu_ucf : str
        Key used to store/load the ISPU UCF file path in `loaded_file_path`.
    ispu_json : str
        Key used to store/load the ISPU JSON file path in `loaded_file_path`.
    """

    ispu_ucf = "ispu_ucf"
    ispu_json = "ispu_json"
    ispu_output_json = "ispu_output_json"

class CommandWidget(QWidget):
    """Qt widget that renders a dynamic UI to send a PnPL command.

    Parameters
    ----------
    controller : Any
        Controller providing methods like `send_command`, `upload_file`,
        `upload_mlc_ucf_file`, and `upload_ispu_ucf_file`, plus
        `update_component_status`.
    comp_name : str
        Component name (e.g., sensor or algorithm component instance).
    comp_sem_type : str
        Component semantic type used by the controller when refreshing status.
    command_name : str
        Command identifier (e.g., "load_file", "set_property").
    request_name : str
        Outer JSON object name for request fields, when applicable.
    request_fields : list[CommandField] | None
        Sequence of request field descriptors. Can be an empty list.
    response_name : str | None, optional
        Outer JSON object name for response fields, when the device nests
        responses (default is None for flat responses).
    response_fields : list[CommandField] | None, optional
        Sequence of response field descriptors (default is empty list).
    command_label : str | None, optional
        Optional title to display in the widget header.
    parent : QWidget | None, optional
        Parent widget.

    Notes
    -----
    If the command involves file uploads and the component refers to AI sensors
    (e.g., names containing ``_mlc`` or ``_ispu``), the send button is initially
    disabled until all required files are selected.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_sem_type,
        command_name,
        request_name,
        request_fields,
        response_name=None,
        response_fields=None,
        command_label=None,
        parent=None,
    ):
        super().__init__(parent)
        self.app = QApplication.instance()
        self.controller = controller
        self.comp_name = comp_name
        self.comp_sem_type = comp_sem_type
        self.command_name = command_name
        self.request_name = request_name
        self.request_fields = request_fields if request_fields is not None else []
        self.response_name = response_name
        self.response_fields = response_fields if response_fields is not None else []
        self.req_values = dict()
        self.resp_values = dict()
        self.req_labels = dict()
        self.resp_labels = dict()
        self.loaded_file_path = {}
        self.loaded_file_value = {}
        self.file_id_list = []

        # Register as a custom widget for Qt Designer integration.
        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            CommandWidget, module="CommandWidget"
        )
        loader = QUiLoader()
        command_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__), "UI", "send_command_widget.ui"
            ),
            parent,
        )
        command_title_frame = command_widget.frame_component_config.findChild(
            QFrame, "frame_title"
        )

        command_fields_widget = command_widget.frame_component_config.findChild(
            QFrame, "frame_contents"
        )
        self.command_send_button = command_widget.findChild(QPushButton, "pushButton")
        self.command_send_button.clicked.connect(
            partial(self.clicked_send_command_button, self, self.file_id_list)
        )
        if "_mlc" in self.comp_name or "_ispu" in self.comp_name:
            self.command_send_button.setEnabled(False)
            self.command_send_button.setStyleSheet(STDTDL_PushButton.invalid)
        else:
            self.command_send_button.setEnabled(True)
            self.command_send_button.setStyleSheet(STDTDL_PushButton.green)

        if command_label is not None:
            command_title_label = command_title_frame.findChild(QLabel, "label_title")
            command_title_label.setText(command_label)

        layout = QVBoxLayout(self)
        command_fields_frame = QFrame()
        if "load_file" not in command_name:
            # Build UI editors for request/response fields based on their types.
            for f in self.request_fields:
                self.req_labels[f.f_name] = QLabel(f.f_label)
                self.req_labels[f.f_name].setFixedWidth(150)
                if f.f_type == TypeEnum.STRING.value:
                    self.req_values[f.f_name] = QLineEdit(f.f_value)
                elif (
                    f.f_type == TypeEnum.DOUBLE.value or f.f_type == TypeEnum.FLOAT.value
                ):
                    self.validator = QDoubleValidator()
                    self.req_values[f.f_name] = QLineEdit(f.f_value)
                    self.req_values[f.f_name].setValidator(self.validator)
                elif f.f_type == TypeEnum.INTEGER.value:
                    self.validator = QIntValidator(0, 1000, self)
                    self.req_values[f.f_name] = QLineEdit(f.f_value)
                    self.req_values[f.f_name].setValidator(self.validator)
                elif f.f_type == TypeEnum.BOOLEAN.value:
                    self.req_values[f.f_name] = QRadioButton(f.f_value)
                elif f.f_type == TypeEnum.ENUM.value:
                    if not f.f_name in self.req_values:
                        self.req_values[f.f_name] = QComboBox()
                    self.req_values[f.f_name].addItem(f.f_label)
                else:
                    self.req_values[f.f_name] = QLineEdit("UNKNOWN")

                self.req_values[f.f_name].setFixedWidth(200)

            for f in self.response_fields:
                self.resp_labels[f.f_name] = QLabel(f.f_label)
                self.resp_labels[f.f_name].setFixedWidth(150)
                if f.f_type == TypeEnum.STRING.value:
                    self.resp_values[f.f_name] = QLineEdit(f.f_value)
                elif (
                    f.f_type == TypeEnum.DOUBLE.value or f.f_type == TypeEnum.FLOAT.value
                ):
                    self.validator = QDoubleValidator()
                    self.resp_values[f.f_name] = QLineEdit(f.f_value)
                    self.resp_values[f.f_name].setValidator(self.validator)
                elif f.f_type == TypeEnum.INTEGER.value:
                    self.validator = QIntValidator(0, 1000, self)
                    self.resp_values[f.f_name] = QLineEdit(f.f_value)
                    self.resp_values[f.f_name].setValidator(self.validator)
                elif f.f_type == TypeEnum.BOOLEAN.value:
                    self.resp_values[f.f_name] = QRadioButton(f.f_value)
                elif f.f_type == TypeEnum.ENUM.value:
                    if not f.f_name in self.resp_values:
                        self.resp_values[f.f_name] = QComboBox()
                    self.resp_values[f.f_name].addItem(f.f_label)
                else:
                    self.resp_values[f.f_name] = QLineEdit("UNKNOWN")

                self.resp_values[f.f_name].setFixedWidth(200)

            if len(self.req_values) > 0:
                req_title = QLabel("- Request")
                req_title.setStyleSheet("font-weight: 900; color: #20b2aa;")
                layout.addWidget(req_title)
            for name, label in self.req_labels.items():
                in_layout = QHBoxLayout()
                in_layout.addWidget(label)
                in_layout.addWidget(self.req_values[name])
                layout.addLayout(in_layout)

            if len(self.resp_values) > 0:
                resp_title = QLabel("- Response")
                resp_title.setStyleSheet("font-weight: 900; color: #20b2aa;")
                layout.addWidget(resp_title)
            for name, label in self.resp_labels.items():
                in_layout = QHBoxLayout()
                in_layout.addWidget(label)
                in_layout.addWidget(self.resp_values[name])
                layout.addLayout(in_layout)
        else:
            # Build file-browse rows for file upload commands.
            for i in range(0, len(request_fields), 2):
                browse_file_button = QPushButton("Browse...")
                browse_file_button.setFixedHeight(30)
                browse_file_button.setStyleSheet(STDTDL_PushButton.valid)
                browse_file_button.adjustSize()
                ext_filter = ""
                file_id = ""
                if "_mlc" in comp_name:
                    ext_filter = UCF_AND_JSON_FILE_FILTER
                    file_id = MLC_CmdValues.mlc_config
                    file_desc = "Configuration file (ucf or json)"
                if "_ispu" in comp_name:
                    if "ucf" in request_fields[i].f_name:
                        file_id = ISPU_CmdValues.ispu_ucf
                        ext_filter = UCF_AND_JSON_FILE_FILTER
                        file_desc = "Configuration file (ucf or json)"
                    elif "output" in request_fields[i].f_name:
                        file_id = ISPU_CmdValues.ispu_output_json
                        ext_filter = "JSON files (*.json *.JSON)"
                        file_desc = "Output JSON file"
                    elif "json" in request_fields[i].f_name:
                        file_id = ISPU_CmdValues.ispu_json
                        ext_filter = "JSON files (*.json *.JSON)"
                        file_desc = "Configuration JSON file"
                # if "ucf" in request_fields[i].f_label.lower():
                #     ext_filter = UCF_AND_JSON_FILE_FILTER
                # elif "json" in request_fields[i].f_label.lower():
                #     ext_filter = "JSON files (*.json *.JSON)"

                self.file_id_list.append(file_id)
                self.loaded_file_value[file_id] = QLineEdit()
                self.loaded_file_value[file_id].setFixedHeight(30)
                self.loaded_file_value[file_id].setContentsMargins(9, 0, 9, 0)
                self.loaded_file_value[file_id].setPlaceholderText(file_desc)
                self.loaded_file_value[file_id].setReadOnly(True)

                browse_file_button.clicked.connect(
                    partial(self.clicked_browse_file_button, self, file_id, ext_filter)
                )
                in_layout = QHBoxLayout()
                in_layout.addWidget(self.loaded_file_value[file_id])
                in_layout.addWidget(browse_file_button)
                in_layout.setContentsMargins(6, 6, 6, 6)
                layout.addLayout(in_layout)

        if len(request_fields) / 2 > 1:
            layout.setSpacing(12)
            layout.setContentsMargins(0, 0, 0, 12)
        else:
            layout.setContentsMargins(0, 0, 0, 24)

        command_fields_frame.setLayout(layout)
        command_fields_widget.layout().addWidget(command_fields_frame)

        self.setContentsMargins(26, 9, 9, 9)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(command_widget)

    def __load_ucf_timer_done(self, ai_sensor_name, widget, loading_window):
        """Finalize AI UCF load and refresh affected components.

        Parameters
        ----------
        ai_sensor_name : str
            Base AI component name (part before the first underscore), used to
            identify other components to refresh.
        widget : CommandWidget
            The current command widget instance; used to access component type.
        loading_window : LoadingWindow
            The temporary loading dialog to dismiss once the refresh is scheduled.
        """

        # Update all components. UCF can modify other sensors (of the same component)
        # configuration, thus a full refresh is requested for matching names.
        for cn in list(self.controller.components_dtdl.keys()):
            if ai_sensor_name in cn:
                self.controller.update_component_status(cn, widget.comp_sem_type)
        loading_window.loadingDone()

    def fill_response_fields(self, response_string):
        """Populate response field editors using a JSON response string.

        Parameters
        ----------
        response_string : str | None
            Raw JSON response returned by `controller.send_command(...)` when
            available. If None, nothing is updated.

        Notes
        -----
        The expected structure is either a flat mapping using the
        ``"<comp>*<cmd>"`` key or a nested response under ``response_name``. Field
        values are mapped to widget editors by their original DTDL type.
        """
        if response_string is not None:
            # print(response_string)
            # test_response_string_1 =
            # "{\"iis3dwb_acc*read_register\": {\"value\": \"test_value\"}}"
            # test_response_string_N =
            # "{\"iis3dwb_acc*read_register\":
            #   {\"register\": {\"value\": \"test_value\", \"type\": \"string\"}}}"
            # response_string = test_response_string_N
            if len(self.resp_values) != 0:
                json_resp = json.loads(response_string)
                inner_json = json_resp.get(self.comp_name + "*" + self.command_name)
                if inner_json is not None:
                    if len(self.resp_values) == 1:
                        f = self.response_fields[0]
                        fw = self.resp_values[0]
                        resp_value = inner_json[f.f_name]
                        if (
                            f.f_type == TypeEnum.STRING.value
                            or f.f_type == TypeEnum.DOUBLE.value
                            or f.f_type == TypeEnum.FLOAT.value
                            or f.f_type == TypeEnum.INTEGER.value
                        ):
                            fw.setText(str(resp_value))
                        elif f.f_type == TypeEnum.BOOLEAN.value:
                            fw.setChecked(resp_value)
                        elif f.f_type == TypeEnum.ENUM.value:
                            if isinstance(f.f_value, int):
                                fw.setCurrentIndex(resp_value)
                            else:
                                fw.setCurrentIndex(int(resp_value))
                    else:
                        for i, rv in enumerate(self.resp_values):
                            f = self.response_fields[i]
                            fw = self.resp_values[rv]
                            resp_value = inner_json[self.response_name][f.f_name]
                            if (
                                f.f_type == TypeEnum.STRING.value
                                or f.f_type == TypeEnum.DOUBLE.value
                                or f.f_type == TypeEnum.FLOAT.value
                                or f.f_type == TypeEnum.INTEGER.value
                            ):
                                fw.setText(str(resp_value))
                            elif f.f_type == TypeEnum.BOOLEAN.value:
                                fw.setChecked(resp_value)
                            elif f.f_type == TypeEnum.ENUM.value:
                                if isinstance(f.f_value, int):
                                    fw.setCurrentIndex(resp_value)
                                else:
                                    fw.setCurrentIndex(int(resp_value))
        else:
            print("No response string")

    def __get_ispu_output_json_path(self):
        return self.loaded_file_path.get(
            ISPU_CmdValues.ispu_output_json,
            self.loaded_file_path.get(ISPU_CmdValues.ispu_json, ""),
        )

    def __get_ispu_config_path(self):
        return self.loaded_file_path.get(
            ISPU_CmdValues.ispu_ucf,
            self.loaded_file_path.get(ISPU_CmdValues.ispu_json, ""),
        )

    def __is_ispu_upload_ready(self):
        ispu_config_path = self.__get_ispu_config_path()
        if ispu_config_path == "":
            return False

        if ispu_config_path.lower().endswith(".json"):
            return True

        if ispu_config_path.lower().endswith(".ucf"):
            return self.__get_ispu_output_json_path() != ""

        return False

    def clicked_send_command_button(self, widget, file_id_list):
        """Send the current command or trigger file upload flows.

        Parameters
        ----------
        widget : CommandWidget
            The originating widget instance (used to resolve fields and names).
        file_id_list : list[str]
            Sequence of file identifiers that must be populated for file-based
            commands. For non-file commands this can be empty.
                (unused here but kept for next implementation)
        """
        _ = file_id_list # Unused parameter
        message_fields = dict()
        if widget.command_name == "load_file":
            if "_mlc" in self.comp_name:
                if self.loaded_file_path[MLC_CmdValues.mlc_config].endswith(".json") or \
                    self.loaded_file_path[MLC_CmdValues.mlc_config].endswith(".JSON"):
                    self.controller.upload_mlc_json_file(
                        self.comp_name, self.loaded_file_path[MLC_CmdValues.mlc_config]
                    )
                elif self.loaded_file_path[MLC_CmdValues.mlc_config].endswith(".ucf") or \
                    self.loaded_file_path[MLC_CmdValues.mlc_config].endswith(".UCF"):
                    self.controller.upload_mlc_ucf_file(
                        self.comp_name, self.loaded_file_path[MLC_CmdValues.mlc_config]
                    )
                loading_window = LoadingWindow(
                    "Loading...", "UCF Configuration file Loading", self
                )
                QTimer.singleShot(
                    5000,
                    lambda: self.__load_ucf_timer_done(
                        self.comp_name.split("_")[0], widget, loading_window
                    ),
                )
                return
            elif "_ispu" in self.comp_name:
                loading_window = LoadingWindow(
                    "Loading...", "Configuration file Loading", self
                )
                ispu_config_path = self.__get_ispu_config_path()
                ispu_output_json = self.__get_ispu_output_json_path()
                if ispu_config_path.lower().endswith(".json"):
                    self.controller.upload_ispu_json_file(
                        self.comp_name,
                        ispu_config_path,
                        ispu_output_json or None,
                    )
                else:
                    self.controller.upload_ispu_ucf_file(
                        self.comp_name,
                        ispu_config_path,
                        ispu_output_json or None,
                    )
                QTimer.singleShot(
                    5000,
                    lambda: self.__load_ucf_timer_done(
                        self.comp_name.split("_")[0], widget, loading_window
                    ),
                )
                return
            else:
                self.controller.upload_file(self.comp_name, self.loaded_file_path)
        else:
            for f in widget.request_fields:
                if f.f_type == TypeEnum.STRING.value:
                    message_fields[f.f_name] = widget.req_values[f.f_name].text()
                elif (
                    f.f_type == TypeEnum.DOUBLE.value or f.f_type == TypeEnum.FLOAT.value
                ):
                    message_fields[f.f_name] = float(widget.req_values[f.f_name].text())
                elif f.f_type == TypeEnum.INTEGER.value:
                    message_fields[f.f_name] = int(widget.req_values[f.f_name].text())
                elif f.f_type == TypeEnum.BOOLEAN.value:
                    message_fields[f.f_name] = widget.req_values[f.f_name].isChecked()
                elif f.f_type == TypeEnum.ENUM.value:
                    if isinstance(f.f_value, int):
                        message_fields[f.f_name] = widget.req_values[f.f_name].currentIndex()
                    else:
                        message_fields[f.f_name] = widget.req_values[f.f_name].itemText(
                            widget.req_values[f.f_name].currentIndex()
                        )

            json_string = PnPLCMDManager.create_command_cmd(
                widget.comp_name, widget.command_name, self.request_name, message_fields
            )
            ret = self.controller.send_command(json_string)
            self.fill_response_fields(ret)

        self.controller.update_component_status(widget.comp_name, widget.comp_sem_type)

    def clicked_browse_file_button(self, widget, file_id, filter):
        """Open a file dialog, capture the selection, and update UI state.

        Parameters
        ----------
        widget : CommandWidget
            The originating command widget instance. (unused here but kept for
            consistency with other slots).
        file_id : str
            Identifier of the file field (e.g., ``mlc_ucf``, ``ispu_json``).
        filter : str
            File dialog filter (e.g., ``"Supported files (*.ucf *.UCF *.json *.JSON)"``).
        """
        _ = widget # Unused parameter
        if "_mlc" in self.comp_name:
            ucf_filter = UCF_AND_JSON_FILE_FILTER
            filepath = QFileDialog.getOpenFileName(filter=ucf_filter)
            if filepath[0]:  # Check if a file was actually selected (not cancelled)
                self.loaded_file_path[file_id] = filepath[0]
                self.loaded_file_value[file_id].setText(self.loaded_file_path[file_id])
                if (
                    MLC_CmdValues.mlc_config in self.loaded_file_path
                    and self.loaded_file_path[MLC_CmdValues.mlc_config] != ""
                ):
                    self.command_send_button.setEnabled(True)
                    self.command_send_button.setStyleSheet(STDTDL_PushButton.green)
                else:
                    self.command_send_button.setEnabled(False)
                    self.command_send_button.setStyleSheet(STDTDL_PushButton.invalid)
        elif "_ispu" in self.comp_name:
            ext_filter = filter
            filepath = QFileDialog.getOpenFileName(filter=ext_filter)
            if filepath[0]:  # Check if a file was actually selected (not cancelled)
                self.loaded_file_path[file_id] = filepath[0]
                self.loaded_file_value[file_id].setText(self.loaded_file_path[file_id])
                if self.__is_ispu_upload_ready():
                    self.command_send_button.setEnabled(True)
                    self.command_send_button.setStyleSheet(STDTDL_PushButton.green)
                else:
                    self.command_send_button.setEnabled(False)
                    self.command_send_button.setStyleSheet(STDTDL_PushButton.invalid)
        else:
            filepath = QFileDialog.getOpenFileName()
            if filepath[0]:  # Check if a file was actually selected (not cancelled)
                self.loaded_file_path[file_id] = filepath[0]
                self.loaded_file_value[file_id].setText(self.loaded_file_path[file_id])
                self.controller.upload_file(self.loaded_file_path[file_id])
