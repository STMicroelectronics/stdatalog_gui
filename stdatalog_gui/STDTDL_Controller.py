#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    STDTDL_Controller.py
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
"""Controller interfaces and signals for the ST DTDL GUI.

This module defines the abstract controller class and related enums that coordinate the
ST DTDL GUI. The controller exposes Qt signals for device connection state, component
discovery/updates/removal, telemetry, and plotting metadata, and provides abstract
operations for device communication and configuration management.

Responsibilities:
- Own and expose signals for GUI pages/widgets to react to hardware state changes.
- Load DTDL device templates and emit discovery signals for sensors/algorithms/actuators.
- Track component configuration widgets and plugin plot widgets.
- Bridge to the Data Toolkit pipeline to reflect component status.

Design Notes:
- This file focuses on contracts and orchestration; concrete implementations must provide
    device-specific logic by implementing the abstract methods.
- Docstrings follow the project style with Parameters/Returns sections.
"""

from abc import abstractmethod
from enum import Enum

from PySide6.QtCore import QObject, Signal

from stdatalog_dtk.HSD_DataToolkit_Pipeline import HSD_DataToolkit_Pipeline
from stdatalog_pnpl.DTDL.device_template_manager import DeviceTemplateManager
from stdatalog_pnpl.DTDL.device_template_model import InterfaceElement
from stdatalog_pnpl.DTDL.dtdl_utils import (
    DTDL_ACTUATORS_ID_COMP_KEY,
    DTDL_ALGORITHMS_ID_COMP_KEY,
    DTDL_SENSORS_ID_COMP_KEY,
)
from stdatalog_gui.Utils.PlotParams import (
    SensorPlotParams,
    AlgorithmPlotParams,
    ActuatorPlotParams,
)

class ComponentType(Enum):
    """Component categories handled by the controller.

    Values:
    - SENSOR: Hardware sensor component.
    - ALGORITHM: Firmware/processing algorithm component.
    - OTHER: Any other component not categorized.
    - ACTUATOR: Hardware actuator component (Motor control telemetries).
    - NONE: No component (default/unset).
    """
    SENSOR = 0
    ALGORITHM = 1
    OTHER = 2
    ACTUATOR = 3
    NONE = -1

class STDTDL_Controller(QObject):
    """Abstract base controller for the ST DTDL GUI.

    Central orchestrator that exposes Qt signals, loads DTDL templates to discover
    components, manages component configuration widgets, and integrates with the Data
    Toolkit pipeline. Concrete subclasses must implement device-specific operations.

    Signals (selection):
    - sig_device_connected (bool): Device connection state changes.
    - sig_component_found/sensor/algorithm/actuator: DTDL-driven discovery events.
    - sig_component_updated (str, dict): Generic component update.
    - sig_sensor_component_updated (str, SensorPlotParams): Sensor plot metadata.
    - sig_algorithm_component_updated (str, AlgorithmPlotParams): Algorithm plot metadata.
    - sig_actuator_component_updated (str, ActuatorPlotParams): Actuator plot metadata.
    - sig_component_removed (str): Component removed from the system.
    - sig_component_config_widget_width_updated (int): UI width updates for config widgets.
    - sig_plot_window_time_updated (float): Plot window duration changes.
    - Various TMOS/ToF detections and file conversion notifications.

    Attributes:
    - device_id (int): Current device index (default 0).
    - plots_layout: Layout instance used to place plot widgets.
    - components_dtdl (dict): Map of component name -> DTDL interface/model.
    - components_status (dict): Component status data from firmware.
    - cconfig_widgets (dict): Component name -> configuration widget instance.
    - plot_widgets (dict): Component name -> plot widget instance.
    - plugin_plot_widgets (list): Extra plot widgets added by plugins.
    - data_pipeline: Optional Data Toolkit pipeline instance.
    - qt_app: Reference to QApplication for UI processing as needed.
    """

    # Signals
    sig_device_connected = Signal(bool)
    sig_com_init_error = Signal()

    sig_dtm_loading_started = Signal()
    sig_dtm_loading_completed = Signal()

    sig_component_found = Signal(str, InterfaceElement)
    sig_sensor_component_found = Signal(str, InterfaceElement)
    sig_actuator_component_found = Signal(str, InterfaceElement)
    sig_algorithm_component_found = Signal(str, InterfaceElement)

    sig_component_updated = Signal(str, dict)
    sig_sensor_component_updated = Signal(str, SensorPlotParams)
    sig_algorithm_component_updated = Signal(str, AlgorithmPlotParams)
    sig_actuator_component_updated = Signal(str, ActuatorPlotParams)

    sig_component_removed = Signal(str)

    sig_telemetry_received = Signal(str)

    sig_component_config_widget_width_updated = Signal(int)

    sig_plot_window_time_updated = Signal(float)

    sig_mlc_config_loaded = Signal(str, str)
    sig_ispu_config_loaded = Signal(str, str, str)

    sig_wav_conversion_completed = Signal(str, str)
    sig_offline_plots_completed = Signal()

    sig_tmos_presence_detected = Signal(bool,str,str)
    sig_tmos_motion_detected = Signal(bool,str,str)

    sig_tof_presence_detected = Signal(bool,str)
    sig_tof_presence_detected_in_roi = Signal(bool,int,str)

    sig_autologging_is_stopping = Signal(bool)
    sig_logging = Signal(bool, int)
    sig_detecting = Signal(bool)

    sig_pnpl_response_received = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.device_id = 0  # default device id
        self.plots_layout = None
        self.components_dtdl = dict()  # From DTDL DeviceModel
        self.components_status = dict()  # From FW
        self.cconfig_widgets = dict()  # {comp_name:CConfigWidget}
        self.plot_widgets = dict()
        # self.plugin_plot_widgets = dict()
        self.plugin_plot_widgets = []
        self.__dt_manager = None
        self.log_msg = ""
        self.detect_msg = ""
        self.data_pipeline = None
        self.qt_app = None

    def set_Qt_app(self, qt_app):
        """Set the Qt application instance.

        Parameters:
        - qt_app: QApplication or compatible application instance.

        Returns:
        - None
        """
        self.qt_app = qt_app

    def set_plots_layout(self, plots_layout):
        """Assign the layout used to host plot widgets.

        Parameters:
        - plots_layout: Layout object (e.g., QVBoxLayout) used for plots.

        Returns:
        - None
        """
        self.plots_layout = plots_layout

    def load_local_device_template(self, dev_template_json):
        """Load a local DTDL device template and emit discovery signals.

        Parameters:
        - dev_template_json (str | pathlib.Path): Path to the DTDL JSON template.

        Returns:
        - None
        """
        self.__dt_manager = DeviceTemplateManager(dev_template_json)
        self.components_dtdl = self.__dt_manager.get_components()
        for comp_name in self.components_dtdl.keys():
            if (
                ":" + DTDL_SENSORS_ID_COMP_KEY + ":"
                in self.components_dtdl[comp_name].id
            ):
                self.sig_sensor_component_found.emit(
                    comp_name, self.components_dtdl[comp_name]
                )
            elif (
                ":" + DTDL_ALGORITHMS_ID_COMP_KEY + ":"
                in self.components_dtdl[comp_name].id
            ):
                self.sig_algorithm_component_found.emit(
                    comp_name, self.components_dtdl[comp_name]
                )
            elif (
                ":" + DTDL_ACTUATORS_ID_COMP_KEY + ":"
                in self.components_dtdl[comp_name].id
            ):
                self.sig_actuator_component_found.emit(
                    comp_name, self.components_dtdl[comp_name]
                )
            else:
                self.sig_component_found.emit(
                    comp_name, self.components_dtdl[comp_name]
                )
        if self.data_pipeline is not None:
            self.data_pipeline.update_components_status(self.components_status)

    def get_component_config_widget(self, comp_name):
        """Retrieve a component's configuration widget by name.

        Parameters:
        - comp_name (str): Component name.

        Returns:
        - QWidget | None: The configuration widget if present, otherwise None.
        """
        if comp_name in self.cconfig_widgets:
            return self.cconfig_widgets[comp_name]
        else:
            return None

    def add_component_config_widget(self, cconfig_widget):
        """Register and show a component configuration widget.

        Parameters:
        - cconfig_widget (QWidget): Widget instance for the component.

        Returns:
        - None
        """
        self.cconfig_widgets[cconfig_widget.comp_name] = cconfig_widget
        self.cconfig_widgets[cconfig_widget.comp_name].setVisible(True)

    def remove_component_config_widget(self, comp_name):
        """Remove and delete a component configuration widget.

        Parameters:
        - comp_name (str): Name of the component whose widget is removed.

        Returns:
        - None
        """
        self.cconfig_widgets[comp_name].setVisible(False)
        self.cconfig_widgets[comp_name].deleteLater()
        self.cconfig_widgets.pop(comp_name)

    def hide_plot_widget(self, comp_name):
        """Hide a plot widget for the given component.

        Parameters:
        - comp_name (str): Component name whose plot widget is hidden.

        Returns:
        - None
        """
        self.plot_widgets[comp_name].setVisible(False)

    def show_plot_widget(self, comp_name):
        """Show a plot widget for the given component.

        Parameters:
        - comp_name (str): Component name whose plot widget is shown.

        Returns:
        - None
        """
        self.plot_widgets[comp_name].setVisible(True)

    def add_plugin_plot_widget(self, plot_widget):
        """Add a plugin-provided plot widget to the layout and internal list.

        Parameters:
        - plot_widget (QWidget): Plot widget to add.

        Returns:
        - None
        """
        self.plots_layout.addWidget(plot_widget)
        self.plugin_plot_widgets.append(plot_widget)

    def remove_plugin_plot_widget(self, plot_widget):
        """Remove and delete a previously added plugin plot widget.

        Parameters:
        - plot_widget (QWidget): Plot widget to remove.

        Returns:
        - None
        """
        plot_widget.setVisible(False)
        plot_widget.deleteLater()
        self.plugin_plot_widgets.remove(plot_widget)
        self.plots_layout.removeWidget(plot_widget)

    def clear_all_plugin_plot_widgets(self):
        """Remove and delete all plugin plot widgets from the layout.

        Parameters:
        - None

        Returns:
        - None
        """
        for plot_widget in self.plugin_plot_widgets:
            plot_widget.setVisible(False)
            plot_widget.deleteLater()
            self.plots_layout.removeWidget(plot_widget)
        self.plugin_plot_widgets.clear()

    def set_log_msg(self, log_msg):
        """Set the log status message shown in the UI.

        Parameters:
        - log_msg (str): Text for the logging message area.

        Returns:
        - None
        """
        self.log_msg = log_msg

    def set_detect_msg(self, detect_msg):
        """Set the detection status message shown in the UI.

        Parameters:
        - detect_msg (str): Text for the detecting message area.

        Returns:
        - None
        """
        self.detect_msg = detect_msg

    def set_component_config_width(self, width):
        """Emit a signal to update the component configuration widget width.

        Parameters:
        - width (int): Target width for component configuration widgets.

        Returns:
        - None
        """
        self.sig_component_config_widget_width_updated.emit(width)

    def create_data_pipeline(self):
        """Instantiate the Data Toolkit pipeline bound to this controller.

        Parameters:
        - None

        Returns:
        - None
        """
        self.data_pipeline = HSD_DataToolkit_Pipeline(self)

    def destroy_data_pipeline(self):
        """Tear down the Data Toolkit pipeline instance.

        Parameters:
        - None

        Returns:
        - None
        """
        self.data_pipeline = None

    def get_log_msg(self):
        """Get the current logging status message.

        Parameters:
        - None

        Returns:
        - str: Logging message.
        """
        return self.log_msg

    def get_detect_msg(self):
        """Get the current detecting status message.

        Parameters:
        - None

        Returns:
        - str: Detecting message.
        """
        return self.detect_msg

    @abstractmethod
    def refresh(self):
        """Refresh controller state and UI bindings."""

    @abstractmethod
    def is_com_ok(self):
        """Return whether the communication link is available.

        Returns:
        - bool: True if COM is OK; False otherwise.
        """

    @abstractmethod
    def get_device_formatted_name(self, device):
        """Return a user-friendly formatted device name.
        Parameters:
        - device : dict | object
            Device status dictionary for v2 or device object for v1/serial.

        Returns:
        - str: Formatted device name.
        """

    @abstractmethod
    def get_device_list(self):
        """Return the list of available devices.

        Returns:
        - list: Sequence of detected devices or descriptors.
        """


    @abstractmethod
    def get_device_presentation_string(self, d_id = 0):
        """Return a presentation string for the given device.

        Parameters:
        - d_id (int): Device index (default 0).

        Returns:
        - str: Presentation string.
        """

    @abstractmethod
    def get_device_info(self, d_id = 0):
        """Return a dictionary with device information.

        Parameters:
        - d_id (int): Device index (default 0).

        Returns:
        - dict: Device information.
        """

    @abstractmethod
    def is_sensor_enabled(self, comp_name, d_id = 0):
        """Return whether a sensor component is enabled.

        Parameters:
        - comp_name (str): Component name.
        - d_id (int): Device index (default 0).

        Returns:
        - bool: True if enabled; False otherwise.
        """

    @abstractmethod
    def fill_component_status(self, comp_name):
        """Populate internal status for the specified component.

        Parameters:
        - comp_name (str): Component name.

        Returns:
        - None
        """

    @abstractmethod
    def get_component_status(self, comp_name):
        """Return the current status dictionary for the specified component.

        Parameters:
        - comp_name (str): Component name.

        Returns:
        - dict: Component status.
        """

    @abstractmethod
    def update_component_status(self, comp_name, comp_type = "other"):
        """Update firmware-side status for a component and propagate to listeners.

        Parameters:
        - comp_name (str): Component name.
        - comp_type (str | ComponentType): Component type (default "other").

        Returns:
        - None
        """

    @abstractmethod
    def update_device_status(self):
        """Refresh and emit current device status."""

    @abstractmethod
    def connect_to(self, d_id, d_text = None, com_speed = None):
        """Establish a connection to the specified device.

        Parameters:
        - d_id (int): Device index to connect to.
        - d_text (str | None): Optional device descriptor.
        - com_speed (Any | None): Optional COM speed.

        Returns:
        - None
        """

    @abstractmethod
    def disconnect(self):
        """Disconnect from the current device and release resources."""

    @abstractmethod
    def send_command(self, json_command):
        """Send a JSON command to the device.

        Parameters:
        - json_command (str): JSON payload.

        Returns:
        - None
        """

    @abstractmethod
    def get_device_status(self):
        """Return the current device status dictionary.

        Returns:
        - dict: Device status.
        """

    @abstractmethod
    def save_config(self, on_pc, on_sd):
        """Persist configuration on PC and/or SD card.

        Parameters:
        - on_pc (bool): Save config on PC.
        - on_sd (bool): Save config on SD card.

        Returns:
        - None
        """

    @abstractmethod
    def is_hsd_link_serial(self):
        """Return whether HSD link type is serial.

        Returns:
        - bool: True if serial; False otherwise.
        """
