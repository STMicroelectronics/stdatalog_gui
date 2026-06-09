
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

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout

from stdatalog_gui.Utils.PlotParams import SensorCameraPlotParams
from stdatalog_gui.Widgets.Plots.PlotImageWidget import PlotImageWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class HSDPlotImageWidget(PlotWidget):    
    def __init__(self, controller, comp_name, comp_display_name, plot_params, p_id=0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent)
        self.active_tags = dict()
        self.plot_params = plot_params
        self.w = plot_params.width
        self.h = plot_params.height
        self.format = 8
        self.image = {}
        self.pixel_format = plot_params.pixel_format
                
        # Clear PlotWidget inherited graphic elements (mantaining all attributes, functions and signals)
        for i in reversed(range(self.layout().count())): 
            self.contents_frame.layout().itemAt(i).widget().setParent(None)

        image_width = plot_params.width
        image_height = plot_params.height

        self.t1_out = PlotImageWidget(controller, comp_name, comp_display_name, image_width, image_height, plot_label= "Image 1", p_id = p_id, parent=self)
        self.image["target1"] = self.t1_out
        self.t1_out.setMinimumWidth(320)
        self.t1_out.setMinimumHeight(240)
        image_frame = QFrame()
        wdg_layout = QHBoxLayout()
        wdg_layout.addWidget(self.t1_out)
        image_frame.setLayout(wdg_layout)
        #image_frame.setFixedSize(320,240)
        self.contents_frame.layout().addWidget(image_frame)
        
        
    
    @Slot(bool, int) #Override PlotLinesWavWidget s_is_logging
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
        super().s_is_logging(status, interface)
    
    def update_plot_characteristics(self, plot_params:SensorCameraPlotParams):
        self.plot_params = plot_params
        print("update_plot_characteristics")
        self.image["target1"].update_plot_characteristics(plot_params)
    
    def add_data(self, data):
        #print("Sensor PKG Data ")
        self.image["target1"].add_data(data)

    