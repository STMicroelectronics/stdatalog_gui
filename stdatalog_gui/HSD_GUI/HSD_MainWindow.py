# *****************************************************************************
#  * @file    MainWindow.py
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
Main window for HSDatalog2 that wires controller, configuration page, and AI imagery.

This module defines the ``HSD_MainWindow`` class, a concrete specialization of
``STDTDL_MainWindow`` that sets up the device configuration page, binds a controller, and
manages images/icons for AI anomaly detection and classification outputs. It also
forwards key events to the controller and ensures a clean shutdown of logging, plot
threads, and serial links on close.

Highlights
----------
- Configures the ``HSD_DeviceConfigPage`` for device-specific settings.
- Maintains mappings from output class names to representative images.
- Exposes helpers to set AI tool badges (ISPU, Nanoedge variants).
- Forwards key press/release events to the controller via signals.
- Gracefully closes threads and links when the window is closed.
"""

import stdatalog_gui.UI.images #NOTE don't delete this! it is used from resource_filename
from stdatalog_gui.STDTDL_MainWindow import STDTDL_MainWindow

from stdatalog_gui.HSD_GUI.HSD_DeviceConfigPage import HSD_DeviceConfigPage
from stdatalog_gui.HSD_GUI.HSD_Controller import HSD_Controller

from pkg_resources import resource_filename
motor_normal_img_path = resource_filename('stdatalog_gui.UI.images', 'Motor_Normal_Class.png')
motor_anomaly_img_path = resource_filename('stdatalog_gui.UI.images', 'Motor_Anomaly_Class.png')
motor_vibration_img_path = resource_filename('stdatalog_gui.UI.images', 'Motor_Vibration_Class.png')
motor_magnet_img_path = resource_filename('stdatalog_gui.UI.images', 'Motor_Magnet_Class.png')
motor_belt_img_path = resource_filename('stdatalog_gui.UI.images', 'Motor_Belt_Class.png')
ispu_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'ISPU.png')
nanoedge_ispu_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'Nanoedge_ISPU.png')
nanoedge_stm32_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'Nanoedge_STM32.png')
ai_output_img_path = resource_filename('stdatalog_gui.UI.images', 'AI_Output.png')

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class HSD_MainWindow(STDTDL_MainWindow):
    """Main window that integrates HSD controller and AI image mappings.

    Parameters
    ----------
    app : QApplication
        The Qt application instance, forwarded to ``STDTDL_MainWindow``.
    controller : HSD_Controller, optional
        The device controller. Defaults to ``HSD_Controller(None)``.
    parent : QWidget | None, optional
        Parent widget. Default is ``None``.

    Attributes
    ----------
    device_conf_page : HSD_DeviceConfigPage
        Configuration page embedded in the main window.
    supported_out_class_dict : dict[str, tuple[str, str]]
        Mapping from raw class identifiers to a pair of display name and image path.
    anomaly_classes : dict[str, str]
        Mapping from anomaly class display names to image paths.
    out_classes : dict[str, str]
        Mapping from classifier output display names to image paths.
    supported_ai_tools_dict : dict[str, tuple[str, str]]
        Mapping from AI tool identifiers to display name and image path.
    ai_anomaly_tool : dict[str, str]
        Mapping from selected anomaly tool display name to image path.
    ai_classifier_tool : dict[str, str]
        Mapping from selected classifier tool display name to image path.
    """

    def __init__(self, app, controller = HSD_Controller(None), parent=None):
        super().__init__(app, controller, parent)

        self.device_conf_page = HSD_DeviceConfigPage(
            self.configuration_widget, self.controller
        )

        self.supported_out_class_dict = {
            "Motor_Normal_class": ("Normal", motor_normal_img_path),
            "Motor_Anomaly_class": ("Anomaly", motor_anomaly_img_path),
            "Motor_Vibration_class": ("Vibration", motor_vibration_img_path),
            "Motor_Magnet_class": ("Magnet", motor_magnet_img_path),
            "Motor_Belt_class": ("Belt", motor_belt_img_path),
            # NOTE inserted here for ISPU CES 2023 demo purposes
            "ISPU": ("ISPU", ispu_logo_img_path),
        }
        self.anomaly_classes = {}
        self.out_classes = {}

        self.supported_ai_tools_dict = {
            "ISPU": ("ISPU", ispu_logo_img_path),
            "Nanoedge_ISPU": ("Nanoedge on ISPU", nanoedge_ispu_logo_img_path),
            "Nanoedge_STM32": ("Nanoedge on STM32", nanoedge_stm32_logo_img_path),
        }
        self.ai_anomaly_tool = {}
        self.ai_classifier_tool = {}

        self.setWindowTitle("HSDatalog2")

    def setAIAnomalyImages(self, anomaly_images:list):
        """Register images for anomaly output classes.

        Parameters
        ----------
        anomaly_images : list[str]
            Collection of raw class identifiers. Each identifier is mapped to a display
            name and image path using ``supported_out_class_dict``. Unknown identifiers
            fall back to a generic AI output image.

        Returns
        -------
        None
        """
        for n in anomaly_images:
            if n in self.supported_out_class_dict:
                out_c_name = self.supported_out_class_dict[n][0]
                out_c_img = self.supported_out_class_dict[n][1]
                self.anomaly_classes[out_c_name] = out_c_img
            else:
                self.anomaly_classes[n] = ai_output_img_path
        self.controller.set_anomaly_classes(self.anomaly_classes)

    def setAIClassifierImages(self, class_names:list):
        """Register images for classifier output classes.

        Parameters
        ----------
        class_names : list[str]
            Collection of raw class identifiers. Each is mapped via
            ``supported_out_class_dict`` to a display name and image path; unknown names
            use the generic AI output image.

        Returns
        -------
        None
        """
        for n in class_names:
            if n in self.supported_out_class_dict:
                out_c_name = self.supported_out_class_dict[n][0]
                out_c_img = self.supported_out_class_dict[n][1]
                self.out_classes[out_c_name] = out_c_img
            else:
                self.out_classes[n] = ai_output_img_path
        self.controller.set_output_classes(self.out_classes)

    def setAIAnomalyTool(self, tool_name:str):
        """Set the active anomaly detection tool and its image.

        Parameters
        ----------
        tool_name : str
            Tool identifier, e.g., ``"ISPU"`` or ``"Nanoedge_ISPU"``. When present in
            ``supported_ai_tools_dict``, its display name and image are persisted and
            forwarded to the controller.

        Returns
        -------
        None
        """
        if tool_name in self.supported_ai_tools_dict:
            ai_anomaly_tool_name = self.supported_ai_tools_dict[tool_name][0]
            ai_anomaly_tool_img = self.supported_ai_tools_dict[tool_name][1]
            self.ai_anomaly_tool[ai_anomaly_tool_name] = ai_anomaly_tool_img
            self.controller.set_ai_anomaly_tool(self.ai_anomaly_tool)

    def setAIClassifierTool(self, tool_name:str):
        """Set the active classification tool and its image.

        Parameters
        ----------
        tool_name : str
            Tool identifier, e.g., ``"Nanoedge_STM32"``. When present in
            ``supported_ai_tools_dict``, its display name and image are persisted and
            forwarded to the controller.

        Returns
        -------
        None
        """
        if tool_name in self.supported_ai_tools_dict:
            ai_classifier_tool_name = self.supported_ai_tools_dict[tool_name][0]
            ai_classifier_tool_img = self.supported_ai_tools_dict[tool_name][1]
            self.ai_classifier_tool[ai_classifier_tool_name] = ai_classifier_tool_img
            self.controller.set_ai_classifier_tool(self.ai_classifier_tool)

    def getOutputClassDict(self):
        """Return the mapping of classifier output display names to images.

        Returns
        -------
        dict[str, str]
            Dictionary where keys are display names and values are image paths.
        """
        return self.out_classes

    def closeEvent(self, event):
        """Shutdown logging, plot threads, and links before closing.

        This handler stops the controller logging, closes plot threads if the HSD
        instance exists, and safely shuts down the serial link when used. Finally, it
        accepts the close event.

        Parameters
        ----------
        event : QCloseEvent
            The close event dispatched by Qt.

        Returns
        -------
        None
        """
        self.controller.stop_log()
        if self.controller.hsd is not None:
            self.controller.hsd.close_plot_threads()
        if self.controller.is_hsd_link_serial():
            self.controller.stop_serial_reader_thread()
            if self.controller.hsd_link is not None:
                self.controller.hsd_link.close()
        event.accept()

    def keyPressEvent(self, event):
        """Forward key press events to the controller.

        Parameters
        ----------
        event : QKeyEvent
            The key press event from Qt.

        Returns
        -------
        None
        """
        self.controller.sig_key_pressed.emit(event.key())

    def keyReleaseEvent(self, event):
        """Forward key release events to the controller.

        Parameters
        ----------
        event : QKeyEvent
            The key release event from Qt.

        Returns
        -------
        None
        """
        self.controller.sig_key_released.emit(event.key())
