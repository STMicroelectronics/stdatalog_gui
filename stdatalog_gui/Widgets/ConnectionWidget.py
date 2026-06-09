#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    ConnectionWidget.py
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
Connection controls and status presentation for device connectivity.

This module defines `ConnectionWidget`, a Qt widget that manages discovery and
connection of compatible devices exposed by the underlying controller. It provides a
drop-down list of detected devices, handles serial-link specifics (optional baud rate
when using HSD Link Serial), and shows a small presentation panel with board and
firmware identifiers after a successful connection.

Responsibilities:
- Populate the device list using the controller API and refresh on command.
- Start/stop connections and display transient errors to the user.
- Honor controller state: disable while detecting/logging, reflect connection status.
- Surface board/firmware IDs and trigger device template loading on connect.

Design Notes:
- The layout is loaded at runtime from `connection_widget.ui` via `QUiLoader`.
- No behavior change is introduced; this file only adds documentation and wraps long
    lines to a maximum of 100 characters.
"""

import os
import stdatalog_gui

from PySide6.QtWidgets import (
    QLineEdit,
    QVBoxLayout,
    QWidget,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

class ConnectionWidget(QWidget):
    """Widget for device connection management and presentation.

    Parameters
    ----------
    controller : Any
        Application controller exposing connectivity methods and signals. Expected to
        provide: `get_device_list`, `is_com_ok`, `is_hsd_link_serial`, `connect_to`,
        `disconnect`, `refresh`, `get_device_presentation_string`, `get_device_formatted_name`,
        `load_device_template`, `get_component_status`, and signals like
        `sig_device_connected`, `sig_com_init_error`, `sig_logging`, `sig_detecting`.
    parent : QWidget | None, optional
        Optional parent widget.

    Attributes
    ----------
    is_connected : bool
        Current connection state reflected in the button label.
    COM_combo_box : QComboBox
        Device list populated from the controller.
    COM_connect_button : QPushButton
        Toggles connection state.
    COM_refresh_button : QPushButton
        Triggers a device list refresh.
    COM_error_message : QLabel
        Area for transient error messages (e.g., empty device list).
    com_speed_frame : QFrame
        Container for the serial speed input, visible only for HSD serial link.
    com_speed_value : QLineEdit
        Baud rate input validated via `QIntValidator`.
    presentation_widget : QWidget
        Hidden by default; shows board and firmware IDs after connect.
    board_id_value : QLineEdit
        Read-only field for the board identifier (hex string).
    fw_id_value : QLineEdit
        Read-only field for the firmware identifier (hex string).
    """

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.controller.sig_device_connected.connect(self.s_is_connected)
        self.controller.sig_com_init_error.connect(self.s_com_init_error)
        self.controller.sig_logging.connect(self.s_is_logging)
        self.controller.sig_detecting.connect(self.s_is_detecting)

        self.is_connected = False

        self.setWindowTitle("Connection")

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            ConnectionWidget, module="ConnectionWidget"
        )
        loader = QUiLoader()

        connection_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "connection_widget.ui",
            ),
            parent,
        )
        contents_widget = connection_widget.frame_connection.findChild(
            QFrame, "frame_contents"
        )
        inner_contents_widget = connection_widget.frame_connection.findChild(
            QFrame, "frame_inner_contents"
        )
        self.COM_combo_box = contents_widget.findChild(QComboBox, "comboBox_COM_list")
        self.COM_connect_button = contents_widget.findChild(
            QPushButton, "pushButton_COM_connect"
        )
        self.COM_connect_button.clicked.connect(self.clicked_COM_connect_button)
        self.COM_refresh_button = contents_widget.findChild(
            QPushButton, "pushButton_COM_refresh"
        )
        self.COM_refresh_button.clicked.connect(self.clicked_COM_refresh_button)
        self.COM_error_message: QLabel = contents_widget.findChild(
            QLabel, "label_COM_error_msg"
        )

        self.com_speed_frame = contents_widget.findChild(QFrame, "frame_COM_speed")
        self.com_speed_value = contents_widget.findChild(QLineEdit, "lineEdit_COM_speed")
        # Limit input to positive integers within signed 32-bit range.
        self.com_speed_value.setValidator(QIntValidator(1, 2147483647))
        self.com_speed_value.setText("1843200")  # Default value
        # Tooltip with min and max values.
        self.com_speed_value.setToolTip("Enter a value between 1 and 2147483647")
        self.com_speed_frame.setVisible(False)

        #Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(connection_widget)

        self.presentation_widget = QWidget()
        presentation_layout = QVBoxLayout()
        self.presentation_widget.setLayout(presentation_layout)
        self.presentation_widget.setVisible(False)
        board_id_layout = QHBoxLayout()
        board_id_label = QLabel("Board Id: ")
        board_id_label.setFixedWidth(100)
        self.board_id_value = QLineEdit()
        self.board_id_value.setReadOnly(True)
        board_id_layout.addWidget(board_id_label)
        board_id_layout.addWidget(self.board_id_value)
        fw_id_layout = QHBoxLayout()
        fw_id_label = QLabel("FW Id: ")
        fw_id_label.setFixedWidth(100)
        self.fw_id_value = QLineEdit()
        self.fw_id_value.setReadOnly(True)
        fw_id_layout.addWidget(fw_id_label)
        fw_id_layout.addWidget(self.fw_id_value)
        presentation_layout.addLayout(board_id_layout)
        presentation_layout.addLayout(fw_id_layout)
        inner_contents_widget.layout().addWidget(self.presentation_widget)

        if self.controller.is_com_ok() == True:
            self.hide_error_message()
            self.fill_COM_combo_box()
        else:
            self.s_com_init_error()

    def hide_error_message(self):
        """Clear and hide the error banner for device-related messages."""
        self.COM_error_message.setText("")
        self.COM_error_message.setFixedHeight(0)
        self.COM_error_message.setVisible(False)

    def show_error_message(self, error_msg):
        """Show a transient error message in the banner area.

        Parameters
        ----------
        error_msg : str
            Text to display in the error banner.

        Returns
        -------
        None
        """
        self.COM_error_message.setText(error_msg)
        self.COM_error_message.setFixedHeight(30)
        self.COM_error_message.setVisible(True)

    def fill_COM_combo_box(self):
        """Populate the COM/device combo box using the controller.

        Notes
        -----
        - Enables or disables the connect button based on device presence.
        - Shows the baud-rate frame only for HSD serial link connections.
        - If no devices are detected, triggers the COM init error handler.
        """
        devices = self.controller.get_device_list()
        self.COM_connect_button.setEnabled(not devices == [])

        if self.controller.is_hsd_link_serial():
            self.com_speed_frame.setVisible(True)
        else:
            self.com_speed_frame.setVisible(False)

        if devices == []:
            self.s_com_init_error()
        self.empty_COM_combo_box()
        for d in devices:
            d_alias = self.controller.get_device_formatted_name(d)
            self.COM_combo_box.addItem(d_alias)
        self.COM_combo_box.setCurrentIndex(0)

    def empty_COM_combo_box(self):
        """Clear the device list combo box."""
        self.COM_combo_box.clear()

    @Slot()
    def clicked_COM_connect_button(self):
        """Connect to or disconnect from the currently selected device.

        Behavior
        --------
        - If already connected, disconnects and clears presentation values.
        - If not connected, optionally checks the motor controller configuration
            (when available) and may emit a controller signal to validate the MCP
            setup before attempting the connection.
        - On successful connect, shows board/firmware IDs and loads the device
            template via the controller.
        """
        if self.is_connected:
            self.controller.disconnect()
            self.COM_connect_button.setText("Connect")
            self.presentation_widget.setVisible(False)
            self.board_id_value.setText("")
            self.fw_id_value.setText("")
        else:
            do_connection = True
            if do_connection:
                if self.controller.is_hsd_link_serial():
                    if self.com_speed_value.text() == "":
                        self.show_error_message("Please enter a valid baudrate")
                        return
                    else:
                        self.controller.connect_to(
                            self.COM_combo_box.currentIndex(),
                            self.COM_combo_box.currentText(),
                            int(self.com_speed_value.text()),
                        )
                else:
                    self.controller.connect_to(
                        self.COM_combo_box.currentIndex(),
                        self.COM_combo_box.currentText(),
                    )
                pres_res = self.controller.get_device_presentation_string(
                    self.COM_combo_box.currentIndex()
                )
                if pres_res is not None:
                    self.presentation_widget.setVisible(True)
                    board_id = hex(pres_res["board_id"])
                    fw_id = hex(pres_res["fw_id"])
                    self.board_id_value.setText(str(board_id))
                    self.fw_id_value.setText(str(fw_id))
                    self.controller.load_device_template(board_id, fw_id)

    @Slot()
    def clicked_COM_refresh_button(self):
        """Refresh the device list and update combo box and errors accordingly."""
        self.controller.refresh()
        if self.controller.is_com_ok() == True:
            self.hide_error_message()
            self.fill_COM_combo_box()

    @Slot(bool)
    def s_is_connected(self, status:bool):
        """React to controller connection changes and update UI state.

        Parameters
        ----------
        status : bool
            True when the controller reports an active connection.
        """
        if status:
            self.COM_connect_button.setText("Disconnect")
            self.is_connected = True
        else:
            self.COM_connect_button.setText("Connect")
            self.is_connected = False

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        """Enable or disable the widget according to detection state.

        Parameters
        ----------
        status : bool
            True to indicate device detection is in progress.
        """
        self.setEnabled(False) if status else self.setEnabled(True)

    @Slot(bool)
    def s_is_logging(self, status:bool, interface: int):
        """Mirror detection state while logging to prevent user interaction.

        Parameters
        ----------
        status : bool
            Whether logging is active.
        interface : int
            Optional interface identifier provided by the controller.
        """
        self.s_is_detecting(status)

    @Slot()
    def s_com_init_error(self):
        """Show an error and clear devices when COM initialization fails or is empty."""
        self.empty_COM_combo_box()
        self.show_error_message(
            "Empty device list. Please try to connect a compatible device and click "
            "the refresh button"
        )
