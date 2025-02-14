 
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

from stdatalog_gui.Utils.PlotParams import MCTelemetriesPlotParams
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget
from stdatalog_gui.HSD_MC_GUI.Widgets.HSD_MC_FastTelemetriesPlotLinesWidget import HSD_MC_FastTelemetriesPlotLinesWidget

class HSD_MC_FastTelemetriesPlotWidget(PlotWidget):
    def __init__(self, controller, comp_name, comp_display_name, plot_params, time_window, p_id = 0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, "")
        
        self.plot_t_interval_size = int(self.plot_len/(time_window / self.timer_interval))
        
        self.graph_curves = dict()
        self.one_t_interval_resampled = dict()
        
        self.graph_widget.deleteLater()

        self.plots_params = plot_params

        self.graph_widgets = {}

        for i, p in enumerate(plot_params.plots_params_dict):
            unit = self.plots_params.plots_params_dict[p].unit
            self.plots_params.plots_params_dict[p].unit = "{} [{}]".format(p,unit)
            pw = HSD_MC_FastTelemetriesPlotLinesWidget(self.controller,
                                    self.plots_params.plots_params_dict[p].comp_name,
                                    p,
                                    plot_params.plots_params_dict[p],
                                    i,
                                    self
                                    )
            self.graph_widgets[p] = pw

            # Clear PlotWidget inherited graphic elements (mantaining all attributes, functions and signals)
            for i in reversed(range(pw.layout().count())): 
                pw.layout().itemAt(i).widget().setParent(None)
            
            self.contents_frame.layout().addWidget(self.graph_widgets[p].graph_widget)
            self.contents_frame.layout().setSpacing(6)

        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params: MCTelemetriesPlotParams):
        self.plots_params = plot_params
        for p in plot_params.plots_params_dict:
            p_enabled = plot_params.plots_params_dict[p].enabled
            self.graph_widgets[p].graph_widget.setVisible(p_enabled)

        if self.app_qt is not None:
            self.app_qt.processEvents()
        
    @Slot(bool)
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1 or interface == 3:
            print("Component {} is logging via USB: {}".format(self.comp_name,status))
            if status:
                #Get number of enabled fast telemetries
                self.ft_enabled_list = [ ft for ft in self.plots_params.plots_params_dict if self.plots_params.plots_params_dict[ft].enabled]
                self.update_plot_characteristics(self.plots_params)
            else:
                self.ft_enabled_list = []

    def update_plot(self):
        super().update_plot()

    def add_data(self, data):
        for i, ft_enabled_name in enumerate(self.ft_enabled_list):
            if "I" in ft_enabled_name:
                self.graph_widgets[ft_enabled_name].add_data([data[0][i::len(self.ft_enabled_list)]*self.plots_params.current_scaler])
            elif "V" in ft_enabled_name:
                self.graph_widgets[ft_enabled_name].add_data([data[0][i::len(self.ft_enabled_list)]*self.plots_params.voltage_scaler])

    def get_num_enabled_fast_tele(self):
        enabled_cnt = 0
        for i, p in enumerate(self.plots_params.plots_params_dict):
            if self.plots_params.plots_params_dict[p].enabled:
                enabled_cnt += 1
        return enabled_cnt

    


 
