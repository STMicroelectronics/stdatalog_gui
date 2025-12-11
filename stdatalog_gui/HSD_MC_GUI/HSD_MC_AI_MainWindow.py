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

from stdatalog_gui.HSD_MC_GUI.HSD_MC_Controller import HSD_MC_Controller
from stdatalog_gui.HSD_MC_GUI.HSD_MC_DeviceConfigPage import HSD_MC_DeviceConfigPage
from stdatalog_gui.STDTDL_MainWindow import STDTDL_MainWindow
from stdatalog_gui.HSD_MC_GUI.Widgets.HSD_MC_CheckMCPConnectionWindow import HSD_MC_CheckMCPConnectionWindow
from PySide6.QtCore import Slot
from stdatalog_gui.HSD_MC_GUI.Widgets.HSD_MC_ConnectionWidget import HSD_MC_ConnectionWidget
import stdatalog_gui.UI.images
import stdatalog_gui.HSD_MC_GUI.UI.images

from pkg_resources import resource_filename

motor_recovery_img_path = resource_filename('stdatalog_gui.HSD_MC_GUI.UI.images', 'Recovery_Status.png')
motor_normal_img_path = resource_filename('stdatalog_gui.HSD_MC_GUI.UI.images', 'Motor_Normal_Class.png')
motor_anomaly_img_path = resource_filename('stdatalog_gui.HSD_MC_GUI.UI.images', 'Motor_Anomaly_Class.png')
motor_vibration_img_path = resource_filename('stdatalog_gui.HSD_MC_GUI.UI.images', 'Motor_Vibration_Class.png')
motor_magnet_img_path = resource_filename('stdatalog_gui.HSD_MC_GUI.UI.images', 'Motor_Magnet_Class.png')
motor_belt_img_path = resource_filename('stdatalog_gui.HSD_MC_GUI.UI.images', 'Motor_Belt_Class.png')
ispu_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'ISPU.png')
nanoedge_ispu_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'Nanoedge_ISPU.png')
nanoedge_stm32_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'Nanoedge_STM32.png')
cubeai_stm32_logo_img_path = resource_filename('stdatalog_gui.UI.images', 'CubeAI_STM32.png')
ai_output_img_path = resource_filename('stdatalog_gui.UI.images', 'AI_Output.png')

motor_bearing_img_path = resource_filename('stdatalog_gui.HSD_MC_GUI.UI.images', 'Motor_Bearing_Class.png')


class HSD_MC_AI_MainWindow(STDTDL_MainWindow):
    
    def __init__(self, app, controller=HSD_MC_Controller(None), parent=None):
        super().__init__(app, controller, parent)

        # Remove the original connection widget and insert MC_ConnectionWidget at the same position
        if self.connection_widget is not None:
            layout = self.connection_page.layout()
            index = layout.indexOf(self.connection_widget)
            layout.removeWidget(self.connection_widget)
            self.connection_widget.deleteLater()
            self.connection_widget = HSD_MC_ConnectionWidget(self.controller, self)
            layout.insertWidget(index, self.connection_widget)

        self.controller.sig_mcp_check_connection.connect(self.s_check_mcp_connection)

        self.device_conf_page = HSD_MC_DeviceConfigPage(self.configuration_widget, self.controller)
        self.setWindowTitle("HSDatalog2_MC_AI")
        self.motor_demo_states = {}

        self.supported_out_class_dict = {
            "Motor_Normal_class" : ("Normal" , motor_normal_img_path),
            "Motor_Fault_class" : ("Fault" , motor_anomaly_img_path),
            "Motor_Vibration_class" : ("Vibration" , motor_vibration_img_path),
            "Motor_Magnet_class" : ("Magnet" , motor_magnet_img_path),
            "Motor_Bearing_class" : ("Bearing" , motor_bearing_img_path),
            "Motor_Belt_class": ("Belt", motor_belt_img_path),
            "ISPU" : ("ISPU", ispu_logo_img_path) #NOTE inserted here for ISPU CES 2023 demo purposes
        }
        self.anomaly_classes = {}
        self.out_classes = {}

        self.supported_ai_tools_dict = {
            "ISPU" : ("ISPU", ispu_logo_img_path),
            "Nanoedge_ISPU" : ("Nanoedge on ISPU", nanoedge_ispu_logo_img_path),
            "Nanoedge_STM32" : ("Nanoedge on STM32", nanoedge_stm32_logo_img_path),
            "CubeAI_STM32" : ("CubeAI on STM32", cubeai_stm32_logo_img_path)
        }
        self.ai_anomaly_tool = {}
        self.ai_classifier_tool = {}
        
        self.setWindowTitle("HSDatalog2")

    def setAIAnomalyImages(self, anomaly_images:list):
        for n in anomaly_images:
            if n in self.supported_out_class_dict:
                out_c_name = self.supported_out_class_dict[n][0]
                out_c_img = self.supported_out_class_dict[n][1]
                self.anomaly_classes[out_c_name] = out_c_img 
            else:
                self.anomaly_classes[n] = ai_output_img_path
        self.controller.set_anomaly_classes(self.anomaly_classes)
        
    def setAIClassifierImages(self, class_names:list):
        for n in class_names:
            if n in self.supported_out_class_dict:
                out_c_name = self.supported_out_class_dict[n][0]
                out_c_img = self.supported_out_class_dict[n][1]
                self.out_classes[out_c_name] = out_c_img 
            else:
                self.out_classes[n] = ai_output_img_path
        self.controller.set_output_classes(self.out_classes)
    
    def setAIAnomalyTool(self, tool_name:str):
        if tool_name in self.supported_ai_tools_dict:
            ai_anomaly_tool_name = self.supported_ai_tools_dict[tool_name][0]
            ai_anomaly_tool_img = self.supported_ai_tools_dict[tool_name][1]
            self.ai_anomaly_tool[ai_anomaly_tool_name] = ai_anomaly_tool_img
            self.controller.set_ai_anomaly_tool(self.ai_anomaly_tool)

    def setAIClassifierTool(self, tool_name:str):
        if tool_name in self.supported_ai_tools_dict:
            ai_classifier_tool_name = self.supported_ai_tools_dict[tool_name][0]
            ai_classifier_tool_img = self.supported_ai_tools_dict[tool_name][1]
            self.ai_classifier_tool[ai_classifier_tool_name] = ai_classifier_tool_img
            self.controller.set_ai_classifier_tool(self.ai_classifier_tool)

    def getOutputClassDict(self):
        return self.out_classes

    def closeEvent(self, event):
        self.controller.stop_log()
        event.accept()

    # TODO: Next version --> Hotplug events notification support
    # @Slot(bool)
    # def s_usb_hotplug_event(self, status):
    #     print("HSDv2 USB Device Plugged") if status else print("HSDv2 USB Device Unplugged")
    #     # if status == False:
    #     #     self.page_manager.setCurrentWidget(self.connection_page)
    #     #     self.menu_btn_device_conf.setVisible(False)
    # TODO: Next version --> Hotplug events notification support
    
    def setMotorDemoImages(self, class_names:list):
        for n in class_names:
            self.motor_demo_states[n] = motor_recovery_img_path
        self.controller.set_motor_demo_states(self.motor_demo_states)

    @Slot()
    def s_check_mcp_connection(self):
        self.check_connection_window = HSD_MC_CheckMCPConnectionWindow(self.page_manager)
        self.check_connection_window.show()
        self.app.processEvents()
    
    def keyPressEvent(self, event):
        self.controller.sig_key_pressed.emit(event.key())
 
    def keyReleaseEvent(self, event):
        self.controller.sig_key_released.emit(event.key())