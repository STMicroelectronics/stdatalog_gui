
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

import os
import stdatalog_gui

from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget, QLabel, QComboBox, QHBoxLayout, QPushButton, QFrame
from PySide6.QtCore import Slot
from PySide6.QtGui import QIntValidator
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

class ConnectionWidget(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.controller.sig_device_connected.connect(self.s_is_connected)
        self.controller.sig_com_init_error.connect(self.s_com_init_error)
        self.controller.sig_logging.connect(self.s_is_logging)
        self.controller.sig_detecting.connect(self.s_is_detecting)
        
        self.is_connected = False
        
        self.setWindowTitle("Connection")
        
        QPyDesignerCustomWidgetCollection.registerCustomWidget(ConnectionWidget, module="ConnectionWidget")
        loader = QUiLoader()

        connection_widget = loader.load(os.path.join(os.path.dirname(stdatalog_gui.__file__),"UI","connection_widget.ui"), parent)
        contents_widget = connection_widget.frame_connection.findChild(QFrame,"frame_contents")
        inner_contents_widget = connection_widget.frame_connection.findChild(QFrame,"frame_inner_contents")
        self.COM_combo_box = contents_widget.findChild(QComboBox,"comboBox_COM_list")
        self.COM_connect_button = contents_widget.findChild(QPushButton,"pushButton_COM_connect")
        self.COM_connect_button.clicked.connect(self.clicked_COM_connect_button)
        self.COM_refresh_button = contents_widget.findChild(QPushButton, "pushButton_COM_refresh")
        self.COM_refresh_button.clicked.connect(self.clicked_COM_refresh_button)
        self.COM_error_message:QLabel = contents_widget.findChild(QLabel,"label_COM_error_msg")

        self.com_speed_frame = contents_widget.findChild(QFrame, "frame_COM_speed")
        self.com_speed_value = contents_widget.findChild(QLineEdit, "lineEdit_COM_speed")
        self.com_speed_value.setValidator(QIntValidator(1, 2147483647))  # Limit input to positive integers
        self.com_speed_value.setText("1843200")  # Default value
        self.com_speed_value.setToolTip("Enter a value between 1 and 2147483647")  # Tooltip with min and max values
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
        self.COM_error_message.setText("")
        self.COM_error_message.setFixedHeight(0)
        self.COM_error_message.setVisible(False)
    
    def show_error_message(self, error_msg):
        self.COM_error_message.setText(error_msg)
        self.COM_error_message.setFixedHeight(30)
        self.COM_error_message.setVisible(True)

    def fill_COM_combo_box(self):
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
        self.COM_combo_box.clear()

    @Slot()
    def clicked_COM_connect_button(self):
        if self.is_connected:
            self.controller.disconnect()
            self.COM_connect_button.setText("Connect")
            self.presentation_widget.setVisible(False)
            self.board_id_value.setText("")
            self.fw_id_value.setText("")
        else:
            do_connection = True
            motor_controller_ret_val = self.controller.get_component_status("motor_controller")
            if motor_controller_ret_val and "PnPL_Error" not in motor_controller_ret_val:
                motor_controller = motor_controller_ret_val['motor_controller']
                if motor_controller is not None:
                    if not motor_controller['mcp_configured']:
                            self.COM_connect_button.setEnabled(False)
                            self.controller.sig_mcp_check_connection.emit()
                            do_connection = False
            if do_connection:
                if self.controller.is_hsd_link_serial():
                    if self.com_speed_value.text() == "":
                        self.show_error_message("Please enter a valid baudrate")
                        return
                    else:
                        self.controller.connect_to(self.COM_combo_box.currentIndex(), self.COM_combo_box.currentText(),int(self.com_speed_value.text()))
                else:
                    self.controller.connect_to(self.COM_combo_box.currentIndex(), self.COM_combo_box.currentText())
                pres_res = self.controller.get_device_presentation_string(self.COM_combo_box.currentIndex())
                if pres_res is not None:
                    self.presentation_widget.setVisible(True)
                    board_id = hex(pres_res["board_id"])
                    fw_id = hex(pres_res["fw_id"])
                    self.board_id_value.setText(str(board_id))
                    self.fw_id_value.setText(str(fw_id))
                    self.controller.load_device_template(board_id,fw_id)
                
    @Slot()
    def clicked_COM_refresh_button(self):
        self.controller.refresh()
        if self.controller.is_com_ok() == True:
            self.hide_error_message()
            self.fill_COM_combo_box()

    @Slot(bool)
    def s_is_connected(self, status:bool):
        if status:
            self.COM_connect_button.setText("Disconnect")
            self.is_connected = True
        else:
            self.COM_connect_button.setText("Connect")
            self.is_connected = False

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        self.setEnabled(False) if status else self.setEnabled(True)
    
    @Slot(bool)
    def s_is_logging(self, status:bool, interface: int):
        self.s_is_detecting(status)
            
    @Slot()
    def s_com_init_error(self):
        self.empty_COM_combo_box()
        self.show_error_message("Empty device list. Please try to connect a compatible device and click the refresh button")