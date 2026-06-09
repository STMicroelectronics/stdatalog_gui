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
"""
Main application window for the ST DTDL GUI.

Manages page navigation (connection, configuration, experimental features, log viewer), wires
controller signals to UI slots, and coordinates loading dialogs and header/plot content areas.
This module serves as the central hub for user interaction within the GUI.

Responsibilities:
- Initialize and configure the main window and its widgets.
- Handle navigation between different application pages.
- Respond to controller signals for device connection and DTM loading.
- Manage application logging and display log files within the GUI.

Classes:
- `STDTDL_MainWindow`: The main window class orchestrating the GUI.

Usage Example:
    from PySide6.QtWidgets import QApplication
    from stdatalog_gui.STDTDL_MainWindow import STDTDL_MainWindow
    from stdatalog_gui.STDTDL_Controller import STDTDL_Controller
    app = QApplication([])
    controller = STDTDL_Controller()
    main_window = STDTDL_MainWindow(app, controller)
    main_window.show()
    app.exec()
"""

import sys
import os
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QTextEdit,
    QLabel,
    QPushButton,
    QWidget,
    QFrame,
)
from PySide6.QtCore import Slot

from stdatalog_gui.STDTDL_ExperimentalFeaturesPage import STDTDL_ExperimentalFeaturesPage
from stdatalog_gui.UI.styles import STDTDL_MenuButton
from stdatalog_gui.UI.Ui_MainWindow import Ui_MainWindow
from stdatalog_gui.Widgets.DeviceTemplateLoadingWidget import DeviceTemplateLoadingWidget
from stdatalog_gui.Widgets.LoadingWindow import LoadingWindow
from stdatalog_gui.Widgets.ConnectionWidget import ConnectionWidget
from stdatalog_gui.Widgets.AboutDialog import AboutDialog
from stdatalog_gui.Widgets.ToggleButton import ToggleButton

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class STDTDL_MainWindow(QMainWindow):
    """
    Top-level window orchestrating all GUI pages and widgets.
    This class can be extended to create customized main windows for specific applications,
    leveraging the existing structure for page management and controller integration.
    It handles navigation between connection, configuration, experimental features,
    and log viewer pages, wiring controller signals to appropriate slots for UI updates.
    
    Responsibilities:
    - Initialize and configure the main window and its widgets.
    - Handle navigation between different application pages.
    - Respond to controller signals for device connection and DTM loading.
    - Manage application logging and display log files within the GUI.
    - Set application title, credits, and version labels.
    - Forward log messages to the controller for display.

    Note: This class assumes the existence of a controller that provides
    necessary signals and configuration APIs. The controller should be an instance
    of `STDTDL_Controller` or a compatible subclass.

    Parameters:
    - app: QApplication instance used to process events for long operations.
    - controller: The ST DTDL controller providing signals and configuration APIs.
    - parent (QWidget | None): Optional parent widget.

    Returns:
    - None
    """

    def __init__(self, app, controller, parent=None):
        super(STDTDL_MainWindow, self).__init__(parent)

        self.app = app

        self.controller = controller
        self.controller.sig_device_connected.connect(self.s_device_connected)
        self.controller.sig_dtm_loading_started.connect(self.s_dtm_loading_started)
        self.controller.sig_dtm_loading_completed.connect(self.s_dtm_loaded)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.app_title = "ST DTDL GUI"
        self.app_credit = "created by ST"
        self.app_version = ""
        self.ui.label_app_title.setText(self.app_title)
        self.ui.label_credits.setText(self.app_credit)
        self.ui.label_version.setText(self.app_version)

        self.plugin_folder = ""
        self.loading_window = None

        self.setWindowTitle(self.app_title)

        # Find the widgets in the xml file
        # Main stacked widget (Application page manager)
        self.page_manager = self.findChild(QStackedWidget, "stacked_widget")

        # Connection page
        self.connection_page = self.findChild(QWidget, "page_connection")
        frame_log_file_options = self.findChild(QFrame, "frame_log_file_options")
        frame_dt_settings = self.findChild(QFrame, "frame_dt_settings")

        app_log_file_label = QLabel("Enable application log file")
        app_log_file_label.setStyleSheet("font: 700 10pt \"Segoe UI\";")
        frame_log_file_options.layout().addWidget(app_log_file_label)
        app_log_file_toggle_button = ToggleButton()
        frame_log_file_options.layout().addWidget(app_log_file_toggle_button)
        app_log_file_toggle_button.toggled.connect(self.app_log_file_button_toggled)

        adv_settings_label = QLabel("Advanced Settings")
        adv_settings_label.setStyleSheet("font: 700 10pt \"Segoe UI\";")
        frame_dt_settings.layout().addWidget(adv_settings_label)
        adv_settings_toggle_button = ToggleButton()
        frame_dt_settings.layout().addWidget(adv_settings_toggle_button)
        adv_settings_toggle_button.toggled.connect(self.adv_settings_button_toggled)

        self.connection_widget = ConnectionWidget(self.controller, self)
        self.device_model_loading_widget = DeviceTemplateLoadingWidget(self.controller, self)
        self.device_model_loading_widget.setVisible(False)

        self.connection_page.layout().addWidget(self.connection_widget)
        self.connection_page.layout().addWidget(self.device_model_loading_widget)

        self.connection_page.layout().addStretch()

        # Device Components Configuration page
        self.configuration_widget = self.findChild(QWidget, "page_device_config")
        # for plots processEvent
        self.controller.set_Qt_app(self.app)
        self.device_conf_page = None

        self.widget_device_config = self.findChild(QFrame, "widget_device_config")
        self.widget_plots = self.findChild(QWidget, "widget_plots")
        self.widget_header = self.findChild(QWidget, "widget_header")

        #Acquisitions upload page
        self.page_experimental_features = self.findChild(QWidget, "page_experimental_features")
        self.page_experimental_features = STDTDL_ExperimentalFeaturesPage(
            self.page_experimental_features,
            self.controller,
        )

        # Application Log file display page
        self.show_log_file_page = self.findChild(QWidget, "page_app_log_file")
        self.log_file_text_edit: QTextEdit = self.show_log_file_page.findChild(
            QTextEdit,
            "log_file_textEdit",
        )
        self.log_file_text_title: QLabel = self.show_log_file_page.findChild(
            QLabel,
            "log_file_title",
        )

        # self.show_log_file_page.layout().addStretch()

        # Set the first displayed [Connection] Page
        self.page_manager.setCurrentWidget(self.connection_page)

        # Left Menu Items (page navigation menu)
        self.menu_btn_connection = self.findChild(QPushButton, "menu_btn_connection")
        self.menu_btn_connection.clicked.connect(self.clicked_menu_connection)
        self.menu_btn_device_conf = self.findChild(QPushButton, "menu_btn_device_conf")
        self.menu_btn_device_conf.clicked.connect(self.clicked_menu_device_conf)
        self.menu_btn_experimental_features = self.findChild(
            QPushButton,
            "menu_btn_experimental_features"
        )
        self.menu_btn_experimental_features.clicked.connect(self.clicked_menu_experimental_features)
        self.menu_btn_about = self.findChild(QPushButton, "menu_btn_about")
        self.menu_btn_about.clicked.connect(self.clicked_menu_about)
        self.menu_btn_show_log_file = self.findChild(QPushButton, "menu_btn_show_log_file")
        self.menu_btn_show_log_file.clicked.connect(self.clicked_menu_btn_show_log_file)

        # Hide Configuration menu button (it will be unhided when a device will be connected)
        self.menu_btn_device_conf.setVisible(False)
        # Hide Application file viewer menu button
        # (it will be unhided if The user wants to save the application log file)
        self.menu_btn_show_log_file.setVisible(False)

    def quit(self):
        """Terminate the application process.

        Parameters:
        - None

        Returns:
        - None
        """
        sys.exit(0)

    def clicked_menu_connection(self):
        """Switch to the connection page and update menu styles.

        Parameters:
        - None

        Returns:
        - None
        """
        self.page_manager.setCurrentWidget(self.connection_page)
        self.menu_btn_device_conf.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_DEVICE_CONFIG,
                False,
            )
        )
        self.menu_btn_show_log_file.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_LOG_INFO,
                False,
            )
        )
        self.menu_btn_experimental_features.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_EXPERIMENTAL_FEATURES,
                False,
            )
        )

    def clicked_menu_device_conf(self):
        """Switch to the device configuration page and update menu styles.

        Parameters:
        - None

        Returns:
        - None
        """
        self.page_manager.setCurrentWidget(self.device_conf_page.page_widget)
        self.menu_btn_device_conf.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_DEVICE_CONFIG,
                True,
            )
        )
        self.menu_btn_show_log_file.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_LOG_INFO,
                False,
            )
        )
        self.menu_btn_experimental_features.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_EXPERIMENTAL_FEATURES,
                False,
            )
        )
        if self.loading_window is not None:
            self.loading_window.loadingDone()

    def clicked_menu_experimental_features(self):
        """Switch to the experimental features page and update menu styles.

        Parameters:
        - None

        Returns:
        - None
        """
        self.page_manager.setCurrentWidget(self.page_experimental_features.page_widget)
        self.menu_btn_device_conf.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_DEVICE_CONFIG,
                False,
            )
        )
        self.menu_btn_experimental_features.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_EXPERIMENTAL_FEATURES,
                True,
            )
        )
        self.menu_btn_show_log_file.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_LOG_INFO,
                False,
            )
        )

    def clicked_menu_about(self):
        """Show the About dialog.

        Parameters:
        - None

        Returns:
        - None
        """
        print("WARNING - About screen will be available soon.")
        dlg = AboutDialog(self, self.app_title, self.app_credit, self.app_version)
        dlg.exec_()

    def clicked_menu_btn_show_log_file(self):
        """Switch to the application log viewer page and update menu styles.

        Parameters:
        - None

        Returns:
        - None
        """
        self.page_manager.setCurrentWidget(self.show_log_file_page)
        self.menu_btn_device_conf.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_DEVICE_CONFIG,
                False,
            )
        )
        self.menu_btn_show_log_file.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_LOG_INFO,
                True,
            )
        )
        self.menu_btn_experimental_features.setStyleSheet(
            STDTDL_MenuButton.get_stylesheet(
                STDTDL_MenuButton.STDTDL_Page.PAGE_EXPERIMENTAL_FEATURES,
                False,
            )
        )
        for handler in log.parent.handlers:
            if hasattr(handler, "baseFilename"):
                log_file_name = getattr(handler, "baseFilename")
                self.log_file_text_title.setText(
                    f"Log File: {os.path.basename(log_file_name)}"
                )
                # print(f"writing log to {log_file_name}")
                log_text = open(log_file_name, encoding="utf-8").read()
                self.log_file_text_edit.setText(log_text)

    def closeEvent(self, event):
        """Accept the close event and allow the window to close.

        Parameters:
        - event (QCloseEvent): Event instance to accept.

        Returns:
        - None
        """
        event.accept()

    def setAppTitle(self, title:str):
        """Set the application title label.

        Parameters:
        - title (str): New title to display.

        Returns:
        - None
        """
        self.ui.label_app_title.setText(title)

    def setAppCredits(self, credits:str):
        """Set the application credits label.

        Parameters:
        - credits (str): Credits string.

        Returns:
        - None
        """
        self.ui.label_credits.setText(credits)

    def setAppVersion(self, version:str):
        """Set the application version label.

        Parameters:
        - version (str): Version string.

        Returns:
        - None
        """
        self.ui.label_version.setText(version)

    def setLogMsg(self, log_msg:str):
        """Forward a log message to the controller.

        Parameters:
        - log_msg (str): Message to show in the GUI log area.

        Returns:
        - None
        """
        self.controller.set_log_msg(log_msg)

    def setComponentsConfigWidth(self, width):
        """Set the device components configuration panel width.

        Parameters:
        - width (int): Desired width for the configuration area.

        Returns:
        - None
        """
        self.controller.set_component_config_width(width)

    @Slot(bool)
    def s_device_connected(self, status):
        """React to device connection status changes and update the UI.

        Parameters:
        - status (bool): True if connected, False if disconnected.

        Returns:
        - None
        """
        if status:
            self.menu_btn_device_conf.setVisible(True)
            self.menu_btn_connection.setStyleSheet(
                STDTDL_MenuButton.get_stylesheet(
                    STDTDL_MenuButton.STDTDL_Page.PAGE_CONNECTION,
                    True,
                )
            )
        else:
            self.menu_btn_device_conf.setVisible(False)
            self.menu_btn_connection.setStyleSheet(
                STDTDL_MenuButton.get_stylesheet(
                    STDTDL_MenuButton.STDTDL_Page.PAGE_CONNECTION,
                    False,
                )
            )

            if self.page_manager.currentWidget() is not self.connection_page:
                self.page_manager.setCurrentWidget(self.connection_page)

            for i in reversed(range(self.widget_header.layout().count())):
                self.widget_header.layout().itemAt(i).widget().setParent(None)

            if self.widget_device_config is not None:
                for i in reversed(range(self.widget_device_config.layout().count())):
                    self.widget_device_config.layout().itemAt(i).widget().setParent(None)

            if self.widget_plots is not None:
                for i in reversed(range(self.widget_plots.layout().count())):
                    self.widget_plots.layout().itemAt(i).widget().setParent(None)

    @Slot()
    def s_dtm_loading_started(self):
        """Show the loading window when DTM loading starts."""
        self.loading_window = LoadingWindow(
            "Loading...",
            "Device Template Model Loading",
            self.page_manager,
        )
        self.app.processEvents()

    @Slot()
    def s_dtm_loaded(self):
        """Navigate to the device configuration page after DTM is loaded."""
        self.clicked_menu_device_conf()

    @Slot()
    def app_log_file_button_toggled(self, status):
        """Enable/disable app log file saving and toggle menu visibility.

        Parameters:
        - status (bool): True to enable log file; False to disable.

        Returns:
        - None
        """
        self.menu_btn_show_log_file.setVisible(status)
        logger.setup_applevel_logger(
            is_debug=status,
            file_name=f"{datetime.today().strftime('%Y%m%d_%H_%M_%S')}_app_debug.log",
        )

    @Slot()
    def adv_settings_button_toggled(self, status):
        """Show/hide advanced settings (device model loading widget).

        Parameters:
        - status (bool): Visibility flag.

        Returns:
        - None
        """
        self.device_model_loading_widget.setVisible(status)
