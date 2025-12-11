# *****************************************************************************
#  * @file    DeviceConfigPage.py
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
#

import os
from PySide6.QtCore import Slot

from stdatalog_gui.STDTDL_DeviceConfigPage import STDTDL_DeviceConfigPage
from stdatalog_gui.Widgets.Plots.AnomalyDetectorWidget import AnomalyDetectorWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDMLCConfigurationWidget import HSDMCLConfigurationWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotALSWidget import HSDPlotALSWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotPOWWidget import HSDPlotPOWWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotTMOSWidget import HSDPlotTMOSWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotToFWidget import HSDPlotToFWidget
from stdatalog_gui.HSD_GUI.Widgets.AppClassificationControlWidget import AppClassificationControlWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDAutoModeWidget import HSDAutoModeWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDLogControlWidget import HSDLogControlWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDAdvLogControlWidget import HSDAdvLogControlWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDComponentWidget import HSDALSComponentWidget, HSDComponentWidget
from stdatalog_gui.HSD_GUI.Widgets.TagsInfoWidget import TagsInfoWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotLinesWidget import HSDPlotLinesWidget

from stdatalog_core.HSD_link.HSDLink import HSDLink

from stdatalog_gui.Widgets.Plots.PlotBarFFTWidget import PlotBarFFTWidget
from stdatalog_gui.Widgets.Plots.ClassifierOutputWidget import ClassifierOutputWidget
from stdatalog_gui.Utils.PlotParams import ActuatorPlotParams, PlotPAmbientParams, PlotPMotionParams, PlotPObjectParams, PlotPPresenceParams, SensorLightPlotParams, SensorPlotParams, AlgorithmPlotParams, SensorPowerPlotParams, SensorPresenscePlotParams, SensorRangingPlotParams

from stdatalog_gui.STDTDL_Controller import ComponentType
from PySide6.QtWidgets import QMessageBox
import json
import stdatalog_pnpl.DTDL.dtdl_utils as DTDLUtils

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class HSD_DeviceConfigPage(STDTDL_DeviceConfigPage):

    def __init__(self, page_widget, controller):
        super().__init__(page_widget, controller)
        
        self.controller.sig_hsd_bandwidth_exceeded.connect(self.s_bandwidth_exceeded)
        self.controller.sig_streaming_error.connect(self.s_streaming_error)
        self.controller.sig_is_waiting_auto_start.connect(self.s_is_waiting_autostart)
        self.controller.sig_is_auto_started.connect(self.s_auto_started)
        self.controller.sig_pnpl_response_received.connect(self.s_pnpl_response_received)

        self.anomaly_classes = {}
        self.output_classes = {}

        self.threads_stop_flags = []
        self.sensor_data_files = []

        self.ignored_components = ["applications_stblesensor","wifi_config"]

        self.graph_id = 0

        self.log_file_name = None
        for handler in log.parent.handlers:
            if hasattr(handler, "baseFilename"):
                self.log_file_name = os.path.basename(getattr(handler, 'baseFilename'))

    
    @Slot(str, dict)
    def s_component_found(self, comp_name, comp_interface):
        #create a ComponentWidget
        comp_display_name = comp_interface.display_name if isinstance(comp_interface.display_name, str) else comp_interface.display_name.en
        if comp_name == "log_controller":
            c_status = self.controller.get_component_status(comp_name)
            if "controller_type" in c_status["log_controller"]:
                controller_type = c_status["log_controller"]["controller_type"]
                if controller_type == 0: #0 == HSD Advanced log controller
                    self.log_control_widget = HSDAdvLogControlWidget(self.controller, comp_contents=comp_interface.contents, parent=self.widget_header)
                    self.controller.set_rtc_time()
                elif controller_type == 1: #1 == App classification controller
                    self.log_control_widget = AppClassificationControlWidget(self.controller, comp_contents=comp_interface.contents, parent=self.widget_header)
                elif controller_type == 2: #2 == HSD Simple log controller
                    self.log_control_widget = HSDLogControlWidget(self.controller, comp_contents=comp_interface.contents, parent=self.widget_header)
                    self.controller.set_rtc_time()
            else:
                self.log_control_widget = HSDLogControlWidget(self.controller, comp_contents=comp_interface.contents, parent=self.widget_header)
                self.controller.set_rtc_time()
            self.controller.add_component_config_widget(self.log_control_widget)
            self.add_header_widget(self.log_control_widget)
            self.controller.fill_component_status(comp_name)
        elif comp_name == "tags_info":
            self.tags_info_widget = TagsInfoWidget(self.controller, comp_contents=comp_interface.contents, c_id=1, parent=self.widget_special_componenents)
            self.tags_info_widget.clicked_show_button()
            self.controller.add_component_config_widget(self.tags_info_widget)
            self.widget_special_componenents.layout().addWidget(self.tags_info_widget)
            self.controller.fill_component_status(comp_name)
        elif comp_name in self.ignored_components:
            pass
        elif comp_name == "automode":
            fw_info = self.controller.hsd_link.get_firmware_info(self.controller.device_id)
            if(HSDLink.get_versiontuple(fw_info["firmware_info"]["fw_version"]) >= HSDLink.get_versiontuple("1.2.0")):
                self.automode_widget = HSDAutoModeWidget(self.controller, comp_contents=comp_interface.contents, c_id=0, parent=self.widget_special_componenents)
                self.controller.add_component_config_widget(self.automode_widget)
                self.widget_special_componenents.layout().addWidget(self.automode_widget)
                self.controller.fill_component_status(comp_name)
        else:
            comp_config_widget = HSDComponentWidget(self.controller, comp_name, comp_display_name, "", comp_interface.contents, self.comp_id, self.device_config_widget)
            self.controller.add_component_config_widget(comp_config_widget)
            self.device_config_widget.layout().addWidget(comp_config_widget)
            self.controller.fill_component_status(comp_name)
            self.comp_id += 1

    
    @Slot(str, dict)
    def s_sensor_component_found(self, comp_name, comp_interface):
        #create a HSDComponentWidget
        comp_display_name = comp_interface.display_name if isinstance(comp_interface.display_name, str) else comp_interface.display_name.en
        if "_mlc" in comp_name:
            sensor_config_widget = HSDMCLConfigurationWidget(self.controller, comp_name, comp_display_name, ComponentType.SENSOR, comp_interface.contents, self.comp_id, self.device_config_widget)
        elif "_als" in comp_name:
            sensor_config_widget = HSDALSComponentWidget(self.controller, comp_name, comp_display_name, ComponentType.SENSOR, comp_interface.contents, self.comp_id, self.device_config_widget)
        else:
            sensor_config_widget = HSDComponentWidget(self.controller, comp_name, comp_display_name, ComponentType.SENSOR, comp_interface.contents, self.comp_id, self.device_config_widget)
        
        self.controller.add_component_config_widget(sensor_config_widget)
        self.device_config_widget.layout().addWidget(sensor_config_widget)
        
        comp_status = self.controller.get_component_status(comp_name)

        try:
            enabled = self.controller.is_sensor_enabled(comp_name)
            self.comp_id += 1
            sensor_plot_params:SensorPlotParams = self.controller.get_plot_params(comp_name, ComponentType.SENSOR, comp_interface, comp_status)
            if sensor_plot_params is not None:
                if isinstance(sensor_plot_params, SensorRangingPlotParams):
                    sensor_plot_widget = HSDPlotToFWidget(self.controller, comp_name, comp_display_name, sensor_plot_params, self.graph_id, self.plots_widget) 
                elif isinstance(sensor_plot_params, SensorPresenscePlotParams):
                    plots_params_dict = {}
                    s_enabled = comp_status[comp_name].get("enable")
                    embedded_compensation = comp_status[comp_name].get("embedded_compensation")
                    software_compensation = comp_status[comp_name].get("software_compensation")
                    
                    plots_params_dict["Ambient"] = PlotPAmbientParams(comp_name, s_enabled, 1)
                    plots_params_dict["Object"] = PlotPObjectParams(comp_name, s_enabled, 4, embedded_compensation, software_compensation)
                    plots_params_dict["Presence"] = PlotPPresenceParams(comp_name, s_enabled, 1, embedded_compensation, software_compensation)
                    plots_params_dict["Motion"] = PlotPMotionParams(comp_name, s_enabled, 1, embedded_compensation, software_compensation)
                    sensor_plot_params.plots_params_dict = plots_params_dict
                    sensor_plot_widget = HSDPlotTMOSWidget(self.controller, comp_name, comp_display_name, sensor_plot_params, self.graph_id, self.plots_widget) 
                elif isinstance(sensor_plot_params, SensorLightPlotParams):
                    sensor_plot_widget = HSDPlotALSWidget(self.controller, comp_name, comp_display_name, sensor_plot_params, self.graph_id, self.plots_widget)
                elif isinstance(sensor_plot_params, SensorPowerPlotParams):
                    sensor_plot_widget = HSDPlotPOWWidget(self.controller, comp_name, comp_display_name, sensor_plot_params, self.graph_id, self.plots_widget)
                else:
                    sensor_plot_widget = HSDPlotLinesWidget(self.controller, comp_name, comp_display_name, sensor_plot_params, self.graph_id, self.plots_widget)
                self.graph_id +=1
                self.controller.add_plot_widget(sensor_plot_widget, enabled)
                self.plots_widget.layout().addWidget(sensor_plot_widget)
                log.debug("comp_name: {} - status: {}".format(comp_name,enabled))
                sensor_plot_widget.setVisible(enabled)
        except Exception as e:
            print(e)
            log.warning("It is impossible to know the Sensor [{}] enabling status from the FW device status".format(comp_name))

        self.controller.fill_component_status(comp_name)
        self.controller.check_hsd_bandwidth()

    @Slot(str, dict)
    def s_algorithm_component_found(self, comp_name, comp_interface):
        comp_display_name = comp_interface.display_name if isinstance(comp_interface.display_name, str) else comp_interface.display_name.en
        alg_config_widget = HSDComponentWidget(self.controller, comp_name, comp_display_name, ComponentType.ALGORITHM, comp_interface.contents, self.comp_id, self.device_config_widget)
        self.comp_id += 1
        self.controller.add_component_config_widget(alg_config_widget)
        self.device_config_widget.layout().addWidget(alg_config_widget)
        
        comp_status = self.controller.get_component_status(comp_name)

        algorithm_plot_params = self.controller.get_plot_params(comp_name, ComponentType.ALGORITHM, comp_interface, comp_status)
        if algorithm_plot_params is not None:
            alg_type = algorithm_plot_params.alg_type
            if alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_FFT.value:
                alg_plot_widget = PlotBarFFTWidget(self.controller, comp_name, comp_display_name=comp_display_name, fft_len = algorithm_plot_params.fft_len, fft_input_freq_hz = algorithm_plot_params.fft_sample_freq, p_id=self.graph_id, parent=self.plots_widget)
                self.graph_id +=1
                self.controller.add_plot_widget(alg_plot_widget)
                self.plots_widget.layout().addWidget(alg_plot_widget)
                alg_plot_widget.setVisible(True)
            elif alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_ANOMALY_DETECTOR.value:
                anomaly_classes = self.controller.get_anomaly_classes()
                ai_tool = self.controller.get_ai_anomaly_tool()
                alg_plot_widget = AnomalyDetectorWidget(self.controller, comp_name, comp_display_name, anomaly_classes=anomaly_classes, ai_tool=ai_tool, p_id=self.graph_id, parent=self.plots_widget)
                self.graph_id +=1
                self.controller.add_plot_widget(alg_plot_widget)
                self.plots_widget.layout().addWidget(alg_plot_widget)
                alg_plot_widget.setVisible(True)
            elif alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_CLASSIFIER.value:
                # out_classes = self.controller.get_output_classes()
                # algo_out_map = [c for c in comp_interface.contents if c.name == "algo_out"]
                # if len(algo_out_map) == 1:
                #     out_fields = algo_out_map[0].schema.fields
                #     w_signal = False
                #     w_confidence = False
                #     plots_array = {}
                #     for f in out_fields:
                #         f_display_name = f.display_name if isinstance(f.display_name, str) else f.display_name.en
                        
                #         # if f.name == "class":#NOTE to be implemented if needed in the future defined format
                #         #     out_class = True
                        
                #         # if f.name == "signal":#NOTE to be implemented if needed in the future defined format
                #         #     w_signal = True
                        
                #         if f.name == "confidence":
                #             w_confidence = True
                #     out_classes = self.controller.get_output_classes()
                #     ai_tool = self.controller.get_ai_tool()
                #     alg_plot_widget = ClassifierOutputWidget(self.controller, comp_name, comp_display_name, out_classes=out_classes, ai_tool=ai_tool, with_signal=w_signal, with_confidence=w_confidence, p_id=self.graph_id, parent=self.plots_widget)
                #     # alg_plot_widget.remove_spacers(True, True)
                #     self.graph_id +=1
                # else:
                out_classes = self.controller.get_output_classes()
                ai_tool = self.controller.get_ai_classifier_tool()
                alg_plot_widget = ClassifierOutputWidget(self.controller, comp_name, comp_display_name, out_classes=out_classes, ai_tool=ai_tool, p_id=self.graph_id, parent=self.plots_widget)
                self.graph_id +=1
                self.controller.add_plot_widget(alg_plot_widget)
                self.plots_widget.layout().addWidget(alg_plot_widget)
                alg_plot_widget.setVisible(True)
        
        self.controller.fill_component_status(comp_name)        

    @Slot(str, dict)
    def s_actuator_component_found(self, comp_name, comp_interface):
        #create a HSDComponentWidget
        comp_display_name = comp_interface.display_name if isinstance(comp_interface.display_name, str) else comp_interface.display_name.en
        act_config_widget = HSDComponentWidget(self.controller, comp_name, comp_display_name, ComponentType.ACTUATOR, comp_interface.contents, self.comp_id, self.device_config_widget)
        self.comp_id += 1
        self.controller.add_component_config_widget(act_config_widget)
        self.device_config_widget.layout().addWidget(act_config_widget)

        self.controller.fill_component_status(comp_name)
    
    @Slot(str, SensorPlotParams)
    def s_sensor_component_updated(self, comp_name, plot_params:SensorPlotParams):
        enabled = plot_params.enabled
        self.controller.update_plot_widget(comp_name, plot_params, enabled)

    @Slot(str, AlgorithmPlotParams)
    def s_algorithm_component_updated(self, comp_name, plot_params:AlgorithmPlotParams):
        enabled = plot_params.enabled
        self.controller.update_plot_widget(comp_name, plot_params, enabled)

    @Slot(str, AlgorithmPlotParams)
    def s_actuator_component_updated(self, comp_name, plot_params:ActuatorPlotParams):
        enabled = plot_params.enabled
        self.controller.update_plot_widget(comp_name, plot_params, enabled)
    
    def endisable_log_controller_components(self, status):
        if isinstance(self.log_control_widget, HSDAdvLogControlWidget):
            # self.log_control_widget.interface_combobox.setEnabled(not status)
            self.log_control_widget.save_config_button.setEnabled(not status)
            self.log_control_widget.load_config_button.setEnabled(not status)
            self.log_control_widget.time_spinbox.setEnabled(not status)
    
    def set_anomaly_classes(self, anomaly_classes):
        self.anomaly_classes = anomaly_classes

    def set_output_classes(self, output_classes):
        self.output_classes = output_classes

    def set_ai_anomaly_tool(self, ai_anomaly_tool):
        self.ai_anomaly_tool = ai_anomaly_tool

    def set_ai_classifier_tool(self, ai_classifier_tool):
        self.ai_classifier_tool = ai_classifier_tool
    
    def add_header_widget(self, widget):
        self.widget_header.layout().addWidget(widget)
    
    @Slot(bool)
    def s_is_logging(self, status:bool, interface:int):
        self.endisable_logging_message(status)
        if self.controller.auto_started == False:
            self.select_all_button.setEnabled(not status)
            self.endisable_log_controller_components(status)
            self.endisable_component_config(status, ["tags_info","device_info"])
        else:
            self.endisable_component(not status, "tags_info")

    def s_is_waiting_autostart(self, status:bool):
        self.endisable_component(status, "tags_info")

    @Slot(bool)
    def s_bandwidth_exceeded(self, status:bool):
        if status:
            error_msg = "Safe bandwidth limit exceeded.\nConsider disabling sensors or lowering ODRs to avoid possible data corruption.\nHave a look in {} log file for more detailed info.".format(self.log_file_name if self.log_file_name is not None else "application")
            log.warning(error_msg)
            self.set_error_message(True, error_msg)
        else:
            self.set_error_message(False, "")

    @Slot(bool, str)
    def s_streaming_error(self, status, message:str):
        self.set_error_message(status, message)

    def s_auto_started(self, status):
        self.controller.auto_started = not self.controller.auto_started
        self.select_all_button.setEnabled(not status)
        self.endisable_component_config(status, ["tags_info","device_info"])
        self.endisable_log_controller_components(status)
        self.automode_widget.setEnabled(not status)

    def s_pnpl_response_received(self, command, response):
        """Handle PNPL response and show error/warning if needed."""
        try:
            response_dict = json.loads(response) if isinstance(response, str) else dict(response)
        except Exception:
            response_dict = {"raw_response": response}

        error_msg = None
        warning_msg = None

        if "PnPL_Error" in response_dict:
            error_msg = response_dict["PnPL_Error"]
        elif "PnPL_Warning" in response_dict:
            warning_msg = response_dict["PnPL_Warning"]
        elif (
            "PnPL_Response" in response_dict
            and "message" in response_dict["PnPL_Response"]
        ):
            msg = response_dict["PnPL_Response"]["message"]
            if "PnPL_Error" in msg: # PnPL_Error wins among the PnPL_Response status field
                error_msg = msg
            elif "PnPL_Warning" in msg: # PnPL_Warning wins among the PnPL_Response status field
                warning_msg = msg
            elif "status" in response_dict["PnPL_Response"]: # If PnPL_Error or PnPL_Warning are not present, check the status (Property set error)
                if response_dict["PnPL_Response"]["status"] == False:
                    if "value" in response_dict["PnPL_Response"]:
                        prop_value = response_dict["PnPL_Response"]["value"]
                        error_msg = f"Error response generated by {command} Message.\nCurrent value remains: {prop_value}"
                    else:
                        error_msg = f"Error response generated by {command}."
            
        if error_msg:
            msg = error_msg if isinstance(error_msg, str) else json.dumps(error_msg, indent=4)
            self.show_pnpl_response_error(msg)
        if warning_msg:
            msg = warning_msg if isinstance(warning_msg, str) else json.dumps(warning_msg, indent=4)
            self.show_pnpl_response_warning(msg)

    def show_pnpl_response_error(self, error_msg):
        """Show a message box with the PnPL response error."""
        msg_box = QMessageBox(QMessageBox.Critical, "PnPL Response Error", str(error_msg), parent=self.widget_header)
        msg_box.setStyleSheet("QMessageBox { background-color: rgb(44, 49, 60); }")
        msg_box.exec()

    def show_pnpl_response_warning(self, warning_msg):
        """Show a message box with the PnPL response warning."""
        msg_box = QMessageBox(QMessageBox.Warning, "PnPL Response Warning", str(warning_msg), parent=self.widget_header)
        msg_box.setStyleSheet("QMessageBox { background-color: rgb(44, 49, 60); }")
        msg_box.exec()
