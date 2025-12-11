
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

import os

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFileDialog, QFrame, QLineEdit, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui
from stdatalog_gui.UI.styles import STDTDL_PushButton

class DeviceTemplateLoadingWidget(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        
        self.s_is_dt_loaded = False
        self.selected_device_template_path = ""
        self.setWindowTitle("Device Template")

        QPyDesignerCustomWidgetCollection.registerCustomWidget(DeviceTemplateLoadingWidget, module="DeviceTemplateLoadingWidget")
        loader = QUiLoader()
        dt_load_widget = loader.load(os.path.join(os.path.dirname(stdatalog_gui.__file__),"UI","device_template_load_widget.ui"), parent)
        contents_widget = dt_load_widget.frame_dt_load.findChild(QFrame,"frame_contents")
        self.dt_value = contents_widget.findChild(QLineEdit,"lineEdit_dt_path_value")
        self.dt_value.setReadOnly(True)
        self.browse_dt_button = contents_widget.findChild(QPushButton,"pushButton_browse_in_file")
        self.browse_dt_button.clicked.connect(self.clicked_browse_dt_button)

        ids_widgets_frame = dt_load_widget.findChild(QFrame,"frame_ids")
        self.fw_id_value = ids_widgets_frame.findChild(QLineEdit,"lineEdit_fw_id")
        self.board_id_value = ids_widgets_frame.findChild(QLineEdit,"lineEdit_board_id")
        self.pushButton_upload = ids_widgets_frame.findChild(QPushButton,"pushButton_upload")
        self.pushButton_upload.clicked.connect(self.clicked_upload_button)
        self.pushButton_upload.setEnabled(False)
        self.pushButton_upload.setStyleSheet(STDTDL_PushButton.red)

        self.ok_label = dt_load_widget.findChild(QLabel,"ok_label")
        self.ok_label.setVisible(False)
        self.ko_label = dt_load_widget.findChild(QLabel,"ko_label")
        self.ko_label.setVisible(False)
        
        #Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(dt_load_widget)

    @Slot()
    def clicked_browse_dt_button(self):
        json_filter = "JSON Device Template files (*.json *.JSON)"
        filepath = QFileDialog.getOpenFileName(filter=json_filter)
        self.selected_device_template_path = filepath[0]
        self.dt_value.setText(self.selected_device_template_path)
        self.pushButton_upload.setEnabled(False)
        if self.selected_device_template_path != "":
            self.pushButton_upload.setEnabled(True)
            self.pushButton_upload.setStyleSheet(STDTDL_PushButton.green)
        else:
            self.pushButton_upload.setEnabled(False)
            self.pushButton_upload.setStyleSheet(STDTDL_PushButton.red)

    @Slot()
    def clicked_upload_button(self):
        self.ko_label.setVisible(False)
        self.ok_label.setVisible(False)
        try:
            # Use text() if present, else fallback to placeholderText()
            fw_id_text = self.fw_id_value.text().strip()
            if not fw_id_text:
                fw_id_text = self.fw_id_value.placeholderText().strip()
            self.fw_id = fw_id_text
            if self.fw_id:
                try:
                    self.fw_id = int(self.fw_id, 0)  # allow hex like 0xff
                    if not (0 <= self.fw_id <= 255):
                        self.fw_id = ""
                except (ValueError, TypeError):
                    self.fw_id = ""
            else:
                self.fw_id = ""

            board_id_text = self.board_id_value.text().strip()
            if not board_id_text:
                board_id_text = self.board_id_value.placeholderText().strip()
            self.board_id = board_id_text
            if self.board_id:
                try:
                    self.board_id = int(self.board_id, 0)
                    if not (0 <= self.board_id <= 255):
                        self.board_id = ""
                except (ValueError, TypeError):
                    self.board_id = ""
            else:
                self.board_id = ""

            self.controller.add_custom_device_template(self.selected_device_template_path, self.fw_id, self.board_id)
            self.controller.refresh()
            self.s_is_dt_loaded = True
            self.ko_label.setVisible(False)
            self.ok_label.setVisible(True)

        except Exception as e:
            print("Error uploading device template: {}".format(e))
            self.ko_label.setVisible(True)
            self.ok_label.setVisible(False)
            return
