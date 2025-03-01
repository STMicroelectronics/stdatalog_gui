 
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

from collections import deque
import time
import numpy as np
from functools import partial

from PySide6.QtCore import Slot, Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QIcon, QIntValidator, QPainter, QPen, QBrush
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame, QPushButton, QLineEdit, QButtonGroup, QLabel, QGridLayout

import pyqtgraph as pg
from stdatalog_gui.UI.styles import STDTDL_Chip, STDTDL_LineEdit, STDTDL_PushButton
from stdatalog_gui.Utils import UIUtils
from stdatalog_gui.Widgets.Plots.PlotWidget import CustomPGPlotWidget, PlotWidget

from PySide6.QtCore import Signal

from pkg_resources import resource_filename
flip_x = resource_filename('stdatalog_gui.UI.icons', 'outline_sync_alt_white_18.png')
flip_y = resource_filename('stdatalog_gui.UI.icons', 'outline_sync_alt_white_18_rot90.png')
rot_clockwise = resource_filename('stdatalog_gui.UI.icons', 'outline_autorenew_white_18dp.png')
rot_cclockwise = resource_filename('stdatalog_gui.UI.icons', 'outline_autorenew_white_flipped_18dp.png')

roi_colors_rgba = [ [182, 206, 95, 128],
                    [98, 195, 235, 128],
                    [235, 50, 151, 128],
                    [106, 193, 164, 128],
                    [255, 117, 20, 128]]

roi_qcolors = [QColor('#B6CE5F'),
               QColor('#62C3EB'),
               QColor('#EB3297'),
               QColor('#6AC1A4'),
               QColor('#FF7514')]

MIN_DIST = 0
MAX_DIST = 4000
ROI_NUMBER = 5
VALIDITY_MASK_VALID_VALUE_1 = 5
VALIDITY_MASK_VALID_VALUE_2 = 9
VALIDITY_MASK_INVALID_VALUE = 255
# VALIDITY_MASK_NOT_SURE_VALUE_1 = 6
# VALIDITY_MASK_NOT_SURE_VALUE_2 = 9

class CustomHeatmapPlotWidget(CustomPGPlotWidget):
    def __init__(self, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

    def mouseMoveEvent(self, ev):
        pass

class Chip(QPushButton):
    
    def __init__(self, text, color, parent=None):
        super().__init__(text, parent)
        self.color = color
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setFixedHeight(30)
        self.setStyleSheet(STDTDL_Chip.color(color))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._color = QColor(255, 0, 0)
        self._alpha = 0
        self._direction = 1

    def start_flash(self):
        self._timer.start(10)

    def stop_flash(self):
        self._timer.stop()
        self._alpha = 0
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        brush = QBrush(self.color)
        brush.setColor(QColor(self._color.red(), self._color.green(), self._color.blue(), self._alpha))
        painter.setBrush(brush)
        painter.drawRoundedRect(self.rect(), 12, 12)
        painter.setPen(QPen(Qt.black))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

    def _on_timeout(self):
        self._alpha += self._direction * 10
        if self._alpha > 255:
            self._alpha = 255
            self._direction = -1
        elif self._alpha < 0:
            self._alpha = 0
            self._direction = 1
        self.update()

class ROISettingsWidget(QFrame):

    sig_selected_roi = Signal(int)
    sig_data_rotation = Signal(int)
    sig_data_x_flip = Signal()
    sig_data_y_flip = Signal()
    sig_roi_threshold_set = Signal(int,int)#roi_id,th_value
    sig_presence_threshold_set = Signal(int)#th_value

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # Create a vertical layout for the widget
        layout = QVBoxLayout()

        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedWidth(150)

        # Create a button group to manage the radio buttons
        self.button_group = QButtonGroup()

        # Set the layout for the widget
        self.setLayout(layout)

        self.rotation_id = 0
        self.flipped_x_status = False
        self.flipped_y_status = False
        self.rois_chips = {}
        self.rois_threshold_lineedits = {}
        self.setStyleSheet("QFrame { border: transparent; background:#272c36}")

        # Create button widgets to adjust the rotation value
        self.rot_left_button = QPushButton()
        self.rot_right_button = QPushButton()
        self.rot_left_button.setStyleSheet(STDTDL_PushButton.valid)
        self.rot_right_button.setStyleSheet(STDTDL_PushButton.valid)
        self.rot_left_button.setIcon(QIcon(rot_clockwise))
        self.rot_right_button.setIcon(QIcon(rot_cclockwise))
        self.rot_left_button.clicked.connect(lambda:self.data_rotation(+1))
        self.rot_right_button.clicked.connect(lambda:self.data_rotation(-1))

        # Create a label widget to display the value
        self.rot_label = QLabel("0°")
        self.rot_label.setStyleSheet("font:700")
        self.rot_label.setAlignment(Qt.AlignCenter)

        rot_label_title = QLabel("Data Rotation:")
        flip_x_label_title = QLabel("Data Horizontal Flip:")
        flip_y_label_title = QLabel("Data Vertical Flip:")
        roi_label_title = QLabel("ROI settings:")

        rotation_layout = QHBoxLayout()
        rotation_layout.addWidget(self.rot_left_button)
        rotation_layout.addWidget(self.rot_label)
        rotation_layout.addWidget(self.rot_right_button)
        
        self.flip_x_label = QLabel("Normal")
        self.flip_x_label.setStyleSheet("font:700")
        flip_x_layout = QHBoxLayout()
        self.flip_x_button = QPushButton()
        self.flip_x_button.setStyleSheet(STDTDL_PushButton.valid)
        self.flip_x_button.setIcon(QIcon(flip_x))
        self.flip_x_button.clicked.connect(self.data_x_flip)
        flip_x_layout.addWidget(self.flip_x_button)
        flip_x_layout.addWidget(self.flip_x_label)

        self.flip_y_label = QLabel("Normal")
        self.flip_y_label.setStyleSheet("font:700")
        flip_y_layout = QHBoxLayout()
        self.flip_y_button = QPushButton()
        self.flip_y_button.setStyleSheet(STDTDL_PushButton.valid)
        self.flip_y_button.setIcon(QIcon(flip_y))
        self.flip_y_button.clicked.connect(self.data_y_flip)
        flip_y_layout.addWidget(self.flip_y_button)
        flip_y_layout.addWidget(self.flip_y_label)

        self.layout().addWidget(rot_label_title)
        self.layout().insertLayout(1, rotation_layout)
        self.layout().addWidget(flip_x_label_title)
        self.layout().insertLayout(3, flip_x_layout)
        self.layout().addWidget(flip_y_label_title)
        self.layout().insertLayout(5, flip_y_layout)
        

        global_thresh_layout = QVBoxLayout()
        global_thresh_label = QLabel("Global threshold:")
        global_thresh_layout.addWidget(global_thresh_label)
        self.global_thresh_value = QLineEdit()
        self.global_thresh_value.setText(str(MIN_DIST))
        self.global_thresh_value.setFixedSize(60,30)
        self.global_thresh_value.setStyleSheet(STDTDL_LineEdit.valid)
        self.global_thresh_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        int_validator = QIntValidator()
        int_validator.setRange(MIN_DIST, MAX_DIST)
        self.global_thresh_value.setToolTip("min: {}, max: {}".format(MIN_DIST, MAX_DIST))
        self.global_thresh_value.setValidator(int_validator)
        self.global_thresh_value.textChanged.connect(partial(UIUtils.validate_value, self.controller,  self.global_thresh_value))
        self.global_thresh_value.editingFinished.connect(lambda: self.presence_threshold_set(self.global_thresh_value))
        global_thresh_layout.addWidget(self.global_thresh_value)
        self.layout().insertLayout(6, global_thresh_layout)
        
        self.layout().addWidget(roi_label_title)
        rois_layout = QGridLayout()
        roi_col_label = QLabel("region")
        roi_col_label.setStyleSheet("color:#666666;")
        roi_col_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rois_layout.addWidget(roi_col_label,0,0)
        thresh_col_label = QLabel("threshold")
        thresh_col_label.setStyleSheet("color:#666666;")
        thresh_col_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rois_layout.addWidget(thresh_col_label,0,1)

        for i in range(0,ROI_NUMBER):
            self.add_roi_chip(rois_layout,i,6)

        self.layout().insertLayout(8, rois_layout)

    def data_rotation(self, inc_dec):
        self.rotation_id += inc_dec
        r_id = self.rotation_id % 4
        if r_id == 0 or r_id == 4:
            self.rot_label.setText("0°")
        elif r_id == 1:
            self.rot_label.setText("90°")
        elif r_id == 2:
            self.rot_label.setText("180°")
        elif r_id == 3:
            self.rot_label.setText("270°")
        if self.flipped_x_status != self.flipped_y_status:
            self.sig_data_rotation.emit(-inc_dec)
        else:
            self.sig_data_rotation.emit(inc_dec)

    def data_x_flip(self):
        self.flipped_x_status = not self.flipped_x_status
        self.flip_x_label.setText("Flipped") if self.flipped_x_status else self.flip_x_label.setText("Normal")
        self.sig_data_x_flip.emit()

    def data_y_flip(self):
        self.flipped_y_status = not self.flipped_y_status
        self.flip_y_label.setText("Flipped") if self.flipped_y_status else self.flip_y_label.setText("Normal")
        self.sig_data_y_flip.emit()

    def add_roi_chip(self, rois_layout:QGridLayout, roi_id, start_offset = 0):
        # Create a new radio button and add it to the layout
        roi_chip = Chip("ROI {}".format(roi_id), roi_qcolors[roi_id])
        roi_chip.setFixedSize(50,30)
        roi_chip.toggled.connect(lambda: self.roi_radio_clicked(roi_id))
        
        roi_threshold_lineedit = QLineEdit()
        roi_threshold_lineedit.setText(str(MIN_DIST))
        roi_threshold_lineedit.setFixedSize(60,30)
        roi_threshold_lineedit.setStyleSheet(STDTDL_LineEdit.valid)
        roi_threshold_lineedit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        int_validator = QIntValidator()
        int_validator.setRange(MIN_DIST, MAX_DIST)
        roi_threshold_lineedit.setToolTip("min: {}, max: {}".format(MIN_DIST, MAX_DIST))
        roi_threshold_lineedit.setValidator(int_validator)
        roi_threshold_lineedit.textChanged.connect(partial(UIUtils.validate_value, self.controller, roi_threshold_lineedit))
        roi_threshold_lineedit.editingFinished.connect(lambda: self.roi_threshold_set(roi_id, roi_threshold_lineedit))

        # Add the radio button to the button group
        self.button_group.addButton(roi_chip)

        self.rois_chips[roi_id] = roi_chip    
        if len(self.rois_chips) == 1:
            roi_chip.toggle()
        self.rois_threshold_lineedits[roi_id] = roi_threshold_lineedit
        rois_layout.addWidget(roi_chip, roi_id+1, 0)
        rois_layout.addWidget(roi_threshold_lineedit, roi_id+1, 1)
    
    def get_rois_chips(self):
        return self.rois_chips

    def roi_radio_clicked(self, roi_id):
        self.sig_selected_roi.emit(roi_id)

    def roi_threshold_set(self, roi_id, threshold_lineedit):
        self.sig_roi_threshold_set.emit(roi_id, int(threshold_lineedit.text()))
        if (int(threshold_lineedit.text()) > int(self.global_thresh_value.text())):
            self.global_thresh_value.setText(self.rois_threshold_lineedits[roi_id].text())
            self.sig_presence_threshold_set.emit(int(threshold_lineedit.text()))
    
    def presence_threshold_set(self, threshold_lineedit):
        self.sig_presence_threshold_set.emit(int(threshold_lineedit.text()))
        for roi_id in range(ROI_NUMBER):
            if (int(self.rois_threshold_lineedits[roi_id].text()) > int(threshold_lineedit.text())):
                self.rois_threshold_lineedits[roi_id].setText(threshold_lineedit.text())
                self.sig_roi_threshold_set.emit(roi_id, int(threshold_lineedit.text()))

class PlotHeatmapWidget(PlotWidget):
    
    sig_threshold_exceded = Signal(int,int,int)# roi_id, current_value, threshold_value

    def __init__(self, controller, comp_name, comp_display_name, heatmap_shape, plot_label= "", p_id = 0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, plot_label)

        self.plot_label = plot_label
        # Clear PlotWidget inherited graphic elements (mantaining all attributes, functions and signals)
        for i in reversed(range(self.contents_frame.layout().count())): 
            self.contents_frame.layout().itemAt(i).widget().setParent(None)

        main_layout = QHBoxLayout()
        main_frame = QFrame()
        main_frame.setStyleSheet("QFrame { border-radius: 5px; border: 2px solid rgb(27, 29, 35);}")
        main_frame.setLayout(main_layout)
        
        self.graph_widget = CustomHeatmapPlotWidget(parent = self)        
        
        self.heatmap_shape = heatmap_shape
        self.heatmap_rotation = 0
        self.heatmap_is_x_flipped = False
        self.heatmap_is_y_flipped = False
        self.roi_thresolds = {i:MIN_DIST for i in range(ROI_NUMBER)}
        self.presence_threshold = MIN_DIST
        self.global_presence_status = False
        
        self.data = np.zeros(shape=(self.heatmap_shape), dtype='i')
        self._data = deque(maxlen=200000)

        self.validity_mask = np.zeros(shape=(self.heatmap_shape), dtype='i')
        self.zones = PlotHeatmapWidget.create_matrix(self.heatmap_shape[0])
        self.rois = {i: {} for i in range(ROI_NUMBER)}
        self.underthresh = {i: [] for i in range(ROI_NUMBER)}
        self.global_underthresh = np.zeros(shape=(self.heatmap_shape), dtype='i')
        self.is_roi_flashing = {i:False for i in range(ROI_NUMBER)}
        
        self.selected_roi_id = 0
        self.a = 0
        
        self.heatmap_img = pg.ImageItem()
        self.heatmap_img.setImage(self.data, levels=[MIN_DIST, MAX_DIST])

        old_plot_item = self.graph_widget.getPlotItem()
        self.graph_widget.removeItem(old_plot_item)
        self.graph_widget.getPlotItem().addItem(self.heatmap_img)

        self.graph_widget.getPlotItem().layout.setContentsMargins(10, 3, 3, 10)
        self.graph_widget.getPlotItem().setMenuEnabled(False) #Disable right click menu in plots
        self.graph_widget.getPlotItem().showGrid(True,True)
        
        styles = {'color':'#d2d2d2', 'font-size':'12px'}
        self.graph_widget.setLabel('bottom', self.left_label, **styles)
        self.graph_widget.setBackground('#1b1d23')

        self.red_color = QColor(255, 0, 0)
        self.green_color = QColor(0, 255, 0)
        
        self.timer_interval_ms = self.timer_interval*700

        self.rois_layout = QVBoxLayout()
        self.rois_frame = ROISettingsWidget(controller)
        self.rois_frame.sig_data_rotation.connect(self.data_rotation_callback)
        self.rois_frame.sig_selected_roi.connect(self.set_selected_roi_id)
        self.rois_frame.sig_data_x_flip.connect(self.data_flip_x_callback)
        self.rois_frame.sig_data_y_flip.connect(self.data_flip_y_callback)
        self.rois_frame.sig_roi_threshold_set.connect(self.roi_threshold_set_callback)
        self.rois_frame.sig_presence_threshold_set.connect(self.presence_threshold_set_callback)
        self.roi_chips = self.rois_frame.rois_chips

        self.plot_layout = QHBoxLayout()
        self.plot_frame = QFrame()
        self.plot_frame.setStyleSheet("QFrame { border: transparent;}")
        self.plot_frame.setContentsMargins(0,0,0,0)
        self.plot_frame.setLayout(self.plot_layout)
        self.plot_layout.addWidget(self.graph_widget)

        main_layout.addWidget(self.rois_frame)
        main_layout.addWidget(self.plot_frame)
        self.contents_frame.layout().addWidget(main_frame)

        # Add text items for each pixel
        self.text_items = []
        self.fill_with_text_items()

        # Add a mouse click event handler to the imageItem
        self.heatmap_img.mouseClickEvent = self.image_item_clicked
        self.heatmap_img.getViewBox().setAspectLocked(True)

    def fill_with_text_items(self):
        #clean existing text items, if any
        for ti in self.text_items:
            for w in ti:
                self.graph_widget.removeItem(w)
                w.deleteLater()
        self.text_items = []
        
        #add new text items
        for i in range(self.heatmap_shape[0]):
            row = []
            for j in range(self.heatmap_shape[1]):
                text_item = pg.TextItem(text= str(self.data[i, j]), color=(200, 200, 200), anchor=(0,1))
                text_item.setPos(j, i)
                self.graph_widget.addItem(text_item)
                row.append(text_item)
            self.text_items.append(row)

    def update_plot_characteristics(self, heatmap_shape):
        self.heatmap_shape = heatmap_shape
        self.zones = PlotHeatmapWidget.create_matrix(self.heatmap_shape[0])
        self.data = np.zeros(shape=(self.heatmap_shape),dtype='i')
        self._data.clear()
        self.global_underthresh = np.zeros(shape=(self.heatmap_shape), dtype='i')
        self.validity_mask = np.zeros(shape=(self.heatmap_shape), dtype='i')
        self.heatmap_img.setImage(self.data, levels=[MIN_DIST, MAX_DIST])
        self.graph_widget.getPlotItem()._updateView()
        # Add text items for each pixel
        self.fill_with_text_items()
        if self.app_qt is not None:
            self.app_qt.processEvents()

    @Slot(bool, int)
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
            if status:
                self.buffering_timer_counter = 0
                self.timer.start(self.timer_interval_ms)
            else:
                self.timer.stop()
        else: # interface == 0
            print("Component {} is logging on SD Card: {}".format(self.comp_name,status))

    def update_plot(self):
        # Extract all data from the queue (pop)
        if len(self._data) > 0 :
            l_data = self._data.popleft()
            if l_data.shape == self.heatmap_shape:
                self.heatmap_img.setImage(l_data, levels=[MIN_DIST, MAX_DIST])
                for i in range(self.heatmap_shape[0]):
                    for j in range(self.heatmap_shape[1]):
                        curr_data = l_data[i][j]
                        curr_valid_mask = self.validity_mask[i][j]
                        if curr_data > MAX_DIST:
                            self.text_items[j][i].setText("X")
                            curr_valid_mask = VALIDITY_MASK_INVALID_VALUE
                            self.global_underthresh[i][j] = 0
                        else:                    
                            self.text_items[j][i].setText(str(curr_data))
                        
                        if curr_valid_mask == VALIDITY_MASK_INVALID_VALUE:
                            self.text_items[j][i].setColor(self.red_color) #red, invalid
                            self.global_underthresh[i][j] = 0
                        else:
                            self.text_items[j][i].setColor(self.green_color) #green, valid
                            if curr_data != 0 and curr_data < self.presence_threshold:
                                self.global_underthresh[i][j] = 1
                            else:
                                self.global_underthresh[i][j] = 0
                        for k in range(ROI_NUMBER):
                            if len(self.rois[k].keys()) == 0:
                                self.underthresh[k] = []
                            elif (i,j) in self.rois[k].keys():

                                if curr_valid_mask == VALIDITY_MASK_INVALID_VALUE:
                                    if (i,j) in self.underthresh[k]:
                                        self.underthresh[k].remove((i,j))
                                else:
                                    if curr_data < self.roi_thresolds[k]:
                                        if (i,j) not in self.underthresh[k]:
                                            self.underthresh[k].append((i,j))
                                    else:
                                        if (i,j) in self.underthresh[k]:
                                            self.underthresh[k].remove((i,j))
                
                if bool(np.any(self.global_underthresh)) == True and not np.all(0) and self.global_presence_status == False:
                    self.global_presence_status = True
                    self.controller.sig_tof_presence_detected.emit(self.global_presence_status, "tof_presence")
                elif bool(np.any(self.global_underthresh)) == False and not np.all(0) and self.global_presence_status == True:
                    self.global_presence_status = False
                    self.controller.sig_tof_presence_detected.emit(self.global_presence_status, "tof_presence")
                
                for x in range(ROI_NUMBER):
                    if x in self.underthresh and self.underthresh[x] != []:
                        if not self.is_roi_flashing[x]: 
                            roi_chip = self.rois_frame.rois_chips[x]
                            self.is_roi_flashing[x] = True
                            roi_chip.start_flash()
                            self.controller.sig_tof_presence_detected_in_roi.emit(True,x+1,"Target {}".format(x+1))
                    else:
                        if self.is_roi_flashing[x]: 
                            roi_chip = self.rois_frame.rois_chips[x]
                            self.is_roi_flashing[x] = False
                            roi_chip.stop_flash()
                            self.controller.sig_tof_presence_detected_in_roi.emit(False,x+1,"Target {}".format(x+1))
            else:
                self.heatmap_img.setImage(l_data)
        self._data.clear()
        
    def add_data(self, data):
        data_shape = self.heatmap_shape[0]*self.heatmap_shape[1]
        if len(data) == 2:
            if len(data[0]) % (data_shape) == 0 and len(data[0]) != 0:
                l_data = data[0][-data_shape:].reshape(self.heatmap_shape).transpose()
                l_data = np.rot90(l_data, k=-(self.heatmap_rotation % 4))
                if self.heatmap_is_x_flipped:
                    l_data = np.flip(l_data, axis=0)
                if self.heatmap_is_y_flipped:
                    l_data = np.flip(l_data, axis=1)
                self._data.append(l_data)
            
            if len(data[1]) % (data_shape) == 0 and len(data[1]) != 0:
                self.validity_mask = data[1][-data_shape:].reshape(self.heatmap_shape)
                self.validity_mask = np.rot90(self.validity_mask, k=-(self.heatmap_rotation % 4))
                if self.heatmap_is_x_flipped:
                    self.validity_mask = np.flip(self.validity_mask, axis=0)
                if self.heatmap_is_y_flipped:
                    self.validity_mask = np.flip(self.validity_mask, axis=1)
        if len(data) == self.heatmap_shape[0]:
            l_data = np.rot90(data, k=-(self.heatmap_rotation % 4))
            if self.heatmap_is_x_flipped:
                l_data = np.flip(l_data, axis=0)
            if self.heatmap_is_y_flipped:
                l_data = np.flip(l_data, axis=1)
            self._data.append(l_data)

    @staticmethod
    def create_matrix(size):
        # Create a matrix of False values
        matrix = [[False for col in range(size)] for row in range(size)]
        # Create an empty dictionary
        coord_dict = {}
        # Iterate over the rows and columns of the matrix
        for row in range(size):
            for col in range(size):
                # Create a dictionary entry for each tuple of coordinates
                coord_dict[(row, col)] = matrix[row][col]
        # Return the dictionary
        return coord_dict
    
    def set_selected_roi_id(self, roi_id):
        self.selected_roi_id = roi_id
    
    def set_default_rotation(self, rotation):
        self.heatmap_rotation = rotation
        self.rois_frame.rotation_id = rotation
        self.rois_frame.data_rotation(0)

    def set_default_x_flip(self, x_flip):
        self.heatmap_is_x_flipped = x_flip

    def set_default_y_flip(self, y_flip):
        self.heatmap_is_y_flipped = y_flip

    def data_rotation_callback(self, rot_id):
        self.heatmap_rotation += rot_id

    def data_flip_x_callback(self):
        self.heatmap_is_x_flipped = not self.heatmap_is_x_flipped

    def data_flip_y_callback(self):
        self.heatmap_is_y_flipped = not self.heatmap_is_y_flipped

    def roi_threshold_set_callback(self, roi_id, roi_threshold):
        # print("roi_id: {}, roi_threshold: {}".format(roi_id, roi_threshold))
        self.roi_thresolds[roi_id] = roi_threshold
    
    def presence_threshold_set_callback(self, threshold):
        self.presence_threshold = threshold

    def image_item_clicked(self, event):
        # Get the mouse click position in image coordinates
        pos = self.heatmap_img.mapFromScene(event.scenePos())
        x, y = int(pos.x()), int(pos.y())

        # Get the pixel value at the clicked position
        # pixel_value = self.data[y, x]
        # print(f"Clicked on pixel ({x}, {y}) with value {pixel_value}")

        if self.zones[(x,y)] == False:
            if (x,y) not in self.rois[self.selected_roi_id]:
                mask = pg.ImageItem()
                mask.setImage(np.ones((1, 1, 4)) * np.array(roi_colors_rgba[self.selected_roi_id]))
                mask.setPos(QPoint(x,y))
                self.rois[self.selected_roi_id][(x,y)] = mask
            self.graph_widget.addItem(self.rois[self.selected_roi_id][(x,y)])
            self.zones[(x,y)] = True
        else:
            self.graph_widget.removeItem(self.rois[self.selected_roi_id][(x,y)])
            del self.rois[self.selected_roi_id][(x,y)]
            self.zones[(x,y)] = False
