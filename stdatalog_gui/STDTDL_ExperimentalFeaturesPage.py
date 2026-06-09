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

"""Experimental Features Page for the ST DTDL GUI.

Provides an interactive UI for advanced features like Data Toolkit plugin management and
ST AIoT Craft integration (login, dataset listing/creation, and acquisitions upload).

This module acts as a bridge between the GUI and external services, coordinating background
threads and async tasks while keeping the Qt event loop responsive. It exposes widgets and
helpers used to build a cohesive workflow:

- Manage Data Toolkit plugin folder selection and validation.
- Handle login/logout flows for ST AIoT Craft.
- Retrieve and display datasets; create new ones.
- Select local acquisitions and upload them asynchronously.

Design Notes:
- Uses `ThreadPoolExecutor` and dedicated asyncio event loops in worker threads to avoid
    reusing closed loops.
- Communicates across threads via Qt `Signal`s to safely update the UI.
- Respects the application's 100-character line width for readability.
"""

import os
import sys
import subprocess
import asyncio
import importlib
import threading

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QCheckBox,
    QGroupBox,
    QLabel,
    QWidget,
    QSizePolicy,
    QDialog,
    QPlainTextEdit,
    QVBoxLayout,
)
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection
from PySide6.QtCore import QDir, QObject
from PySide6.QtGui import QColor, QIcon
from PySide6.QtUiTools import QUiLoader

import stdatalog_gui.UI.images #NOTE don't delete this! it is used from resource_filename (@row 35)
from stdatalog_gui.UI.styles import STDTDL_Chip, STDTDL_PushButton
from stdatalog_gui.Widgets.LoadingWindow import StaticLoadingWindow, WaitingDialog

from pkg_resources import resource_filename

from stdatalog_gui.Widgets.PluginListItemWidget import PluginListItemWidget
from stdatalog_dtk.HSD_DataToolkit_Pipeline import HSD_DataToolkit_Pipeline

import stdatalog_core.HSD_utils.staiotcraft_dependencies.p310
import stdatalog_core.HSD_utils.staiotcraft_dependencies.p311
import stdatalog_core.HSD_utils.staiotcraft_dependencies.p312
import stdatalog_core.HSD_utils.staiotcraft_dependencies.p313

oidc_client_whl_path_310 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p310',
    'oidc_client-0.2.6-py3-none-any.whl',
)
vespucci_python_utils_whl_path_310 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p310',
    'vespucci_python_utils-0.1.2-py3-none-any.whl',
)
dataset_models_whl_path_310 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p310',
    'dataset_models-0.1.7-py3-none-any.whl',
)
dataset_api_client_whl_path_310 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p310',
    'dataset_api_client-0.1.5-py3-none-any.whl',
)
staiotcraft_sdk_whl_path_310 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p310',
    'staiotcraft_sdk-1.1.0-py3-none-any.whl',
)

oidc_client_whl_path_311 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p311',
    'oidc_client-0.2.6-py3-none-any.whl',
)
vespucci_python_utils_whl_path_311 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p311',
    'vespucci_python_utils-0.1.2-py3-none-any.whl',
)
dataset_models_whl_path_311 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p311',
    'dataset_models-0.1.7-py3-none-any.whl',
)
dataset_api_client_whl_path_311 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p311',
    'dataset_api_client-0.1.5-py3-none-any.whl',
)
staiotcraft_sdk_whl_path_311 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p311',
    'staiotcraft_sdk-1.1.0-py3-none-any.whl',
)

oidc_client_whl_path_312 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p312',
    'oidc_client-0.2.6-py3-none-any.whl',
)
vespucci_python_utils_whl_path_312 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p312',
    'vespucci_python_utils-0.1.2-py3-none-any.whl',
)
dataset_models_whl_path_312 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p312',
    'dataset_models-0.1.7-py3-none-any.whl',
)
dataset_api_client_whl_path_312 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p312',
    'dataset_api_client-0.1.5-py3-none-any.whl',
)
staiotcraft_sdk_whl_path_312 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p312',
    'staiotcraft_sdk-1.1.0-py3-none-any.whl',
)

oidc_client_whl_path_313 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p313',
    'oidc_client-0.2.6-py3-none-any.whl',
)
vespucci_python_utils_whl_path_313 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p313',
    'vespucci_python_utils-0.1.2-py3-none-any.whl',
)
dataset_models_whl_path_313 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p313',
    'dataset_models-0.1.7-py3-none-any.whl',
)
dataset_api_client_whl_path_313 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p313',
    'dataset_api_client-0.1.5-py3-none-any.whl',
)
staiotcraft_sdk_whl_path_313 = resource_filename(
    'stdatalog_core.HSD_utils.staiotcraft_dependencies.p313',
    'staiotcraft_sdk-1.1.0-py3-none-any.whl',
)

check_path = resource_filename(
    'stdatalog_gui.UI.icons',
    'outline_check_white_18dp.png',
)
cloud_upload_path = resource_filename(
    'stdatalog_gui.UI.icons',
    'outline_cloud_upload_white_18dp.png',
)

hsd2_folder_icon_path = resource_filename(
    'stdatalog_gui.UI.icons',
    'baseline_folder_open_white_18dp.png',
)

from stdatalog_gui.Widgets.AcqListItemWidget import AcqListItemWidget
from stdatalog_core.HSD.HSDatalog import HSDatalog
import stdatalog_core.HSD_utils.logger as logger

DEPENDENCY_OK = 0
PYTHON_VERSION_ERROR = -1
DEPENDENCY_INSTALL_ERROR = -2

selected_stylesheet = (
    "border: transparent; background-color: rgb(255, 221, 64);"
    "color: rgb(3, 35, 75);"
)
unselected_stylesheet = (
    "border: transparent; background-color: rgb(39, 44, 54);"
    "color: rgb(210,210,210);"
)

# Workspace folder.
WORKSPACE_PATH = os.path.join(os.path.expanduser('~'), "workspace")

log = logger.get_logger(__name__)

class InstallerThread(QThread):
    """Installs ST AIoT Craft dependencies in a background thread.

    Detects the current Python minor version to choose the correct wheel files, installs
    required packages via `pip`, and emits `finished` when done.
    """
    finished = Signal()

    def run(self):
        """Execute the dependency installation process.

        Parameters:
        - None

        Returns:
        - None
        """

        #Check python version and install the correct whl
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if python_version == "3.10":
            oidc_client_whl_path = oidc_client_whl_path_310
            vespucci_python_utils_whl_path = vespucci_python_utils_whl_path_310
            dataset_models_whl_path = dataset_models_whl_path_310
            dataset_api_client_whl_path = dataset_api_client_whl_path_310
            staiotcraft_sdk_whl_path = staiotcraft_sdk_whl_path_310
        elif python_version == "3.11":
            oidc_client_whl_path = oidc_client_whl_path_311
            vespucci_python_utils_whl_path = vespucci_python_utils_whl_path_311
            dataset_models_whl_path = dataset_models_whl_path_311
            dataset_api_client_whl_path = dataset_api_client_whl_path_311
            staiotcraft_sdk_whl_path = staiotcraft_sdk_whl_path_311
        elif python_version == "3.12":
            oidc_client_whl_path = oidc_client_whl_path_312
            vespucci_python_utils_whl_path = vespucci_python_utils_whl_path_312
            dataset_models_whl_path = dataset_models_whl_path_312
            dataset_api_client_whl_path = dataset_api_client_whl_path_312
            staiotcraft_sdk_whl_path = staiotcraft_sdk_whl_path_312
        elif python_version == "3.13":
            oidc_client_whl_path = oidc_client_whl_path_313
            vespucci_python_utils_whl_path = vespucci_python_utils_whl_path_313
            dataset_models_whl_path = dataset_models_whl_path_313
            dataset_api_client_whl_path = dataset_api_client_whl_path_313
            staiotcraft_sdk_whl_path = staiotcraft_sdk_whl_path_313
        else:
            log.error(f"Unsupported Python version: {python_version}")
            # if loading_dialog.dialog.isVisible():
            #     loading_dialog.loadingDone()
            # return PYTHON_VERSION_ERROR

        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", oidc_client_whl_path]
        )
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                vespucci_python_utils_whl_path,
            ]
        )
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", dataset_models_whl_path]
        )
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", dataset_api_client_whl_path]
        )
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", staiotcraft_sdk_whl_path]
        )
        # loading_dialog.loadingDone()

        subprocess.run(["pip", "install", "requests"])
        self.finished.emit()

class STAIoTCraftLoginThread(QThread):
    """Performs ST AIoT Craft login in a background thread.

    Emits `login_finished(bool)` indicating success or failure to allow safe UI updates.
    """
    login_finished = Signal(bool)

    def __init__(self, staiotcraft_client, parent=None):
        super().__init__(parent)
        self.staiotcraft_client = staiotcraft_client

    def run(self):
        """Attempt to log in using the provided client.

        Parameters:
        - None

        Returns:
        - None
        """
        try:
            self.staiotcraft_client.login()
            self.login_finished.emit(True)
        except Exception as e:
            log.error(f"Login failed: {e}")
            self.login_finished.emit(False)

class STAIoTCraftDataset(QObject):
    """Lightweight dataset view-model for selection and upload flows.

    Attributes:
    - name (str): Dataset name.
    - description (str): Dataset description.
    - id (str): Unique dataset identifier.
    - device (str | None): Associated device name (if any).
    - creation_time (str): Human-readable creation timestamp.
    - last_update_time (str): Human-readable last update timestamp.
    - tag_classes (list[str]): Ground-truth label classes.
    - is_dataset_selected (bool): UI selection state.
    """

    def __init__(self, name, description, id, device, creation_time, last_update_time, tag_classes):
        super().__init__()
        self.name = name
        self.description = description
        self.id = id
        self.device = device
        self.creation_time = creation_time
        self.last_update_time = last_update_time
        self.tag_classes = tag_classes
        self.is_dataset_selected = False

class STAIoTCraftCreateDatasetDialog(QDialog):
    """Dialog to create a dataset on ST AIoT Craft.

    Allows entering a dataset name and optional description, validates input, and calls a
    provided callback to perform creation.
    """

    def __init__(self, dataset_creation_cb, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.dataset_creation_cb = dataset_creation_cb

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            DatasetListItemWidget, module="DatasetListItemWidget"
        )
        loader = QUiLoader()
        dataset_creation_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "create_dataset_dialog.ui",
            ),
            parent,
        )

        self.dataset_name_textEdit = dataset_creation_widget.findChild(
            QLineEdit, "dataset_name_textEdit"
        )
        self.dataset_description_plainTextEdit = dataset_creation_widget.findChild(
            QPlainTextEdit, "dataset_description_plainTextEdit"
        )

        self.frame_dataset_classes = dataset_creation_widget.findChild(
            QFrame, "frame_dataset_classes"
        )
        self.frame_dataset_classes.setVisible(False)

        self.create_button = dataset_creation_widget.findChild(QPushButton, "create_button")
        self.create_button.clicked.connect(self.create_dataset)
        self.cancel_button = dataset_creation_widget.findChild(QPushButton, "cancel_button")
        self.cancel_button.clicked.connect(self.reject)
        self.dataset_error_label = dataset_creation_widget.findChild(QLabel, "dataset_error_label")
        self.dataset_error_label.setVisible(False)

        self.setWindowTitle("Dataset Creation")
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(dataset_creation_widget)

    def create_dataset(self):
        """Validate inputs and invoke dataset creation callback.

        Parameters:
        - None

        Returns:
        - None
        """
        self.dataset_error_label.setVisible(False)
        dataset_name = self.dataset_name_textEdit.text()
        dataset_description = self.dataset_description_plainTextEdit.toPlainText()
        if not dataset_name:
            log.error("Dataset name cannot be empty.")
            self.dataset_error_label.setText("Dataset name cannot be empty.")
            self.dataset_error_label.setVisible(True)
            return
        self.dataset_creation_cb(dataset_name, dataset_description)
        self.accept()
class DatasetListItemWidget(QWidget):
    """List item widget that visualizes a dataset entry.

    Displays name, description, ID, timestamps, and tag classes as chips; supports selection
    and emits callbacks when clicked.
    """
    def __init__(self, dataset, dataset_clicked_cb = None, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.dataset_clicked_cb = dataset_clicked_cb
        self.dataset_name = dataset.name
        self.dataset_description = dataset.description
        self.dataset_id = dataset.id
        self.creation_time = dataset.created.strftime("%Y-%m-%d %H:%M:%S")
        self.last_update_time = dataset.modified.strftime("%Y-%m-%d %H:%M:%S")
        self.tag_classes = dataset.ground_truth_labels
        self.is_dataset_selected = False
        self.chip_colors = [QColor('#B6CE5F'),
                            QColor('#62C3EB'),
                            QColor('#EB3297'),
                            QColor('#6AC1A4')]

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            DatasetListItemWidget,
            module="DatasetListItemWidget",
        )
        loader = QUiLoader()
        dataset_item_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "dataset_list_item_widget.ui",
            ),
            parent,
        )
        self.frame_dataset:QFrame = dataset_item_widget.frame_dataset
        self.frame_dataset_name:QFrame = self.frame_dataset.findChild(
            QFrame, "frame_dataset_name"
        )
        self.label_dataset_name = self.frame_dataset.findChild(
            QPushButton, "label_dataset_name"
        )
        self.label_dataset_name.setText(self.dataset_name)
        self.label_dataset_name.clicked.connect(self.dataset_clicked)
        self.label_dataset_description = self.frame_dataset.findChild(
            QLabel, "label_dataset_description"
        )
        self.label_dataset_description.setText(self.dataset_description)
        self.label_dataset_id = self.frame_dataset.findChild(
            QPushButton, "label_dataset_id"
        )
        self.label_dataset_id.setText(self.dataset_id)
        self.frame_dataset_components = dataset_item_widget.findChild(
            QFrame, "frame_dataset_components"
        )
        self.dataset_creation_textEdit = self.frame_dataset_components.findChild(
            QLineEdit, "dataset_creation_textEdit"
        )
        self.dataset_last_updated_textEdit = self.frame_dataset_components.findChild(
            QLineEdit, "dataset_last_updated_textEdit"
        )
        self.frame_dataset_classes = self.frame_dataset_components.findChild(
            QFrame, "frame_dataset_classes"
        )

        self.dataset_creation_textEdit.setText(str(self.creation_time))
        self.dataset_last_updated_textEdit.setText(str(self.last_update_time))

        for i, c in enumerate(self.tag_classes):
            tc_chip = QPushButton(c)
            tc_chip.setMinimumWidth(60)
            tc_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            tc_chip.setStyleSheet(STDTDL_Chip.color(self.chip_colors[i%4]))
            tc_chip.setCheckable(True)
            tc_chip.setEnabled(False)
            tc_chip.setChecked(True)
            self.frame_dataset_classes.layout().addWidget(tc_chip)
        horizontal_spacer = QWidget()
        horizontal_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.frame_dataset_classes.layout().addWidget(horizontal_spacer)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(dataset_item_widget)
        self.shrinked_size = self.sizeHint()

    def dataset_clicked(self, event):
        """Forward click to the provided callback.

        Parameters:
        - event (QEvent): Click event (unused).

        Returns:
        - None
        """
        _ = event # Unused parameter
        self.dataset_clicked_cb(self)
class STDTDL_ExperimentalFeaturesPage(QObject):
    """GUI controller for experimental features.

    Centralizes logic to manage Data Toolkit plugin folder selection/validation and ST AIoT
    Craft operations (login/logout, dataset management, acquisitions upload). It wires Qt UI
    widgets to actions, maintains state for selections and statuses, and runs async work in
    background threads.

    Parameters:
    - page_widget (QWidget): Root widget containing the experimental features UI.
    - controller: Application controller with Qt app and pipeline utilities.

    Returns:
    - None
    """

    login_finished = Signal()
    upload_finished = Signal()
    sig_datasets_retrieved = Signal(object)
    sig_acquisition_uploaded = Signal(dict)
    sig_acquisition_upload_error = Signal(dict)
    sig_dataset_created = Signal(object)

    def __init__(self, page_widget, controller):
        super().__init__()
        self.event_loop = None
        self.controller = controller
        self.executor = ThreadPoolExecutor()
        self.dependencies_install_dialog = None

        self.sig_datasets_retrieved.connect(self.on_datasets_retrieved)
        self.sig_acquisition_uploaded.connect(self.on_acquisition_uploaded)
        self.sig_acquisition_upload_error.connect(self.on_acquisition_upload_error)
        self.sig_dataset_created.connect(self.on_dataset_created)

        self.staiotcraft_client = None
        self.logged_in = False
        self.login_loading_dialog = None
        self.selected_acquisitions = []
        self.acquisition_uploaded = {}
        self.datasets = []
        self.selected_dataset = None

        self.page_widget = page_widget
        self.main_layout = page_widget.findChild(QFrame, "frame_experimental_features")

        # Data Toolkit settings frame
        self.dt_frame_content = page_widget.findChild(QFrame, "dt_frame_content")
        self.dt_frame_content.setEnabled(False)
        self.dt_plugins_folder_button = self.dt_frame_content.findChild(
            QPushButton, "dt_plugins_folder_button"
        )
        self.dt_plugins_folder_button.clicked.connect(self.select_dt_plugins_folder)
        self.dt_plugin_folder_lineEdit:QLineEdit = self.dt_frame_content.findChild(
            QLineEdit, "dt_plugins_folder_lineEdit"
        )
        self.dt_enabled_checkBox = page_widget.findChild(QCheckBox, "dt_enabled_checkBox")
        self.dt_enabled_checkBox.toggled.connect(self.dt_enable_button_toggled)
        self.dt_plugin_listWidget = page_widget.findChild(
            QListWidget, "dt_plugin_listWidget"
        )

        # layout_device_config
        self.acq_upload_main_layout = page_widget.findChild(QFrame, "acq_upload_frame")
        self.acq_upload_frame_content = page_widget.findChild(QFrame, "acq_upload_frame_content")
        self.acq_upload_frame_content.setEnabled(False)
        self.acquisition_upload_checkBox = page_widget.findChild(
            QCheckBox, "upload_acquisition_checkBox"
        )
        self.acquisition_upload_checkBox.toggled.connect(self.acquisition_upload_checkBox_toggled)

        self.login_error_label = page_widget.findChild(QLabel, "login_error_label")
        self.login_error_label.setVisible(False)
        self.acq_upload_error_label = page_widget.findChild(QLabel, "acq_upload_error_label")
        self.acq_upload_error_label.setVisible(False)

        self.login_button = page_widget.findChild(QPushButton, "login_button")
        self.login_button.setEnabled(False)
        self.login_button.clicked.connect(self._on_login_button_clicked)
        # self.login_button.clicked.connect(lambda: asyncio.run(self.show_login_dialog()))

        self.howto_button = page_widget.findChild(QPushButton, "howto_button")
        self.howto_button.clicked.connect(self.open_howto)

        self.groupBox_datasets_list = page_widget.findChild(
            QGroupBox, "groupBox_datasets_list"
        )
        self.datasets_listWidget:QListWidget = page_widget.findChild(
            QListWidget, "datasets_listWidget"
        )
        self.datasets_listWidget.itemClicked.connect(self.on_dataset_item_click)
        self.groupBox_datasets_list.setEnabled(False)

        self.create_new_dataset_button = page_widget.findChild(
            QPushButton, "create_new_dataset_button"
        )
        self.create_new_dataset_button.clicked.connect(self.show_new_dataset_dialog)
        self.create_new_dataset_button.setEnabled(False)

        self.groupBox_base_acquisition_selection = page_widget.findChild(
            QFrame, "groupBox_base_acquisition_selection"
        )
        self.base_acq_folder_button = page_widget.findChild(QPushButton, "base_acq_folder_button")
        self.base_acq_folder_button.clicked.connect(self.select_base_acquisitions_folder)
        self.base_acq_folder_textEdit:QLineEdit = page_widget.findChild(
            QLineEdit, "base_acq_folder_textEdit"
        )
        self.groupBox_base_acquisition_selection.setEnabled(False)

        self.groupBox_acquisitions_list = page_widget.findChild(
            QGroupBox, "groupBox_acquisitions_list"
        )
        self.acquisitions_listWidget:QListWidget = page_widget.findChild(
            QListWidget, "acquisitions_listWidget"
        )

        # Connect the itemClicked signal to the on_item_click function
        self.acquisitions_listWidget.itemClicked.connect(self.acquisition_selected)

        self.groupBox_acquisitions_list.setEnabled(False)

        self.groupBox_upload_settings = page_widget.findChild(QGroupBox, "groupBox_upload_settings")
        self.upload_acquisition_button = page_widget.findChild(
            QPushButton, "upload_acquisition_button"
        )
        # self.upload_acquisition_button.clicked.connect(self.upload_acquisitions)
        self.upload_acquisition_button.clicked.connect(self._on_acquisitions_upload_button_clicked)
        self.groupBox_upload_settings.setEnabled(False)

    def check_dependencies(self):
        """
        Check for required packages and initiate installation if missing.
        """
        log.info("Checking additional required packages...")

        # required package
        required_package = "staiotcraft_sdk"

        # Check for missing packages
        missing_staiotcraft_sdk = False
        try:
            __import__(required_package)
        except ImportError:
            if required_package == "staiotcraft_sdk":
                missing_staiotcraft_sdk = True

        # Notify user of missing packages
        if missing_staiotcraft_sdk:
            try:
                self.start_dependencies_installation()
            except Exception as e:
                log.error(f"Failed to install the required package: {required_package}")
                log.error(f"Error: {e}")
                if self.dependencies_install_dialog.dialog.isVisible():
                    self.dependencies_install_dialog.loadingDone()
                return DEPENDENCY_INSTALL_ERROR
        else:
            log.info("All required packages are installed.")

        return DEPENDENCY_OK

    def start_dependencies_installation(self):
        """
        Start the installation of required dependencies in a background thread.
        """
        self.acq_upload_frame_content.setEnabled(False)
        self.dependencies_install_dialog = StaticLoadingWindow(
            "Installing required packages...",
            (
                "staiotcraft_sdk package is mandatory to use the ST AIoT Craft "
                "Acquisitions upload feature.\nPlease wait while the package is being "
                "installed..."
            ),
            self.page_widget,
        )
        self.controller.qt_app.processEvents()

        log.warning("The following required packages are missing:")
        log.warning(" - (staiotcraft_sdk) staiotcraft_sdk")
        log.info(
            "This package is required to use the ST AIoT Craft "
            "Acquisitions upload feature and will "
            "be now installed."
        )
        self.thread = InstallerThread()
        self.thread.finished.connect(self.on_dependencies_install_finished)
        self.thread.start()

    def on_dependencies_install_finished(self):
        """
        Handle the completion of the dependency installation process.
        """
        self.dependencies_install_dialog.loadingDone()
        self.acq_upload_frame_content.setEnabled(True)

    def update_datasets_selected_stylesheet(self):
        """Update item styles based on dataset selection state.

        Parameters:
        - None

        Returns:
        - None
        """
        for i in range(self.datasets_listWidget.count()):
            item = self.datasets_listWidget.item(i)
            custom_widget = self.datasets_listWidget.itemWidget(item)
            if custom_widget.is_dataset_selected:
                custom_widget.frame_dataset_name.setStyleSheet(selected_stylesheet)
            else:
                custom_widget.frame_dataset_name.setStyleSheet(unselected_stylesheet)

    def _on_login_button_clicked(self):
        """Handle login/logout button click by delegating to `start_login`.

        Parameters:
        - None

        Returns:
        - None
        """
        self.start_login()

    def create_staiotcraft_client(self):
        """
        Create the ST AIoT Craft client.
        """
        try:
            staiotcraft_module = importlib.import_module('staiotcraft_sdk.staiotcraft_client')
            STAIoTCraftClient = getattr(staiotcraft_module, "STAIoTCraftClient")
            self.staiotcraft_client = STAIoTCraftClient.get_desktop_client(
                workspace_folder=WORKSPACE_PATH
            )
            return self.staiotcraft_client
        except Exception as e:
            log.error(f"Error creating ST AIoT Craft client: {e}")
            return None

    async def get_staiotcraft_datasets(self):
        """
        Get the datasets from the ST AIoT Craft platform.
        """
        try:
            if self.staiotcraft_client is None:
                self.staiotcraft_client = self.create_staiotcraft_client()
            if self.staiotcraft_client is not None:
                datasets = await self.staiotcraft_client.get_datasets()
                self.sig_datasets_retrieved.emit(datasets)
            else:
                log.error("ST AIoT Craft client is not initialized.")
                return []
        except Exception as e:
            log.error(f"Error getting datasets: {e}")
            return []

    def reset_UI(self):
        """
        Reset the UI elements to their initial state.
        """
        self.selected_acquisitions = []
        self.acquisition_uploaded = {}
        self.datasets = []
        self.selected_dataset = None

        self.login_button.setText("Login")
        self.login_button.setStyleSheet(STDTDL_PushButton.green)
        self.acq_upload_error_label.setText("")
        self.acq_upload_error_label.setVisible(False)
        self.upload_acquisition_button.setText("Upload Acquisitions")
        self.upload_acquisition_button.setIcon(QIcon(cloud_upload_path))
        self.groupBox_base_acquisition_selection.setEnabled(False)
        self.create_new_dataset_button.setEnabled(False)
        self.groupBox_datasets_list.setEnabled(False)
        self.groupBox_acquisitions_list.setEnabled(False)
        self.groupBox_upload_settings.setEnabled(False)

        self.acquisitions_listWidget.clear()
        self.datasets_listWidget.clear()

    def on_datasets_retrieved(self, datasets):
        """
        Handle the datasets retrieved from the ST AIoT Craft platform.
        This method populates the datasets list widget with the retrieved datasets.
        """
        self.datasets_listWidget.clear()
        if datasets:
            for dataset in datasets.items:
                item = QListWidgetItem(self.datasets_listWidget)
                custom_widget = DatasetListItemWidget(dataset, self.on_dataset_item_click)
                self.datasets_listWidget.addItem(item)
                self.datasets_listWidget.setItemWidget(item, custom_widget)
                item.setSizeHint(custom_widget.sizeHint())
        else:
            log.info("No datasets found.")
        self.update_datasets_selected_stylesheet()

    def login_finished_handler(self, success):
        """
        Handle the login finished signal.
        """
        if success:
            self.login_error_label.setVisible(False)
            self.groupBox_datasets_list.setEnabled(True)
            self.groupBox_acquisitions_list.setEnabled(True)
            #self.groupBox_upload_settings.setEnabled(True)
            self.create_new_dataset_button.setEnabled(True)
            self.controller.qt_app.processEvents()
            self.executor.submit(self._run_async, self.get_staiotcraft_datasets)
            #print("Datasets fetched successfully.")
        else:
            self.login_error_label.setVisible(True)
            self.login_error_label.setText("Login failed. Please try again.")
            log.error("Login failed. Please try again.")

    def logout_finished_handler(self, success):
        """
        Handle the logout finished signal.
        """
        if success:
            self.login_error_label.setVisible(False)
            self.groupBox_datasets_list.setEnabled(False)
            self.groupBox_acquisitions_list.setEnabled(False)
            #self.groupBox_upload_settings.setEnabled(True)
            self.create_new_dataset_button.setEnabled(False)
        else:
            self.login_error_label.setVisible(True)
            self.login_error_label.setText("Logout failed. Please try again.")
            log.error("Logout failed. Please try again.")

    def start_login(self):
        """
        Start the login process for the ST AIoT Craft platform.
        This method checks if the user is already logged in, and if not, it creates a new
        ST AIoT Craft client and logs in.
        """
        try:
            if not self.logged_in:
                self.login_error_label.setText("")
                self.login_error_label.setVisible(False)
                self.login_loading_dialog = StaticLoadingWindow(
                    "ST AIoT Craft Login",
                    (
                        "Logging in to the ST AIoT Craft platform...\n"
                        "Please fill the login form opened in your browser with your ST account "
                        "credentials.\nIf you don't have an account, please create one."
                    ),
                    self.page_widget,
                )
                self.controller.qt_app.processEvents()

                # Create the ST AIoT Craft client.
                self.staiotcraft_client = self.create_staiotcraft_client()

                self.login_button.setText("Logout")
                self.login_button.setStyleSheet(STDTDL_PushButton.red)
                self.groupBox_base_acquisition_selection.setEnabled(True)
                if self.login_loading_dialog.dialog.isVisible():
                    self.login_loading_dialog.loadingDone()
                self.login_finished_handler(True)
                self.logged_in = True
            else:
                # Logout logic
                self.reset_UI()
                self.staiotcraft_client = None
                if (
                    self.login_loading_dialog is not None
                    and self.login_loading_dialog.dialog.isVisible()
                ):
                    self.login_loading_dialog.loadingDone()
                self.logout_finished_handler(True)
                self.logged_in = False
        except Exception as e:
            log.error(f"Error during login: {e}")
            if (
                self.login_loading_dialog is not None
                and self.login_loading_dialog.dialog.isVisible()
            ):
                self.login_loading_dialog.loadingDone()
            self.reset_UI()
            self.staiotcraft_client = None
            if self.logged_in:
                self.logout_finished_handler(False)
            else:
                self.login_finished_handler(False)

    def on_dataset_item_click(self, item):
        """Toggle dataset selection and update UI state.

        Parameters:
        - item (QListWidgetItem | DatasetListItemWidget): Clicked item or widget.

        Returns:
        - None
        """
        if isinstance(item, DatasetListItemWidget):
            custom_widget = item
            for i in range(self.datasets_listWidget.count()):
                if (
                    self.datasets_listWidget.itemWidget(
                        self.datasets_listWidget.item(i)
                    )
                    == custom_widget
                ):
                    item = self.datasets_listWidget.item(i)
                    self.datasets_listWidget.setCurrentItem(item)
        else:
            custom_widget = self.datasets_listWidget.itemWidget(item)

        clicked_widget = custom_widget
        custom_widget.is_dataset_selected = not custom_widget.is_dataset_selected

        # Convert custom_widget (DatasetListItemWidget) to STAIoTCraftDataset
        dataset_obj = STAIoTCraftDataset(
            name=custom_widget.dataset_name,
            description=custom_widget.dataset_description,
            id=custom_widget.dataset_id,
            device=None,
            creation_time=custom_widget.creation_time,
            last_update_time=custom_widget.last_update_time,
            tag_classes=custom_widget.tag_classes
        )
        self.selected_dataset = dataset_obj if custom_widget.is_dataset_selected else None

        for i in range(self.datasets_listWidget.count()):
            item = self.datasets_listWidget.item(i)
            custom_widget = self.datasets_listWidget.itemWidget(item)
            if custom_widget is not clicked_widget:
                custom_widget.is_dataset_selected = False

        self.update_datasets_selected_stylesheet()
        self.upload_acquisition_button.setText("Upload Acquisitions")
        self.upload_acquisition_button.setIcon(QIcon(cloud_upload_path))
        self.acq_upload_error_label.setText("")
        self.acq_upload_error_label.setVisible(False)
        if self.selected_dataset is not None and self.selected_acquisitions != []:
            self.groupBox_upload_settings.setEnabled(True)
        else:
            self.groupBox_upload_settings.setEnabled(False)

    def create_dataset_handler(self, dataset_name, dataset_description=None):
        """
        Callback function to handle the creation of a new dataset.
        This function is called when the user clicks the "Create" button in the dataset
        creation dialog.
        """
        if not dataset_name:
            log.error("Dataset name cannot be empty.")
            return
        try:
            self.login_error_label.setVisible(False)
            self.login_error_label.setText("")
            self.executor.submit(
                self._run_async,
                self.staiotcraft_create_dataset,
                dataset_name,
                dataset_description,
            )
        except Exception as e:
            log.error(f"Failed to create a new dataset: {e}")

    async def staiotcraft_create_dataset(self, dataset_name, dataset_description=None):
        """
        Create a new dataset on the ST AIoT Craft platform.
        This method is called when the user clicks the "Create" button in the dataset
        creation dialog.
        """
        self.login_error_label.setVisible(False)
        self.login_error_label.setText("")
        max_retries = 2
        for attempt in range(max_retries):
            try:
                dataset = await self.staiotcraft_client.create_dataset(
                    dataset_name=dataset_name,
                    ground_truth_labels=[],
                    description=(
                        dataset_description
                        or 'This is an example dataset created by means of the '
                           'STAIoTCraftSDK_Python.'
                    ),
                )
                if not dataset:
                    raise Exception('Failed to create a new dataset.')
                self.sig_dataset_created.emit(dataset)
                break
            except Exception as e:
                if hasattr(e, 'args') and any("Event loop is closed" in str(arg) for arg in e.args):
                    if attempt < max_retries - 1:
                        continue
                else:
                    log.error(f"Failed to create a new dataset: {e}")
                    self.login_error_label.setText(f"Failed to create a new dataset: {e}")
                    self.login_error_label.setVisible(True)
                    self.sig_dataset_created.emit(None)

    def on_dataset_created(self, dataset):
        """
        Handle the dataset created signal.
        This method is called when a new dataset is successfully created.
        """
        if dataset:
            item = QListWidgetItem(self.datasets_listWidget)
            custom_widget = DatasetListItemWidget(dataset, self.on_dataset_item_click)
            self.datasets_listWidget.addItem(item)
            self.datasets_listWidget.setItemWidget(item, custom_widget)
            item.setSizeHint(custom_widget.sizeHint())
            self.update_datasets_selected_stylesheet()
            print(f"Dataset '{dataset.name}' created successfully.")
            # Select the newly created item in the acquisitions list widget and scroll to it
            if self.datasets_listWidget.count() > 0:
                last_index = self.datasets_listWidget.count() - 1
                self.datasets_listWidget.setCurrentRow(last_index)
                self.datasets_listWidget.scrollToItem(self.datasets_listWidget.item(last_index))
                self.on_dataset_item_click(custom_widget)
        else:
            log.error("Failed to create a new dataset.")

    def show_new_dataset_dialog(self):
        """Open the dialog to create a new ST AIoT Craft dataset.

        Parameters:
        - None

        Returns:
        - None
        """
        new_dataset_dialog = STAIoTCraftCreateDatasetDialog(
            self.create_dataset_handler, self.page_widget
        )
        new_dataset_dialog.setWindowTitle("Dataset  Creation")
        new_dataset_dialog.exec()
        self.controller.qt_app.processEvents()

    def select_dt_plugins_folder(self):
        """Let the user pick the Data Toolkit plugins folder and populate the list.

        Parameters:
        - None

        Returns:
        - None
        """
        self.controller.remove_dt_plugins_folder()
        # Open a dialog to select a directory
        folder_path = QFileDialog.getExistingDirectory(None, 'Select Folder')
        if folder_path:
            self.dt_plugin_listWidget.clear()
            self.dt_plugin_folder_lineEdit.setText(folder_path)
            self.controller.set_dt_plugins_folder(folder_path)
            # List all .py files in the specified data toolkit plugins directory
            files = os.listdir(folder_path)
            py_files = [
                f
                for f in files
                if os.path.isfile(os.path.join(folder_path, f))
                and f.endswith('.py')
                and f != "__init__.py"
            ]
            # Remove the .py extension
            plugin_name = [os.path.splitext(f)[0] for f in py_files]
            for pn in plugin_name:
                if HSD_DataToolkit_Pipeline.validate_plugin(pn) is None:
                    continue
                item = QListWidgetItem(self.dt_plugin_listWidget)
                custom_widget = PluginListItemWidget(pn, item, self.dt_plugin_listWidget)
                self.dt_plugin_listWidget.addItem(item)
                self.dt_plugin_listWidget.setItemWidget(item, custom_widget)
                item.setSizeHint(custom_widget.sizeHint())
            self.dt_enable_button_toggled(True)

    def dt_enable_button_toggled(self, status):
        """Enable or disable Data Toolkit and (re)create the pipeline if needed.

        Parameters:
        - status (bool): When True, enable DT and create pipeline; otherwise disable.

        Returns:
        - None
        """
        self.dt_frame_content.setEnabled(status)
        if status:
            if self.dt_plugin_folder_lineEdit.text() != "":
                self.controller.set_dt_plugins_folder(
                    self.dt_plugin_folder_lineEdit.text()
                )
                self.controller.create_data_pipeline()
        else:
            self.controller.set_dt_plugins_folder(None)
            self.controller.destroy_data_pipeline()

    def acquisition_upload_checkBox_toggled(self, status):
        """Toggle acquisitions upload area and check external dependencies.

        Parameters:
        - status (bool): Whether the upload UI should be enabled.

        Returns:
        - None
        """
        if status:
            res = self.check_dependencies()
            if res == PYTHON_VERSION_ERROR:
                self.acquisition_upload_checkBox.setChecked(False)
                self.login_error_label.setText(
                    "--> [ERROR] - Currently only Python 3.11 is supported."
                )
                self.login_error_label.setVisible(True)
                self.login_button.setEnabled(False)
            elif res == DEPENDENCY_INSTALL_ERROR:
                self.acquisition_upload_checkBox.setChecked(False)
                self.login_error_label.setText(
                    "--> [ERROR] Failed to install required packages."
                )
                self.login_error_label.setVisible(True)
                self.login_button.setEnabled(False)
            else:
                self.login_button.setEnabled(True)
        self.acq_upload_frame_content.setEnabled(status)
        self.login_error_label.setVisible(False)

    def open_howto(self):
        """Show the ST AIoT Craft how-to dialog.

        Parameters:
        - None

        Returns:
        - None
        """
        loader = QUiLoader() # Create a QUiLoader instance
        howto_dialog = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "staiotcraft_howto_dialog.ui",
            ),
            self.page_widget,
        ) # Load the info dialog UI
        howto_dialog.exec() # Execute the info dialog

    def select_base_acquisitions_folder(self):
        """Select a base acquisitions folder and populate the acquisitions list.

        Parameters:
        - None

        Returns:
        - None
        """
        # Open a dialog to select a directory
        folder_path = QFileDialog.getExistingDirectory(None, 'Select Folder')
        if folder_path:
            self.base_acq_folder_textEdit.setText(folder_path)

            self.groupBox_acquisitions_list.setEnabled(True)
            # Clear the list widget
            self.acquisitions_listWidget.clear()

            # Get the list of folders in the selected directory
            dir = QDir(folder_path)
            dir.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
            folder_list = dir.entryList()

            # Add folders to the list widget with icons
            for folder in folder_list:
                hsd_version = HSDatalog.validate_hsd_folder(
                    os.path.join(folder_path, folder)
                )
                if hsd_version != HSDatalog.HSDVersion.INVALID:
                    item = QListWidgetItem(self.acquisitions_listWidget)
                    custom_widget = AcqListItemWidget(
                        self.controller,
                        hsd_version,
                        folder_path,
                        folder,
                        item,
                        self.acquisition_selected,
                        self.acquisitions_listWidget,
                    )
                    self.acquisitions_listWidget.addItem(item)
                    self.acquisitions_listWidget.setItemWidget(item, custom_widget)
                    item.setSizeHint(custom_widget.sizeHint())
                else:
                    log.warning(f"Acquisition {folder}")

    def _on_acquisitions_upload_button_clicked(self):
        """Start the acquisitions upload workflow.

        Parameters:
        - None

        Returns:
        - None
        """
        self.start_acquisitions_upload()
        #asyncio.run(self.upload_acquisitions())
        #self.executor.submit(self._run_async, self.upload_acquisitions)

    def on_acquisition_uploaded(self, params):
        """
        Handle the acquisition uploaded signal.
        This method updates the UI to reflect the uploaded acquisition.
        """
        acq_upload_dialog = params["acq_upload_dialog"]
        self.upload_acquisition_button.setText(f"Acquisition Uploaded")
        self.upload_acquisition_button.setIcon(QIcon(check_path))
        self.acq_upload_error_label.setVisible(False)
        acq_upload_dialog.loadingDone()

    def on_acquisition_upload_error(self, params):
        """
        Handle the acquisition upload error signal.
        This method updates the UI to reflect the error during acquisition upload.
        """
        error_msg = params["error"]
        acq_upload_dialog = params["acq_upload_dialog"]
        self.acq_upload_error_label.setVisible(True)
        self.acq_upload_error_label.setText(error_msg)
        acq_upload_dialog.loadingDone()

    def start_acquisitions_upload(self):
        """
        Start the acquisitions upload process.
        This method checks if the user is logged in and if there are selected acquisitions to
        upload.
        If the conditions are met, it starts the upload process.
        """
        if not self.logged_in:
            self.login_error_label.setText(
                "Please login to ST AIoT Craft platform before uploading acquisitions."
            )
            self.login_error_label.setVisible(True)
            return

        if not self.selected_acquisitions:
            self.login_error_label.setText("Please select at least one acquisition to upload.")
            self.login_error_label.setVisible(True)
            return

        for acq_path in self.selected_acquisitions:
            self.acq_upload_error_label.setText("")
            self.acq_upload_error_label.setVisible(False)
            print(f"Uploading acquisition: {acq_path}")
            acquisition_upload_dialog = StaticLoadingWindow(
                "Uploading Acquisition",
                (
                    f"Please wait while the {acq_path} acquisition is being uploaded to the "
                    "ST AIoT Craft platform..."
                ),
                self.page_widget,
            )
            self.controller.qt_app.processEvents()
            self.executor.submit(
                self._run_async,
                self.upload_acquisition,
                {"acq_path": acq_path, "acq_upload_dialog": acquisition_upload_dialog},
            )

    def _run_async(self, coro_func, *args, **kwargs):
        """
        Run an async coroutine in a new event loop in a background thread.
        Ensures the thread's event loop is always fresh and not reused.
        """
        try:
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            self.event_loop.run_until_complete(coro_func(*args, **kwargs))
        except Exception as e:
            log.error(f"Error running async function: {e}")
            #loop = asyncio.new_event_loop()
            #asyncio.set_event_loop(loop)
            #loop.run_until_complete(coro_func(*args, **kwargs))
        finally:
            self.event_loop.close()
            #loop.close()
            # Remove the event loop reference from the thread to avoid reuse of a closed loop
            try:
                del threading.current_thread().__dict__['_asyncio_event_loop']
            except Exception:
                pass

    async def upload_acquisition(self, params):
        """
        Upload a single acquisition to the ST AIoT Craft platform.
        This method is called by the executor to run the upload process asynchronously.
        """
        if not self.logged_in:
            log.error("User is not logged in. Cannot upload acquisition.")
            return

        if not self.selected_dataset:
            log.error("No dataset selected. Cannot upload acquisition.")
            return

        acq_path = params["acq_path"] # Ensure the path is in the correct format
        max_retries = 2
        for attempt in range(max_retries):
            try:
                await self.staiotcraft_client.upload_acquisition(
                    acq_path,
                    os.path.basename(acq_path),
                    self.selected_dataset.id,
                    exists_ok=False,
                )
                self.sig_acquisition_uploaded.emit(params)
                break
            except Exception as e:
                if hasattr(e, 'args') and any("Event loop is closed" in str(arg) for arg in e.args):
                    if attempt < max_retries - 1:
                        continue
                else:
                    e_msg = f"Error uploading acquisition {acq_path}"
                    log.error(e_msg)
                    if hasattr(e, 'message'):
                        e_msg = f"Error uploading acquisition {acq_path}: {e.message}"
                    params["error"] = e_msg
                    self.sig_acquisition_upload_error.emit(params)
                    self.acquisition_uploaded[e_msg] = False

    async def upload_acquisitions(self):
        """
        Upload selected acquisitions to the ST AIoT Craft platform.
        This method uploads all selected acquisitions to the selected dataset on the ST AIoT Craft
        platform.
        """
        loading_dialog = StaticLoadingWindow(
            "Uploading Acquisitions",
            (
                "Please wait while the acquisitions are being uploaded to the ST AIoT Craft "
                "platform..."
            ),
            self.page_widget,
        )
        self.controller.qt_app.processEvents()

        # Configuring AI.
        # print('Configuring AI...')
        # loading_dialog.message_label.setText("Configuring AI...")
        # self.controller.qt_app.processEvents()
        # await self.staiotcraft_client.configure_ai(
        #     model_name = self.staiotcraft_model.get_selected_model_name(),
        #     project_name = self.staiotcraft_model.get_selected_project_name()
        # )
        print('Uploading selected local acquisitions...')
        loading_dialog.message_label.setText(
            "Uploading selected local acquisitions..."
        )
        self.controller.qt_app.processEvents()
        # Uploading a selected local acquisition.
        for acq_path in self.selected_acquisitions:
            acq_upload_msg = f'Uploading acquisition: {acq_path}'
            print(acq_upload_msg)
            loading_dialog.message_label.setText(acq_upload_msg)
            self.controller.qt_app.processEvents()
            try:
                await self.staiotcraft_client.upload_acquisition(
                    acq_path,
                    os.path.basename(acq_path),
                    self.selected_dataset.id,
                    exists_ok=False,
                )
            except Exception as e:
                log.error(f"Failed to upload acquisition: {acq_path}")
                log.error(f"Error: {e}")
                if hasattr(e, 'acquisition_names'):
                    e_msg = f"Error uploading {e.acquisition_names[0]} folder: {e.message}"
                else:
                    e_msg = f"Error uploading {os.path.basename(acq_path)} folder: {e}"
                loading_dialog.message_label.setText(e_msg)
                self.controller.qt_app.processEvents()
                self.acquisition_uploaded[e_msg] = False
                continue
            self.acquisition_uploaded[acq_path] = True
            print("Upload completed.")
            loading_dialog.message_label.setText("Upload completed.")
            self.controller.qt_app.processEvents()

        if all(self.acquisition_uploaded.values()):
            print('All acquisitions uploaded successfully.')
            loading_dialog.message_label.setText("All acquisitions uploaded successfully!!!")
            self.controller.qt_app.processEvents()
            self.upload_acquisition_button.setText("Acquisitions Uploaded")
            self.upload_acquisition_button.setIcon(QIcon(check_path))
            self.acq_upload_error_label.setVisible(False)
        else:
            print('Error uploading acquisitions.')
            error_string = "Failed to upload acquisitions: \n"
            for e_msg, uploaded in self.acquisition_uploaded.items():
                if not uploaded:
                    print(f"{e_msg}")
                    error_string += f"- {e_msg}\n"

            self.acq_upload_error_label.setVisible(True)
            self.acq_upload_error_label.setText(error_string)
            self.controller.qt_app.processEvents()

            loading_dialog.message_label.setText("Error uploading acquisitions.")
            self.controller.qt_app.processEvents()

        loading_dialog.loadingDone()

        self.acquisition_uploaded = {}

    def acquisition_selected(self, item):
        """Toggle selection for an acquisition and update the upload UI state.

        Parameters:
        - item (QListWidgetItem | AcqListItemWidget): Clicked acquisition item or widget.

        Returns:
        - None
        """
        if isinstance(item, AcqListItemWidget):
            custom_widget = item
            for i in range(self.acquisitions_listWidget.count()):
                if (
                    self.acquisitions_listWidget.itemWidget(
                        self.acquisitions_listWidget.item(i)
                    )
                    == custom_widget
                ):
                    item = self.acquisitions_listWidget.item(i)
                    self.acquisitions_listWidget.setCurrentItem(item)
        else:
            custom_widget = self.acquisitions_listWidget.itemWidget(item)

        if custom_widget.acq_folder_path not in self.selected_acquisitions:
            self.selected_acquisitions.append(custom_widget.acq_folder_path)
        else:
            self.selected_acquisitions.remove(custom_widget.acq_folder_path)

        custom_widget.update_acquisition_selected_stylesheet()

        #self.staiotcraft_model.sig_acquisition_selected.emit(custom_widget.acq_folder_path)
        if self.upload_acquisition_button.text() == "Acquisitions Uploaded":
            self.upload_acquisition_button.setText("Upload Acquisitions")
            self.upload_acquisition_button.setIcon(QIcon(cloud_upload_path))
            self.acq_upload_error_label.setVisible(False)
        if self.selected_dataset is not None and self.selected_acquisitions != []:
            self.groupBox_upload_settings.setEnabled(True)
        else:
            self.groupBox_upload_settings.setEnabled(False)
