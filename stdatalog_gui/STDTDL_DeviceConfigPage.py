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
"""Device Configuration Page controller for the ST DTDL GUI.

This module defines the controller class responsible for wiring the Device Configuration
page in the ST DTDL GUI. It connects controller signals to UI slots, creates per-component
configuration widgets, handles enable/disable toggles, and manages status messages for
logging and detecting.

Responsibilities:
- Build and manage the device configuration layout and header.
- React to discovery/removal of device components and render their configuration widgets.
- Provide bulk enable/disable controls via the "Select all" toggle.
- Show contextual status messages (logging/detecting) and error notifications.
- Maintain plot layout for sensors/algorithms/actuators.

Design Notes:
- Uses PySide6 widgets and signals; designed to be responsive and readable.
- Avoids behavioral changes; only documentation and line-wrapping for readability.
- Follows the project's 100-character line width where possible.
"""

from abc import abstractmethod
from PySide6.QtWidgets import (
    QFrame,
    QWidget,
    QLabel,
    QScrollArea,
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Slot, Qt
from stdatalog_gui.Utils.PlotParams import (
    ActuatorPlotParams,
    AlgorithmPlotParams,
    SensorPlotParams,
)
from stdatalog_gui.Widgets.ComponentWidget import ComponentWidget
from stdatalog_gui.Widgets.ToggleButton import ToggleButton
from stdatalog_gui.STDTDL_Controller import ComponentType

import stdatalog_gui.UI.images #NOTE don't delete this! it is used from resource_filename (@row 35)

from pkg_resources import resource_filename

import stdatalog_core.HSD_utils.logger as logger
from stdatalog_pnpl.PnPLCmd import PnPLCMDManager
log = logger.get_logger(__name__)

class STDTDL_DeviceConfigPage():
    """Controller for the Device Configuration page.

    This class orchestrates the device configuration UI: it creates and manages component
    widgets (sensors, algorithms, actuators), listens to controller signals for discovery,
    updates and removal, and exposes convenience methods to toggle configuration states and
    present status messages.

    Parameters:
    - page_widget (QWidget): Root widget containing the device configuration UI.
    - controller: Application controller exposing signals and device/component APIs.

    Attributes:
    - controller: Reference to the main application controller.
    - page_widget (QWidget): Root page widget for the device configuration UI.
    - main_layout (QFrame): Container frame housing the device configuration contents.
    - widget_header (QWidget): Header widget for title/controls.
    - log_control_widget: Optional widget to control logging (if present).
    - scrollArea_device_config (QScrollArea): Scroll area for component widgets.
    - widget_special_componenents (QWidget): Container for special components (if any).
    - device_config_widget (QWidget): Main container for component configuration.
    - select_all_button (ToggleButton): Global enable/disable toggle for all components.
    - select_all_frame (QFrame): Frame hosting the select-all toggle and label.
    - select_all_label (QFrame): Label reflecting the select-all state.
    - logging_message (QLabel): Status message for logging state.
    - error_message (QLabel): Error message shown for configuration issues.
    - plots_widget (QWidget): Container for plots; layout assigned to controller.
    - comp_id (int): Incremental component identifier used for widget indexing.
    - st_logo_img_path (str): Resource path to the ST logo image.
    - st_logo_image (QLabel): Label used to display the ST logo centered.
    """
    def __init__(self, page_widget, controller):
        """Initialize the device configuration page and wire signals.

        Parameters:
        - page_widget (QWidget): Root widget for the device configuration page.
        - controller: Application controller exposing device/component operations and signals.

        Returns:
        - None
        """
        self.controller = controller

        self.controller.sig_device_connected.connect(self.s_device_connected)
        self.controller.sig_component_config_widget_width_updated.connect(self.s_update_comp_config_width)

        self.controller.sig_component_found.connect(self.s_component_found)
        self.controller.sig_sensor_component_found.connect(self.s_sensor_component_found)
        self.controller.sig_algorithm_component_found.connect(self.s_algorithm_component_found)
        self.controller.sig_actuator_component_found.connect(self.s_actuator_component_found)
        self.controller.sig_dtm_loading_completed.connect(self.add_st_logo_to_device_config_widget_layout)

        self.controller.sig_sensor_component_updated.connect(self.s_sensor_component_updated)
        self.controller.sig_algorithm_component_updated.connect(self.s_algorithm_component_updated)
        self.controller.sig_actuator_component_updated.connect(self.s_actuator_component_updated)

        self.controller.sig_component_removed.connect(self.s_component_removed)

        self.controller.sig_logging.connect(self.s_is_logging)
        self.controller.sig_detecting.connect(self.s_is_detecting)

        self.page_widget = page_widget

        # layout_device_config
        self.main_layout = page_widget.findChild(QFrame, "frame_device_config")
        self.widget_header = self.main_layout.findChild(QWidget, "widget_header")
        self.log_control_widget = None

        self.scrollArea_device_config = self.main_layout.findChild(QScrollArea, "scrollArea_device_config")
        self.widget_special_componenents = self.main_layout.findChild(QWidget,"widget_special_components")
        self.device_config_widget = self.main_layout.findChild(QWidget,"widget_device_config")
        self.select_all_button = ToggleButton()
        self.select_all_button.toggle()
        self.select_all_frame = self.device_config_widget.findChild(QFrame,"select_all_frame")
        self.select_all_frame.layout().addWidget(self.select_all_button)
        self.select_all_button.toggled.connect(self.select_all_button_toggled)
        self.select_all_label = self.select_all_frame.findChild(QFrame,"select_all_label")
        self.select_all_label.setText("Unselect all")
        self.logging_message = QLabel(self.controller.get_log_msg())
        self.logging_message.setContentsMargins(12,6,12,6)
        self.logging_message.hide()
        self.device_config_widget.layout().addWidget(self.logging_message)
        self.error_message = QLabel("")
        self.error_message.setStyleSheet("color: #FF5050;")
        self.error_message.setContentsMargins(12,6,12,6)
        self.error_message.hide()
        self.device_config_widget.layout().addWidget(self.error_message)
        self.plots_widget = self.main_layout.findChild(QWidget,"widget_plots")
        self.controller.set_plots_layout(self.plots_widget.layout())

        self.comp_id = 0

        self.st_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'st_logo.png')
        self.st_logo_image = QLabel()

    def remove_comp_widget(self, name):
        """Remove a component configuration widget by name.

        Parameters:
        - name (str): Component name whose configuration widget should be removed.

        Returns:
        - None
        """
        self.controller.remove_component_config_widget(name)

    def get_nof_components(self):
        """Return the number of components reported by the controller.

        Parameters:
        - None

        Returns:
        - int: Count of components in the connected device, or 0 if COM is not OK.
        """
        if self.controller.is_com_ok():
            return len(
                self.controller.get_device_status()["devices"][
                    self.controller.device_id
                ]["components"]
            )
        return 0

    @Slot()
    def select_all_button_toggled(self, status):
        """Toggle enable state for all components via select-all control.

        Parameters:
        - status (bool): Desired enable state; True enables, False disables.

        Returns:
        - None
        """
        if status:
            self.select_all_label.setText("Unselect all")
        else:
            self.select_all_label.setText("Select all")
        cstatus_dict = self.controller.components_status
        for c in cstatus_dict:
            c_type = cstatus_dict[c].get("c_type")
            if (
                c_type == ComponentType.SENSOR.value
                or c_type == ComponentType.ALGORITHM.value
                or c_type == ComponentType.ACTUATOR.value
            ):
                json_string = PnPLCMDManager.create_set_property_cmd(c, "enable", status)
                self.controller.send_command(json_string)
                self.controller.update_component_status(c, ComponentType(c_type))

    @Slot(bool)
    def s_device_connected(self, status):
        """Handle device connection changes.

        Parameters:
        - status (bool): True if device connected, False otherwise.

        Returns:
        - None
        """
        if not status:
            self.st_logo_image.clear()

    @Slot(int)
    def s_update_comp_config_width(self, width):
        """Update the width of the component configuration area.

        Parameters:
        - width (int): Base width to apply to the scroll area and inner widget.

        Returns:
        - None
        """
        self.scrollArea_device_config.setMinimumWidth(width+6)
        self.scrollArea_device_config.setMaximumWidth(width+6)
        self.scrollArea_device_config.widget().setFixedWidth(width)

    def add_st_logo_to_device_config_widget_layout(self):
        """Add the ST logo to the device configuration layout.

        Parameters:
        - None

        Returns:
        - None
        """
        st_logo_pixmap = QPixmap(self.st_logo_img_path)
        self.st_logo_image.setPixmap(st_logo_pixmap)
        self.st_logo_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.st_logo_image.setContentsMargins(0,12,0,0)
        self.device_config_widget.layout().addWidget(self.st_logo_image)

    @Slot(str, dict)
    def s_component_found(self, comp_name, comp_interface):
        """Create and register a configuration widget for a discovered component.

        Parameters:
        - comp_name (str): Component name as reported by the controller.
        - comp_interface (dict | object): Interface/DTDL info for the component.

        Returns:
        - None
        """
        comp_id = list(self.controller.components_dtdl.keys()).index(comp_name)
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        # if comp_name == "applications_stblesensor":
        #     pass
        # else:
        comp_config_widget = ComponentWidget(
            self.controller,
            comp_name,
            comp_display_name,
            "",
            comp_interface.contents,
            comp_id,
            self.device_config_widget,
        )
        self.controller.add_component_config_widget(comp_config_widget)
        self.device_config_widget.layout().addWidget(comp_config_widget)
        self.controller.fill_component_status(comp_name)

    @Slot(str, dict)
    def s_sensor_component_found(self, comp_name, comp_interface):
        """Create and register a sensor component configuration widget.

        Parameters:
        - comp_name (str): Sensor component name.
        - comp_interface (dict | object): Sensor interface/DTDL info.

        Returns:
        - None
        """
        #create a ComponentWidget
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        sensor_config_widget = ComponentWidget(
            self.controller,
            comp_name,
            comp_display_name,
            ComponentType.SENSOR,
            comp_interface.contents,
            self.comp_id,
            self.device_config_widget,
        )
        self.comp_id += 1
        self.controller.add_component_config_widget(sensor_config_widget)
        self.device_config_widget.layout().addWidget(sensor_config_widget)

        self.controller.fill_component_status(comp_name)

    @Slot(str, dict)
    def s_algorithm_component_found(self, comp_name, comp_interface):
        """Create and register an algorithm component configuration widget.

        Parameters:
        - comp_name (str): Algorithm component name.
        - comp_interface (dict | object): Algorithm interface/DTDL info.

        Returns:
        - None
        """
        #create a ComponentWidget
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        alg_config_widget = ComponentWidget(
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

        self.controller.fill_component_status(comp_name)

    @Slot(str, dict)
    def s_actuator_component_found(self, comp_name, comp_interface):
        """Create and register an actuator component configuration widget.

        Parameters:
        - comp_name (str): Actuator component name.
        - comp_interface (dict | object): Actuator interface/DTDL info.

        Returns:
        - None
        """
        #create a ComponentWidget
        comp_display_name = (
            comp_interface.display_name
            if isinstance(comp_interface.display_name, str)
            else comp_interface.display_name.en
        )
        act_config_widget = ComponentWidget(
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

    @Slot(str)
    def s_component_removed(self, comp_name):
        """Handle component removal by removing its configuration widget.

        Parameters:
        - comp_name (str): Name of the component being removed.

        Returns:
        - None
        """
        self.remove_comp_widget(comp_name)

    @Slot(str, SensorPlotParams)
    @abstractmethod
    def s_sensor_component_updated(self, comp_name, plot_params:SensorPlotParams):
        """Update UI based on sensor plotting parameters.

        Parameters:
        - comp_name (str): Sensor component name.
        - plot_params (SensorPlotParams): Plot configuration for the sensor.

        Returns:
        - None
        """

    @Slot(str, AlgorithmPlotParams)
    @abstractmethod
    def s_algorithm_component_updated(self, comp_name, plot_params:AlgorithmPlotParams):
        """Update UI based on algorithm plotting parameters.

        Parameters:
        - comp_name (str): Algorithm component name.
        - plot_params (AlgorithmPlotParams): Plot configuration for the algorithm.

        Returns:
        - None
        """

    @Slot(str, ActuatorPlotParams)
    @abstractmethod
    def s_actuator_component_updated(self, comp_name, plot_params:ActuatorPlotParams):
        """Update UI based on actuator plotting parameters.

        Parameters:
        - comp_name (str): Actuator component name.
        - plot_params (ActuatorPlotParams): Plot configuration for the actuator.

        Returns:
        - None
        """
        pass

    def set_error_message(self, status, message):
        """Show or hide an error message in the configuration area.

        Parameters:
        - status (bool): True to show error, False to hide.
        - message (str): Error text to display when status is True.

        Returns:
        - None
        """
        if status:
            self.error_message.setText(message)
            self.error_message.show()
        else:
            self.error_message.hide()

    def endisable_logging_message(self, status):
        """Enable or disable the logging status message.

        Parameters:
        - status (bool): True to show logging message, False to hide.

        Returns:
        - None
        """
        if self.controller.get_log_msg() != "":
            self.logging_message.setText(self.controller.get_log_msg())
            self.logging_message.show() if status else self.logging_message.hide()

    def endisable_detecting_message(self, status):
        """Enable or disable the detecting status message.

        Parameters:
        - status (bool): True to show detecting message, False to hide.

        Returns:
        - None
        """
        if self.controller.get_detect_msg() != "":
            self.detect_message.setText(self.controller.get_detect_msg())
            self.detect_message.show() if status else self.detect_message.hide()

    def endisable_component_config(self, status, c_to_avoid):
        """Enable/disable configuration for all components except those to avoid.

        Parameters:
        - status (bool): True to disable, False to enable contents.
        - c_to_avoid (list[str]): Component names to exclude from changes.

        Returns:
        - None
        """
        for w in self.device_config_widget.findChildren(ComponentWidget):
            if w.comp_name not in c_to_avoid:
                self.endisable_component(status, w.comp_name)

    def endisable_component(self, status, c_name):
        """Enable/disable a single component's configuration area and adjust style.

        Parameters:
        - status (bool): True to disable and dim style; False to enable and brighten.
        - c_name (str): Component name whose configuration is updated.

        Returns:
        - None
        """
        w = self.controller.cconfig_widgets[c_name]
        w.contents_widget.setEnabled(not status)
        if status:
            style_split = w.frame_component_config.styleSheet().split(';')
            style_split[-1] = "\ncolor: rgb(100, 100, 100)"
            w.frame_component_config.setStyleSheet(';'.join(style_split))
        else:
            style_split = w.frame_component_config.styleSheet().split(';')
            style_split[-1] = "\ncolor: rgb(210, 210, 210)"
            w.frame_component_config.setStyleSheet(';'.join(style_split))

    @abstractmethod
    def add_header_widget(self, widget):
        """Add a custom header widget to the device configuration page.

        Parameters:
        - widget (QWidget): Widget instance to add to the header area.

        Returns:
        - None
        """
        pass

    @Slot(bool)
    def s_is_logging(self, status:bool, interface:int):
        """Handle logging state changes and adjust UI interactivity.

        Parameters:
        - status (bool): True if logging is active; False otherwise.
        - interface (int): Optional interface index (unused).

        Returns:
        - None
        """
        self.endisable_logging_message(status)
        self.select_all_button.setEnabled(not status)

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        """Handle detecting state changes and adjust UI interactivity.

        Parameters:
        - status (bool): True if detecting is active; False otherwise.

        Returns:
        - None
        """
        self.endisable_detecting_message(status)
        self.select_all_button.setEnabled(not status)
