#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_MainWindow.py
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
"""
Main window for HSDatalog2 Motor Control (MC) GUI.

This module defines the `HSD_MC_MainWindow`, a specialization of the project's
`STDTDL_MainWindow` tailored for motor control use cases. It wires the MC controller,
installs the device configuration page, handles a connection check window, and forwards
key press/release events to the controller.
"""
from PySide6.QtCore import Slot

from stdatalog_gui.HSD_MC_GUI.HSD_MC_Controller import HSD_MC_Controller
from stdatalog_gui.HSD_MC_GUI.HSD_MC_DeviceConfigPage import HSD_MC_DeviceConfigPage
from stdatalog_gui.STDTDL_MainWindow import STDTDL_MainWindow
from stdatalog_gui.HSD_MC_GUI.Widgets.HSD_MC_CheckMCPConnectionWindow import (
    HSD_MC_CheckMCPConnectionWindow,
)
from stdatalog_gui.HSD_MC_GUI.Widgets.HSD_MC_ConnectionWidget import HSD_MC_ConnectionWidget

class HSD_MC_MainWindow(STDTDL_MainWindow):
    """Motor Control variant of the main window.

    Parameters
    ----------
    app : QApplication
        The Qt application instance used for processing events.
    parent : QWidget | None, optional
        Optional parent window.

    Responsibilities
    ----------------
    - Create the MC controller and device configuration page.
    - Connect controller signals for MCP connection checks.
    - Set the window title.
    """

    def __init__(self, app, parent=None):
        """
        Initialize the MC main window with controller and device config page.
        Parameters
        ----------
        app : QApplication
            The Qt application instance used for processing events.
        parent : QWidget | None, optional
            Optional parent window.
        """
        super().__init__(app, HSD_MC_Controller(parent), parent)

        # Remove the original connection widget and insert MC_ConnectionWidget at the same position
        if self.connection_widget is not None:
            layout = self.connection_page.layout()
            index = layout.indexOf(self.connection_widget)
            layout.removeWidget(self.connection_widget)
            self.connection_widget.deleteLater()
            self.connection_widget = HSD_MC_ConnectionWidget(self.controller, self)
            layout.insertWidget(index, self.connection_widget)
        # Connect the MCP connection check signal to its slot.
        self.controller.sig_mcp_check_connection.connect(self.s_check_mcp_connection)
        # Initialize and add the device configuration page.
        self.device_conf_page = HSD_MC_DeviceConfigPage(self.configuration_widget, self.controller)
        # Insert the device configuration page into the main window's configuration tab.
        self.setWindowTitle("HSDatalog2_MC")

    @Slot()
    def s_check_mcp_connection(self):
        """Open the MCP connection check window and process pending events."""
        self.check_connection_window = HSD_MC_CheckMCPConnectionWindow(self.page_manager)
        self.check_connection_window.show()
        self.app.processEvents()

    def keyPressEvent(self, event):
        """Forward key press events to the controller as key codes."""
        self.controller.sig_key_pressed.emit(event.key())

    def keyReleaseEvent(self, event):
        """Forward key release events to the controller as key codes."""
        self.controller.sig_key_released.emit(event.key())
