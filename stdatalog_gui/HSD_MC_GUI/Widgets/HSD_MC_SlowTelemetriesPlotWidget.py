 
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
import stdatalog_gui.HSD_MC_GUI

from stdatalog_gui.Utils.PlotParams import PlotCheckBoxParams, MCTelemetriesPlotParams, PlotGaugeParams, PlotLabelParams, PlotLevelParams
from stdatalog_gui.Widgets.Plots.AnalogGaugeWidget import AnalogGaugeWidget
from stdatalog_gui.Widgets.Plots.CheckBoxListWidget import CheckBoxListWidget
from stdatalog_gui.Widgets.Plots.LabelPlotWidget import LabelPlotWidget
from stdatalog_gui.Widgets.Plots.LevelPlotWidget import LevelPlotWidget
from stdatalog_gui.Widgets.Plots.PlotLinesWidget import PlotLinesWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

class HSD_MC_SlowTelemetriesPlotWidget(PlotWidget):
    def __init__(self, controller, comp_name, comp_display_name, plot_params, time_window, p_id = 0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, "")
    
        self.graph_widget.deleteLater()
        self.plots_params = plot_params

        self.graph_widgets = {}
        
        QPyDesignerCustomWidgetCollection.registerCustomWidget(PlotWidget, module="PlotWidget")
        loader = QUiLoader()
        self.plot_widget = loader.load(os.path.join(os.path.dirname(stdatalog_gui.HSD_MC_GUI.__file__),"UI","slow_mc_telemetries_widget.ui"), parent)

        for i, p in enumerate(self.plots_params.plots_params_dict):
            p_dict_item = self.plots_params.plots_params_dict[p]
            # self.plots_params.plots_params_dict[p].unit = "{} [{}]".format(p,unit)
            if isinstance(p_dict_item, PlotGaugeParams):
                pw = AnalogGaugeWidget(self.controller, self.comp_name, p, p_dict_item.min_val, p_dict_item.max_val, p_dict_item.unit, i, self)
                pw.setMinimumSize(200,200)
                self.graph_widgets[p] = pw
                self.plot_widget.gauges_telemetries.layout().addWidget(self.graph_widgets[p])
            elif isinstance(p_dict_item, PlotLabelParams):
                pw = LabelPlotWidget(self.controller, self.comp_name, p, p_dict_item, i, self)
                pw.title_frame.setVisible(False)
                self.graph_widgets[p] = pw
                self.plot_widget.labels_telemetries.layout().addWidget(self.graph_widgets[p])
            elif isinstance(p_dict_item, PlotLevelParams):
                pw = LevelPlotWidget(self.controller, self.comp_name, p, p_dict_item.min_val, p_dict_item.max_val, 1, p_dict_item.unit, i, self)
                pw.setFixedSize(200, 200)
                #hide x axis
                pw.graph_widget.getAxis('bottom').setVisible(False)
                self.graph_widgets[p] = pw
                self.plot_widget.levels_telemetries.layout().addWidget(self.graph_widgets[p])
            elif isinstance(p_dict_item, PlotCheckBoxParams):
                pw = CheckBoxListWidget(self.controller, self.comp_name, p, p_dict_item.labels, i)
                # pw.setFixedSize(200, 250)
                self.graph_widgets[p] = pw
                self.plot_widget.checkboxes_telemetries.layout().addWidget(self.graph_widgets[p])
            else:
                pw = PlotLinesWidget(self.controller, self.comp_name, p, p_dict_item, i, self)
                self.graph_widgets[p] = pw
                self.plot_widget.lines_telemetries.layout().addWidget(self.graph_widgets[p])

        self.contents_frame.layout().addWidget(self.plot_widget)
        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params: MCTelemetriesPlotParams):
        self.plots_params = plot_params
        if self.plots_params.enabled:
            for p in plot_params.plots_params_dict:
                p_enabled = plot_params.plots_params_dict[p].enabled
                self.graph_widgets[p].setVisible(p_enabled)
        if self.app_qt is not None:
            self.app_qt.processEvents()
        
    @Slot(bool)
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1 or interface == 3:
            print("Component {} is logging via USB: {}".format(self.comp_name,status))
            if status:
                #Get number of enabled slow telemetries
                self.st_enabled_list = [ st for st in self.plots_params.plots_params_dict if self.plots_params.plots_params_dict[st].enabled]
                self.update_plot_characteristics(self.plots_params)
            else:
                self.st_enabled_list = []

    def add_data(self, data):
        for i, st_enabled_name in enumerate(self.st_enabled_list):
            p_dict_item = self.plots_params.plots_params_dict[st_enabled_name]
            if isinstance(p_dict_item, PlotGaugeParams):
                self.graph_widgets[st_enabled_name].add_data(data[i][0])
            else:
                if isinstance(p_dict_item, PlotCheckBoxParams) and st_enabled_name == "fault":
                    if data[i] != 0:
                        self.controller.sig_motor_fault_raised.emit()
                self.graph_widgets[st_enabled_name].add_data([data[i]])