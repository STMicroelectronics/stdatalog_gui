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

"""
Device configuration page for HSDatalog2: wires components and plots per device status.

This module implements ``HSD_DeviceConfigPage``, a concrete device configuration page
that reacts to discovered components (sensors, algorithms, actuators, and special
components like log controllers and tags), creates the related configuration widgets,
and, when appropriate, attaches plotting widgets based on the controller-provided plot
parameters. It also manages UI enablement during logging/auto-start, shows bandwidth
warnings, and surfaces PNPL errors/warnings via message boxes.

Highlights
----------
- Dynamically builds configuration and plotting widgets as components are discovered.
- Supports algorithm plots (FFT bar, anomaly detector, classifier output).
- Applies enable/disable behavior to configuration widgets during logging.
- Displays safe bandwidth exceeded warnings and surfaces PNPL errors/warnings.
"""
import os
import json

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from stdatalog_core.HSD_link.HSDLink import HSDLink
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
from stdatalog_gui.HSD_GUI.Widgets.HSDComponentWidget import HSDALSComponentWidget, \
    HSDComponentWidget, HSDDeviceInfoComponentWidget
from stdatalog_gui.HSD_GUI.Widgets.TagsInfoWidget import TagsInfoWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotLinesWidget import HSDPlotLinesWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotImageWidget import HSDPlotImageWidget


from stdatalog_gui.Widgets.Plots.PlotBarFFTWidget import PlotBarFFTWidget
from stdatalog_gui.Widgets.Plots.ClassifierOutputWidget import ClassifierOutputWidget
from stdatalog_gui.Utils.PlotParams import (
    ActuatorPlotParams,
    PlotPAmbientParams,
    PlotPMotionParams,
    PlotPObjectParams,
    PlotPPresenceParams,
    SensorLightPlotParams,
    SensorPlotParams,
    AlgorithmPlotParams,
    SensorPowerPlotParams,
    SensorPresenscePlotParams,
    SensorRangingPlotParams,
    SensorCameraPlotParams
)
from stdatalog_gui.STDTDL_Controller import ComponentType


import stdatalog_pnpl.DTDL.dtdl_utils as DTDLUtils

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class HSD_DeviceConfigPage(STDTDL_DeviceConfigPage):
    """Concrete device configuration page for HSDatalog2.

    Parameters
    ----------
    page_widget : QWidget
        The container widget hosting the configuration UI.
    controller : STDTDL_Controller
        The application controller that provides component discovery, statuses, and
        plot parameters.

    Attributes
    ----------
    anomaly_classes : dict[str, str]
        Mapping from anomaly class display names to image paths.
    output_classes : dict[str, str]
        Mapping from classifier output display names to image paths.
    threads_stop_flags : list
        Placeholder list for thread stop flags.
    sensor_data_files : list
        Placeholder list for sensor data file paths.
    ignored_components : list[str]
        Components ignored when discovered (e.g., ``applications_stblesensor``).
    graph_id : int
        Incremental identifier used when creating plot widgets.
    log_file_name : str | None
        Basename of the current application log file, if available.
    """

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

        self.ignored_components = ["applications_stblesensor", "wifi_config"]

        self.graph_id = 0

        self.log_file_name = None
        for handler in log.parent.handlers:
            if hasattr(handler, "baseFilename"):
                self.log_file_name = os.path.basename(getattr(handler, "baseFilename"))

    @Slot(str, dict)
    def s_component_found(self, comp_name, comp_interface):
        """Handle discovery of non-sensor components and create related widgets.

        Parameters
        ----------
        comp_name : str
            Component identifier name.
        comp_interface : Any
            Interface object carrying metadata, display name, and contents.

        Notes
        -----
        - Creates and registers log controller, tags info, automode, or a generic
          component widget depending on ``comp_name``.
        - Fills component status via the controller for UI initialization.
        """
        # create a ComponentWidget
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        if comp_name == "log_controller":
            c_status = self.controller.get_component_status(comp_name)
            if "controller_type" in c_status["log_controller"]:
                controller_type = c_status["log_controller"]["controller_type"]
                if controller_type == 0:  # 0 == HSD Advanced log controller
                    self.log_control_widget = HSDAdvLogControlWidget(
                        self.controller,
                        comp_contents=comp_interface.contents,
                        parent=self.widget_header,
                    )
                    self.controller.set_rtc_time()
                elif controller_type == 1:  # 1 == App classification controller
                    self.log_control_widget = AppClassificationControlWidget(
                        self.controller,
                        comp_contents=comp_interface.contents,
                        parent=self.widget_header,
                    )
                elif controller_type == 2:  # 2 == HSD Simple log controller
                    self.log_control_widget = HSDLogControlWidget(
                        self.controller,
                        comp_contents=comp_interface.contents,
                        parent=self.widget_header,
                    )
                    self.controller.set_rtc_time()
            else:
                self.log_control_widget = HSDLogControlWidget(
                    self.controller,
                    comp_contents=comp_interface.contents,
                    parent=self.widget_header,
                )
                self.controller.set_rtc_time()
            self.controller.add_component_config_widget(self.log_control_widget)
            self.add_header_widget(self.log_control_widget)
            self.controller.fill_component_status(comp_name)
        elif comp_name == "tags_info":
            self.tags_info_widget = TagsInfoWidget(
                self.controller,
                comp_contents=comp_interface.contents,
                c_id=1,
                parent=self.widget_special_componenents,
            )
            self.tags_info_widget.clicked_show_button()
            self.controller.add_component_config_widget(self.tags_info_widget)
            self.widget_special_componenents.layout().addWidget(self.tags_info_widget)
            self.controller.fill_component_status(comp_name)
        elif comp_name in self.ignored_components:
            pass
        elif comp_name == "automode":
            fw_info = self.controller.hsd_link.get_firmware_info(self.controller.device_id)
            if (
                HSDLink.get_versiontuple(fw_info["firmware_info"]["fw_version"]) >=
                HSDLink.get_versiontuple("1.2.0")
            ):
                self.automode_widget = HSDAutoModeWidget(
                    self.controller,
                    comp_contents=comp_interface.contents,
                    c_id=0,
                    parent=self.widget_special_componenents,
                )
                self.controller.add_component_config_widget(self.automode_widget)
                self.widget_special_componenents.layout().addWidget(self.automode_widget)
                self.controller.fill_component_status(comp_name)
        elif comp_name == "DeviceInformation":
            comp_config_widget = HSDDeviceInfoComponentWidget(
                self.controller,
                comp_name,
                comp_display_name,
                "",
                comp_interface.contents,
                self.comp_id,
                self.device_config_widget,
            )
            self.controller.add_component_config_widget(comp_config_widget)
            self.device_config_widget.layout().addWidget(comp_config_widget)
            self.controller.fill_component_status(comp_name)
            self.comp_id += 1
        else:
            comp_config_widget = HSDComponentWidget(
                self.controller,
                comp_name,
                comp_display_name,
                "",
                comp_interface.contents,
                self.comp_id,
                self.device_config_widget,
            )
            self.controller.add_component_config_widget(comp_config_widget)
            self.device_config_widget.layout().addWidget(comp_config_widget)
            self.controller.fill_component_status(comp_name)
            self.comp_id += 1


    @Slot(str, dict)
    def s_sensor_component_found(self, comp_name, comp_interface):
        """Handle sensor discovery and attach configuration and plot widgets.

        Parameters
        ----------
        comp_name : str
            Sensor component name.
        comp_interface : Any
            Interface object carrying metadata and contents.

        Notes
        -----
        - Chooses specialized configuration widgets when ``_mlc`` or ``_als`` appear in
          the sensor name; otherwise uses a generic component widget.
        - Builds an appropriate plot widget based on ``SensorPlotParams`` subtype.
        - Sets initial visibility from the sensor enabled state and updates controller
          bandwidth checks.
        """
        # create a HSDComponentWidget
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        if "_mlc" in comp_name:
            sensor_config_widget = HSDMCLConfigurationWidget(
                self.controller,
                comp_name,
                comp_display_name,
                ComponentType.SENSOR,
                comp_interface.contents,
                self.comp_id,
                self.device_config_widget,
            )
        elif "_als" in comp_name:
            sensor_config_widget = HSDALSComponentWidget(
                self.controller,
                comp_name,
                comp_display_name,
                ComponentType.SENSOR,
                comp_interface.contents,
                self.comp_id,
                self.device_config_widget,
            )
        else:
            sensor_config_widget = HSDComponentWidget(
                self.controller,
                comp_name,
                comp_display_name,
                ComponentType.SENSOR,
                comp_interface.contents,
                self.comp_id,
                self.device_config_widget,
            )

        self.controller.add_component_config_widget(sensor_config_widget)
        self.device_config_widget.layout().addWidget(sensor_config_widget)

        comp_status = self.controller.get_component_status(comp_name)

        try:
            enabled = self.controller.is_sensor_enabled(comp_name)
            self.comp_id += 1
            sensor_plot_params: SensorPlotParams = self.controller.get_plot_params(
                comp_name, ComponentType.SENSOR, comp_interface, comp_status
            )
            if sensor_plot_params is not None:
                if isinstance(sensor_plot_params, SensorRangingPlotParams):
                    sensor_plot_widget = HSDPlotToFWidget(
                        self.controller,
                        comp_name,
                        comp_display_name,
                        sensor_plot_params,
                        self.graph_id,
                        self.plots_widget,
                    )
                elif isinstance(sensor_plot_params, SensorPresenscePlotParams):
                    plots_params_dict = {}
                    s_enabled = comp_status[comp_name].get("enable")
                    embedded_compensation = comp_status[comp_name].get(
                        "embedded_compensation"
                    )
                    software_compensation = comp_status[comp_name].get(
                        "software_compensation"
                    )
                    plots_params_dict["Ambient"] = PlotPAmbientParams(
                        comp_name, s_enabled, 1
                    )
                    plots_params_dict["Object"] = PlotPObjectParams(
                        comp_name,
                        s_enabled,
                        4,
                        embedded_compensation,
                        software_compensation,
                    )
                    plots_params_dict["Presence"] = PlotPPresenceParams(
                        comp_name,
                        s_enabled,
                        1,
                        embedded_compensation,
                        software_compensation,
                    )
                    plots_params_dict["Motion"] = PlotPMotionParams(
                        comp_name,
                        s_enabled,
                        1,
                        embedded_compensation,
                        software_compensation,
                    )
                    sensor_plot_params.plots_params_dict = plots_params_dict
                    sensor_plot_widget = HSDPlotTMOSWidget(
                        self.controller,
                        comp_name,
                        comp_display_name,
                        sensor_plot_params,
                        self.graph_id,
                        self.plots_widget,
                    )
                elif isinstance(sensor_plot_params, SensorLightPlotParams):
                    sensor_plot_widget = HSDPlotALSWidget(
                        self.controller,
                        comp_name,
                        comp_display_name,
                        sensor_plot_params,
                        self.graph_id,
                        self.plots_widget,
                    )
                elif isinstance(sensor_plot_params, SensorPowerPlotParams):
                    sensor_plot_widget = HSDPlotPOWWidget(
                        self.controller,
                        comp_name,
                        comp_display_name,
                        sensor_plot_params,
                        self.graph_id,
                        self.plots_widget,
                    )

                elif isinstance(sensor_plot_params,SensorCameraPlotParams):
                    sensor_plot_widget = HSDPlotImageWidget(
                        self.controller, 
                        comp_name, 
                        comp_display_name, 
                        sensor_plot_params, 
                        self.graph_id, 
                        self.plots_widget
                    ) 
                
                else:
                    sensor_plot_widget = HSDPlotLinesWidget(
                        self.controller,
                        comp_name,
                        comp_display_name,
                        sensor_plot_params,
                        self.graph_id,
                        self.plots_widget,
                    )
                self.graph_id +=1
                self.controller.add_plot_widget(sensor_plot_widget, enabled)
                self.plots_widget.layout().addWidget(sensor_plot_widget)
                log.debug(f"comp_name: {comp_name} - status: {enabled}")
                sensor_plot_widget.setVisible(enabled)
        except Exception as e:
            print(e)
            log.warning(
                f"It is impossible to know the Sensor [{comp_name}] enabling status from the "
                "FW device status"
            )

        self.controller.fill_component_status(comp_name)
        self.controller.check_hsd_bandwidth()

    @Slot(str, dict)
    def s_algorithm_component_found(self, comp_name, comp_interface):
        """Handle algorithm discovery and attach configuration and plot widgets.

        Parameters
        ----------
        comp_name : str
            Algorithm component name.
        comp_interface : Any
            Interface carrying algorithm metadata and contents.
        """
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        alg_config_widget = HSDComponentWidget(
            self.controller,
            comp_name,
            comp_display_name,
            ComponentType.ALGORITHM,
            comp_interface.contents,
            self.comp_id,
            self.device_config_widget,
        )
        self.comp_id += 1
        self.controller.add_component_config_widget(alg_config_widget)
        self.device_config_widget.layout().addWidget(alg_config_widget)

        comp_status = self.controller.get_component_status(comp_name)

        algorithm_plot_params = self.controller.get_plot_params(
            comp_name, ComponentType.ALGORITHM, comp_interface, comp_status
        )
        if algorithm_plot_params is not None:
            alg_type = algorithm_plot_params.alg_type
            if alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_FFT.value:
                alg_plot_widget = PlotBarFFTWidget(
                    self.controller,
                    comp_name,
                    comp_display_name=comp_display_name,
                    fft_len=algorithm_plot_params.fft_len,
                    fft_input_freq_hz=algorithm_plot_params.fft_sample_freq,
                    p_id=self.graph_id,
                    parent=self.plots_widget,
                )
                self.graph_id +=1
                self.controller.add_plot_widget(alg_plot_widget)
                self.plots_widget.layout().addWidget(alg_plot_widget)
                alg_plot_widget.setVisible(True)
            elif alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_ANOMALY_DETECTOR.value:
                anomaly_classes = self.controller.get_anomaly_classes()
                ai_tool = self.controller.get_ai_anomaly_tool()
                alg_plot_widget = AnomalyDetectorWidget(
                    self.controller,
                    comp_name,
                    comp_display_name,
                    anomaly_classes=anomaly_classes,
                    ai_tool=ai_tool,
                    p_id=self.graph_id,
                    parent=self.plots_widget,
                )
                self.graph_id +=1
                self.controller.add_plot_widget(alg_plot_widget)
                self.plots_widget.layout().addWidget(alg_plot_widget)
                alg_plot_widget.setVisible(True)
            elif alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_CLASSIFIER.value:
                out_classes = self.controller.get_output_classes()
                ai_tool = self.controller.get_ai_classifier_tool()
                alg_plot_widget = ClassifierOutputWidget(
                    self.controller,
                    comp_name,
                    comp_display_name,
                    out_classes=out_classes,
                    ai_tool=ai_tool,
                    p_id=self.graph_id,
                    parent=self.plots_widget,
                )
                self.graph_id +=1
                self.controller.add_plot_widget(alg_plot_widget)
                self.plots_widget.layout().addWidget(alg_plot_widget)
                alg_plot_widget.setVisible(True)

        self.controller.fill_component_status(comp_name)

    @Slot(str, dict)
    def s_actuator_component_found(self, comp_name, comp_interface):
        """Handle actuator discovery and attach configuration widget.

        Parameters
        ----------
        comp_name : str
            Actuator component name.
        comp_interface : Any
            Interface carrying actuator metadata and contents.
        """
        # create a HSDComponentWidget
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        act_config_widget = HSDComponentWidget(
            self.controller,
            comp_name,
            comp_display_name,
            ComponentType.ACTUATOR,
            comp_interface.contents,
            self.comp_id,
            self.device_config_widget,
        )
        self.comp_id += 1
        self.controller.add_component_config_widget(act_config_widget)
        self.device_config_widget.layout().addWidget(act_config_widget)

        self.controller.fill_component_status(comp_name)

    @Slot(str, SensorPlotParams)
    def s_sensor_component_updated(self, comp_name, plot_params:SensorPlotParams):
        """Update the plot widget associated with a sensor component.

        Parameters
        ----------
        comp_name : str
            Sensor component name.
        plot_params : SensorPlotParams
            Updated plot parameters including enable state.
        """
        enabled = plot_params.enabled
        self.controller.update_plot_widget(comp_name, plot_params, enabled)

    @Slot(str, AlgorithmPlotParams)
    def s_algorithm_component_updated(self, comp_name, plot_params:AlgorithmPlotParams):
        """Update the plot widget associated with an algorithm component.

        Parameters
        ----------
        comp_name : str
            Algorithm component name.
        plot_params : AlgorithmPlotParams
            Updated plot parameters including enable state.
        """
        enabled = plot_params.enabled
        self.controller.update_plot_widget(comp_name, plot_params, enabled)

    @Slot(str, AlgorithmPlotParams)
    def s_actuator_component_updated(self, comp_name, plot_params:ActuatorPlotParams):
        """Update the plot widget associated with an actuator component.

        Parameters
        ----------
        comp_name : str
            Actuator component name.
        plot_params : ActuatorPlotParams
            Updated plot parameters including enable state.
        """
        enabled = plot_params.enabled
        self.controller.update_plot_widget(comp_name, plot_params, enabled)

    def endisable_log_controller_components(self, status):
        """Enable or disable log controller UI elements based on status.

        Parameters
        ----------
        status : bool
            If ``True``, disable save/load/time widgets; otherwise enable them.
        """
        if isinstance(self.log_control_widget, HSDAdvLogControlWidget):
            # self.log_control_widget.interface_combobox.setEnabled(not status)
            self.log_control_widget.save_config_button.setEnabled(not status)
            self.log_control_widget.load_config_button.setEnabled(not status)
            self.log_control_widget.time_spinbox.setEnabled(not status)

    def set_anomaly_classes(self, anomaly_classes):
        """Set anomaly class mapping.

        Parameters
        ----------
        anomaly_classes : dict[str, str]
            Mapping from anomaly display names to image paths.
        """
        self.anomaly_classes = anomaly_classes

    def set_output_classes(self, output_classes):
        """Set classifier output class mapping.

        Parameters
        ----------
        output_classes : dict[str, str]
            Mapping from classifier display names to image paths.
        """
        self.output_classes = output_classes

    def set_ai_anomaly_tool(self, ai_anomaly_tool):
        """Set the active AI anomaly tool mapping.

        Parameters
        ----------
        ai_anomaly_tool : dict[str, str]
            Mapping from tool display name to image path.
        """
        self.ai_anomaly_tool = ai_anomaly_tool

    def set_ai_classifier_tool(self, ai_classifier_tool):
        """Set the active AI classifier tool mapping.

        Parameters
        ----------
        ai_classifier_tool : dict[str, str]
            Mapping from tool display name to image path.
        """
        self.ai_classifier_tool = ai_classifier_tool

    def add_header_widget(self, widget):
        """Add a widget to the header area of the configuration page.

        Parameters
        ----------
        widget : QWidget
            Widget to be added to the header layout.
        """
        self.widget_header.layout().addWidget(widget)

    @Slot(bool)
    def s_is_logging(self, status:bool, interface:int):
        """React to logging state changes and toggle UI elements.

        Parameters
        ----------
        status : bool
            Logging state; ``True`` when logging starts.
        interface : int
            Interface identifier (e.g., USB/Serial/SD). Used for controller logic.
        """
        self.endisable_logging_message(status)
        if self.controller.auto_started == False:
            self.select_all_button.setEnabled(not status)
            self.endisable_log_controller_components(status)
            self.endisable_component_config(status, ["tags_info","device_info"])
        else:
            self.endisable_component(not status, "tags_info")

    def s_is_waiting_autostart(self, status:bool):
        """Enable/disable the tags info component while waiting for auto-start.

        Parameters
        ----------
        status : bool
            Whether the system is waiting for auto-start.
        """
        self.endisable_component(status, "tags_info")

    @Slot(bool)
    def s_bandwidth_exceeded(self, status:bool):
        """Show or clear a bandwidth exceeded warning message.

        Parameters
        ----------
        status : bool
            ``True`` to show the warning; ``False`` to clear it.
        """
        if status:
            error_msg = (
                "Safe bandwidth limit exceeded.\n"
                "Consider disabling sensors or lowering ODRs to avoid possible data "
                "corruption.\n"
                f"Have a look in {self.log_file_name if self.log_file_name is not None else 'application'} log file for more detailed info."
            )
            log.warning(error_msg)
            self.set_error_message(True, error_msg)
        else:
            self.set_error_message(False, "")

    @Slot(bool, str)
    def s_streaming_error(self, status, message:str):
        """Set the error message coming from streaming failures.

        Parameters
        ----------
        status : bool
            Error state to apply. If ``True``, the error message will be shown and 
            logging will be stopped; if ``False``, the error message will be cleared.
        message : str
            Message describing the streaming error.
        """
        self.set_error_message(status, message)
        if status:
            self.controller.stop_log()

    def s_auto_started(self, status):
        """Toggle auto-start state and update UI enablement accordingly.

        Parameters
        ----------
        status : bool
            Auto-start signal state used to toggle enablement.
        """
        self.controller.auto_started = not self.controller.auto_started
        self.select_all_button.setEnabled(not status)
        self.endisable_component_config(status, ["tags_info","device_info"])
        self.endisable_log_controller_components(status)
        self.automode_widget.setEnabled(not status)

    def s_pnpl_response_received(self, command, response):
        """Handle PNPL response and show error or warning if needed.

        Parameters
        ----------
        command : str
            The PNPL command that generated the response.
        response : str | dict
            A JSON string or dictionary containing PNPL response details.

        Notes
        -----
        - Attempts to parse JSON responses; falls back to a raw dictionary when parsing
            fails.
        - Prefers ``PnPL_Error`` over ``PnPL_Warning`` when both are present.
        - Shows message boxes for errors and warnings.
        """
        try:
            response_dict = (
                json.loads(response) if isinstance(response, str) else dict(response)
            )
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
            if "PnPL_Error" in msg:  # PnPL_Error wins among the PnPL_Response status field
                error_msg = msg
            elif "PnPL_Warning" in msg:  # PnPL_Warning wins among the PnPL_Response status field
                warning_msg = msg
            elif (
                "status" in response_dict["PnPL_Response"]
            ):  # If PnPL_Error or PnPL_Warning are not present, check the status
                if response_dict["PnPL_Response"]["status"] == False:
                    if "value" in response_dict["PnPL_Response"]:
                        prop_value = response_dict["PnPL_Response"]["value"]
                        error_msg = (
                            f"Error response generated by {command} Message.\n"
                            f"Current value remains: {prop_value}"
                        )
                    else:
                        error_msg = f"Error response generated by {command}."

        if error_msg:
            msg = (
                error_msg
                if isinstance(error_msg, str)
                else json.dumps(error_msg, indent=4)
            )
            self.show_pnpl_response_error(msg)
        if warning_msg:
            msg = (
                warning_msg
                if isinstance(warning_msg, str)
                else json.dumps(warning_msg, indent=4)
            )
            self.show_pnpl_response_warning(msg)

    def show_pnpl_response_error(self, error_msg):
        """Show a message box with the PNPL response error.

        Parameters
        ----------
        error_msg : str
            The error message to display.

        Returns
        -------
        None
        """
        msg_box = QMessageBox(
            QMessageBox.Critical,
            "PnPL Response Error",
            str(error_msg),
            parent=self.widget_header,
        )
        msg_box.setStyleSheet("QMessageBox { background-color: rgb(44, 49, 60); }")
        msg_box.exec()

    def show_pnpl_response_warning(self, warning_msg):
        """Show a message box with the PNPL response warning.

        Parameters
        ----------
        warning_msg : str
            The warning message to display.

        Returns
        -------
        None
        """
        msg_box = QMessageBox(
            QMessageBox.Warning,
            "PnPL Response Warning",
            str(warning_msg),
            parent=self.widget_header,
        )
        msg_box.setStyleSheet("QMessageBox { background-color: rgb(44, 49, 60); }")
        msg_box.exec()
