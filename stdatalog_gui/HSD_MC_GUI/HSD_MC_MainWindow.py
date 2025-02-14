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

class HSD_MC_MainWindow(STDTDL_MainWindow):
    
    def __init__(self, app, parent=None):
        super().__init__(app, HSD_MC_Controller(parent), parent)

        self.controller.sig_mcp_check_connection.connect(self.s_check_mcp_connection)

        self.device_conf_page = HSD_MC_DeviceConfigPage(self.configuration_widget, self.controller)
        
        self.setWindowTitle("HSDatalog2_MC")
    
    @Slot()
    def s_check_mcp_connection(self):
        self.check_connection_window = HSD_MC_CheckMCPConnectionWindow(self.page_manager)
        self.check_connection_window.show()
        self.app.processEvents()
    
    def keyPressEvent(self, event):
        self.controller.sig_key_pressed.emit(event.key())
 
    def keyReleaseEvent(self, event):
        self.controller.sig_key_released.emit(event.key())