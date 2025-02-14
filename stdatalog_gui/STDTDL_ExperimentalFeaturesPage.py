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
import sys
import subprocess
import asyncio
import importlib

from PySide6.QtWidgets import QFrame, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QFileDialog, QCheckBox, QGroupBox, QLabel, QWidget, QSizePolicy, QRadioButton
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection
from PySide6.QtCore import QDir, Signal, QObject
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

oidc_client_whl_path_310 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p310', 'oidc_client-0.2.6-py3-none-any.whl')
vespucci_python_utils_whl_path_310 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p310', 'vespucci_python_utils-0.1.2-py3-none-any.whl')
dataset_models_whl_path_310 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p310', 'dataset_models-0.1.7-py3-none-any.whl')
dataset_api_client_whl_path_310 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p310', 'dataset_api_client-0.1.5-py3-none-any.whl')
staiotcraft_sdk_whl_path_310 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p310', 'staiotcraft_sdk-1.0.1-py3-none-any.whl')

oidc_client_whl_path_311 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p311', 'oidc_client-0.2.6-py3-none-any.whl')
vespucci_python_utils_whl_path_311 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p311', 'vespucci_python_utils-0.1.2-py3-none-any.whl')
dataset_models_whl_path_311 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p311', 'dataset_models-0.1.7-py3-none-any.whl')
dataset_api_client_whl_path_311 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p311', 'dataset_api_client-0.1.5-py3-none-any.whl')
staiotcraft_sdk_whl_path_311 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p311', 'staiotcraft_sdk-1.0.1-py3-none-any.whl')

oidc_client_whl_path_312 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p312', 'oidc_client-0.2.6-py3-none-any.whl')
vespucci_python_utils_whl_path_312 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p312', 'vespucci_python_utils-0.1.2-py3-none-any.whl')
dataset_models_whl_path_312 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p312', 'dataset_models-0.1.7-py3-none-any.whl')
dataset_api_client_whl_path_312 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p312', 'dataset_api_client-0.1.5-py3-none-any.whl')
staiotcraft_sdk_whl_path_312 = resource_filename('stdatalog_core.HSD_utils.staiotcraft_dependencies.p312', 'staiotcraft_sdk-1.0.1-py3-none-any.whl')

check_path = resource_filename('stdatalog_gui.UI.icons', 'outline_check_white_18dp.png')
cloud_upload_path = resource_filename('stdatalog_gui.UI.icons', 'outline_cloud_upload_white_18dp.png')

hsd2_folder_icon_path = resource_filename('stdatalog_gui.UI.icons', 'baseline_folder_open_white_18dp.png')

from stdatalog_gui.Widgets.AcqListItemWidget import AcqListItemWidget
from stdatalog_core.HSD.HSDatalog import HSDatalog
import stdatalog_core.HSD_utils.logger as logger
from PySide6.QtWidgets import QVBoxLayout, QLabel

DEPENDENCY_OK = 0
PYTHON_VERSION_ERROR = -1
DEPENDENCY_INSTALL_ERROR = -2

selected_model_stylesheet = "border: 2px solid rgb(255, 210, 0); background-color: rgb(255, 221, 64);color: rgb(3, 35, 75);"
unselected_model_stylesheet = "border: transparent; background-color: rgb(39, 44, 54);color: rgb(210,210,210);"

# Workspace folder.
WORKSPACE_PATH = os.path.join(os.path.expanduser('~'), "workspace")

log = logger.get_logger(__name__)

class STAIoTCraftModel(QObject):
    
    sig_model_selected = Signal(str, str)
    sig_acquisition_selected = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.model_name = ""
        self.project_name = ""

    def set_selected_model(self, project_name, model_name):
        self.model_name = model_name
        self.project_name = project_name

    def get_selected_model_name(self):        
        return self.model_name
    
    def get_selected_project_name(self):
        return self.project_name
    
class ModelListItemWidget(QWidget):
    def __init__(self, name, device, component, type, tag_classes, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.name = name
        self.device = device
        self.component = component
        self.type = type
        self.tag_classes = tag_classes
        self.is_model_selected = False
        self.chip_colors = [QColor('#B6CE5F'),
                            QColor('#62C3EB'),
                            QColor('#EB3297'),
                            QColor('#6AC1A4')]

        QPyDesignerCustomWidgetCollection.registerCustomWidget(ModelListItemWidget, module="ModelListItemWidget")
        loader = QUiLoader()
        model_item_widget = loader.load(os.path.join(os.path.dirname(stdatalog_gui.__file__),"UI","model_list_item_widget.ui"), parent)
        self.frame_model:QFrame = model_item_widget.frame_model
        self.frame_model_name = model_item_widget.frame_model.findChild(QFrame,"frame_model_name")
        self.label_model_name = model_item_widget.frame_model.findChild(QPushButton,"label_model_name")
        self.label_model_name.setText(self.name)
        self.label_model_name.clicked.connect(self.model_clicked)
        self.frame_model_components = model_item_widget.findChild(QFrame,"frame_model_components")
        self.model_device_textEdit = self.frame_model_components.findChild(QLineEdit,"model_device_textEdit")
        self.model_component_textEdit = self.frame_model_components.findChild(QLineEdit,"model_component_textEdit")
        self.model_type_textEdit = self.frame_model_components.findChild(QLineEdit,"model_type_textEdit")
        self.frame_model_classes = self.frame_model_components.findChild(QFrame,"frame_model_classes")

        self.model_device_textEdit.setText(self.device)
        self.model_component_textEdit.setText(self.component)
        self.model_type_textEdit.setText(self.type)

        for i, c in enumerate(self.tag_classes):
            tc_chip = QPushButton(c)
            tc_chip.setMinimumWidth(60)
            tc_chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            tc_chip.setStyleSheet(STDTDL_Chip.color(self.chip_colors[i%4]))
            tc_chip.setCheckable(True)
            tc_chip.setEnabled(False)
            tc_chip.setChecked(True)
            self.frame_model_classes.layout().addWidget(tc_chip)
        horizontal_spacer = QWidget()
        horizontal_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.frame_model_classes.layout().addWidget(horizontal_spacer)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(model_item_widget)
        self.shrinked_size = self.sizeHint()

    def model_clicked(self, event):
        self.parent.on_model_item_click(self)

class ProjectListItemWidget(QWidget):
    def __init__(self, staiot_model:STAIoTCraftModel, project, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.project_name = project.ai_project_name
        self.project_desc = project.description
        self.creation_time = project.creation_time
        self.last_update_time = project.last_update_time
        self.models_list = project.models
        self.staiot_model = staiot_model

        QPyDesignerCustomWidgetCollection.registerCustomWidget(ProjectListItemWidget, module="ProjectListItemWidget")
        loader = QUiLoader()
        prj_item_widget = loader.load(os.path.join(os.path.dirname(stdatalog_gui.__file__),"UI","prj_list_item_widget.ui"), parent)
        self.frame_project:QFrame = prj_item_widget.frame_project
        self.frame_prj_name = prj_item_widget.frame_project.findChild(QFrame,"frame_prj_name")
        self.label_prj_name = self.frame_prj_name.findChild(QPushButton,"label_prj_name")
        self.label_prj_name.setText(self.project_name)
        self.frame_prj_components = prj_item_widget.findChild(QFrame,"frame_prj_components")
        self.prj_description_label = self.frame_prj_components.findChild(QLabel,"prj_description_label")
        self.prj_description_label.setText(self.project_desc)
        self.prj_creation_textEdit = self.frame_prj_name.findChild(QLineEdit,"prj_creation_textEdit")
        self.prj_creation_textEdit.setText(str(self.creation_time))
        self.prj_last_updated_textEdit = self.frame_prj_name.findChild(QLineEdit,"prj_last_updated_textEdit")
        self.prj_last_updated_textEdit.setText(str(self.last_update_time))
        self.models_listWidget = prj_item_widget.findChild(QListWidget,"models_listWidget")
        for model in self.models_list:
            item = QListWidgetItem(self.models_listWidget)
            custom_widget = ModelListItemWidget(model.name, model.target.device , model.target.component, model.target.type, model.metadata.classes, self)
            self.models_listWidget.addItem(item)
            self.models_listWidget.setItemWidget(item, custom_widget)
            item.setSizeHint(custom_widget.sizeHint())

        # Calculate the total height required to display all items
        total_height = self.models_listWidget.sizeHintForRow(0) * self.models_listWidget.count() + 2 * self.models_listWidget.frameWidth()
        self.models_listWidget.setFixedHeight(total_height)

        # Connect the itemClicked signal to the on_item_click function
        self.models_listWidget.itemClicked.connect(self.on_model_item_click)

        #Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(prj_item_widget)
        self.shrinked_size = self.sizeHint()

    def update_models_selected_stylesheet(self):
        for i in range(self.models_listWidget.count()):
            item = self.models_listWidget.item(i)
            custom_widget = self.models_listWidget.itemWidget(item)
            if self.staiot_model.get_selected_project_name() != self.project_name:
                custom_widget.frame_model_name.setStyleSheet(unselected_model_stylesheet)
            else:
                if self.staiot_model.get_selected_model_name() != custom_widget.name:
                    custom_widget.frame_model_name.setStyleSheet(unselected_model_stylesheet)
                else:
                    custom_widget.frame_model_name.setStyleSheet(selected_model_stylesheet)

    def on_model_item_click(self, item):
        if isinstance(item, ModelListItemWidget):
            custom_widget = item
            for i in range(self.models_listWidget.count()):
                if self.models_listWidget.itemWidget(self.models_listWidget.item(i)) == custom_widget:
                    item = self.models_listWidget.item(i)
                    self.models_listWidget.setCurrentItem(item)
        else:
            custom_widget = self.models_listWidget.itemWidget(item)

        self.staiot_model.set_selected_model(self.project_name, custom_widget.name)
        self.staiot_model.sig_model_selected.emit(self.project_name, custom_widget.name)
        print(f"Project Selected; {self.project_name}, Model Selected: {custom_widget.name}")

class STDTDL_ExperimentalFeaturesPage():
    def __init__(self, page_widget, controller):
        self.controller = controller
        self.staiot_craft_env_flag = False
        self.selected_acquisitions = []
        self.acquisition_uploaded = {}
        self.staiotcraft_client = None
        self.logged_in = False
        self.staiotcraft_model = STAIoTCraftModel()
        self.staiotcraft_model.sig_model_selected.connect(self.s_model_selected)
        self.staiotcraft_model.sig_acquisition_selected.connect(self.s_acquisition_selected)

        # self.controller.sig_user_login_done.connect(self.s_user_login_cb)
        self.page_widget = page_widget
        self.main_layout = page_widget.findChild(QFrame, "frame_experimental_features")

        # Data Toolkit settings frame
        self.dt_frame_content = page_widget.findChild(QFrame, "dt_frame_content")
        self.dt_frame_content.setEnabled(False)
        self.dt_plugins_folder_button = self.dt_frame_content.findChild(QPushButton, "dt_plugins_folder_button")
        self.dt_plugins_folder_button.clicked.connect(self.select_dt_plugins_folder)
        self.dt_plugin_folder_lineEdit:QLineEdit = self.dt_frame_content.findChild(QLineEdit, "dt_plugins_folder_lineEdit")
        self.dt_enabled_checkBox = page_widget.findChild(QCheckBox, "dt_enabled_checkBox")
        self.dt_enabled_checkBox.toggled.connect(self.dt_enable_button_toggled)
        self.dt_plugin_listWidget = page_widget.findChild(QListWidget, "dt_plugin_listWidget")

        # layout_device_config
        self.acq_upload_main_layout = page_widget.findChild(QFrame, "acq_upload_frame")
        self.acq_upload_frame_content = page_widget.findChild(QFrame, "acq_upload_frame_content")
        self.acq_upload_frame_content.setEnabled(False)
        # self.acq_upload_main_layout.setEnabled(False)
        # self.acq_upload_main_layout.setVisible(False)
        self.acquisition_upload_checkBox = page_widget.findChild(QCheckBox, "upload_acquisition_checkBox")
        self.acquisition_upload_checkBox.toggled.connect(self.acquisition_upload_checkBox_toggled)
        
        self.login_error_label = page_widget.findChild(QLabel, "login_error_label")
        self.login_error_label.setVisible(False)
        self.acq_upload_error_label = page_widget.findChild(QLabel, "acq_upload_error_label")
        self.acq_upload_error_label.setVisible(False)

        self.login_button = page_widget.findChild(QPushButton, "login_button")
        self.login_button.setEnabled(False)
        # self.login_button.clicked.connect(self.show_login_dialog)
        self.login_button.clicked.connect(lambda: asyncio.run(self.show_login_dialog()))

        self.howto_button = page_widget.findChild(QPushButton, "howto_button")
        self.howto_button.clicked.connect(self.open_howto)

        self.groupBox_projects_list = page_widget.findChild(QGroupBox, "groupBox_projects_list")
        self.projects_listWidget:QListWidget = page_widget.findChild(QListWidget, "projects_listWidget")
        # self.projects_listWidget.itemSelectionChanged.connect(self.project_selected)
        self.groupBox_projects_list.setEnabled(False)

        self.groupBox_base_acquisition_selection = page_widget.findChild(QFrame, "groupBox_base_acquisition_selection")
        self.base_acq_folder_button = page_widget.findChild(QPushButton, "base_acq_folder_button")
        self.base_acq_folder_button.clicked.connect(self.select_base_acquisitions_folder)
        self.base_acq_folder_textEdit:QLineEdit = page_widget.findChild(QLineEdit, "base_acq_folder_textEdit")
        self.groupBox_base_acquisition_selection.setEnabled(False)

        self.groupBox_acquisitions_list = page_widget.findChild(QGroupBox, "groupBox_acquisitions_list")
        self.acquisitions_listWidget:QListWidget = page_widget.findChild(QListWidget, "acquisitions_listWidget")
        
        # self.acquisitions_listWidget.itemSelectionChanged.connect(self.acquisition_selected)
        # Connect the itemClicked signal to the on_item_click function
        self.acquisitions_listWidget.itemClicked.connect(self.acquisition_selected)
        
        self.groupBox_acquisitions_list.setEnabled(False)

        self.groupBox_upload_settings = page_widget.findChild(QGroupBox, "groupBox_upload_settings")
        self.upload_acquisition_button = page_widget.findChild(QPushButton, "upload_acquisition_button")
        # self.upload_acquisition_button.clicked.connect(self.upload_acquisitions)
        self.upload_acquisition_button.clicked.connect(lambda: asyncio.run(self.upload_acquisitions()))
        self.groupBox_upload_settings.setEnabled(False)

    def check_dependencies(self):       
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
                loading_dialog = StaticLoadingWindow("Installing required packages...", "staiotcraft_sdk package is mandatory to use the ST AIoT Craft Acquisitions upload feature.\nPlease wait while the package is being installed...", self.page_widget)
                self.controller.qt_app.processEvents()
                log.warning("The following required packages are missing:")
                log.warning(f" - (staiotcraft_sdk) staiotcraft_sdk")
                log.info("This package is required to use the ST AIoT Craft Acquisitions upload feature and will be now installed.")

                #TODO check python version and install the correct whl
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
                else:
                    log.error(f"Unsupported Python version: {python_version}")
                    if loading_dialog.dialog.isVisible():
                        loading_dialog.loadingDone()
                    return PYTHON_VERSION_ERROR

                subprocess.check_call([sys.executable, "-m", "pip", "install", oidc_client_whl_path])
                subprocess.check_call([sys.executable, "-m", "pip", "install", vespucci_python_utils_whl_path])
                subprocess.check_call([sys.executable, "-m", "pip", "install", dataset_models_whl_path])
                subprocess.check_call([sys.executable, "-m", "pip", "install", dataset_api_client_whl_path])
                subprocess.check_call([sys.executable, "-m", "pip", "install", staiotcraft_sdk_whl_path])
                loading_dialog.loadingDone()

            except Exception as e:
                log.error(f"Failed to install the required package: {required_package}")
                log.error(f"Error: {e}")
                if loading_dialog.dialog.isVisible():
                    loading_dialog.loadingDone()
                return DEPENDENCY_INSTALL_ERROR
        else:
            log.info("All required packages are installed.")

        return DEPENDENCY_OK
    
    def select_dt_plugins_folder(self):
        self.controller.remove_dt_plugins_folder()
        # Open a dialog to select a directory
        folder_path = QFileDialog.getExistingDirectory(None, 'Select Folder')
        if folder_path:
            self.dt_plugin_listWidget.clear()
            self.dt_plugin_folder_lineEdit.setText(folder_path)
            self.controller.set_dt_plugins_folder(folder_path)
            # List all .py files in the specified data toolkit plugins directory
            files = os.listdir(folder_path)
            py_files = [f for f in files if os.path.isfile(os.path.join(folder_path, f)) and f.endswith('.py') and f != "__init__.py"]
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
        self.dt_frame_content.setEnabled(status)
        if status:
            if self.dt_plugin_folder_lineEdit.text() != "":
                self.controller.set_dt_plugins_folder(self.dt_plugin_folder_lineEdit.text())
                self.controller.create_data_pipeline()
        else:
            self.controller.set_dt_plugins_folder(None)
            self.controller.destroy_data_pipeline()

    def acquisition_upload_checkBox_toggled(self, status):
        if status:
            res = self.check_dependencies()
            if res == PYTHON_VERSION_ERROR:
                self.acquisition_upload_checkBox.setChecked(False)
                self.login_error_label.setText("--> [ERROR] - Currently only Python 3.11 is supported.")
                self.login_error_label.setVisible(True)
                self.login_button.setEnabled(False)
                pass
            elif res == DEPENDENCY_INSTALL_ERROR:
                self.acquisition_upload_checkBox.setChecked(False)
                self.login_error_label.setText("--> [ERROR] Failed to install required packages.")
                self.login_error_label.setVisible(True)
                self.login_button.setEnabled(False)
            else:
                self.login_button.setEnabled(True)
        self.acq_upload_frame_content.setEnabled(status)
        self.login_error_label.setVisible(False)

    def open_howto(self):
        """
        Show the application information dialog.
        """
        loader = QUiLoader() # Create a QUiLoader instance
        howto_dialog = loader.load(os.path.join(os.path.dirname(stdatalog_gui.__file__),"UI","staiotcraft_howto_dialog.ui"), self.page_widget) # Load the info dialog UI
        howto_dialog.exec() # Execute the info dialog

    async def show_login_dialog(self):
        if not self.logged_in:
            login_loading_dialog = StaticLoadingWindow("ST AIoT Craft Login", "Logging in to the ST AIoT Craft platform...\nPlease fill the login form opened in yout browser with your ST account credentials.\nIf you don't have an account, please create one.", self.page_widget)
            self.controller.qt_app.processEvents()
            self.groupBox_base_acquisition_selection.setEnabled(True)
            
            staiotcraft_module = importlib.import_module('staiotcraft_sdk.staiotcraft_client')
            STAIoTCraftClient = getattr(staiotcraft_module,"STAIoTCraftClient")
            self.staiotcraft_client = STAIoTCraftClient.get_desktop_client(
                workspace_folder = WORKSPACE_PATH
            )
            # Getting user's projects.
            print('Getting user\'s projects...')
            projects = await self.staiotcraft_client.get_projects()
            if not projects:
                if login_loading_dialog.dialog.isVisible():
                    login_loading_dialog.loadingDone()
                    self.logged_in = False
                    self.login_button.setText("Login")
                    self.login_button.setStyleSheet(STDTDL_PushButton.green)
                raise Exception('No projects available for the user.')
            else:
                if len(projects) > 0:
                    self.groupBox_projects_list.setEnabled(True)
                    self.projects_listWidget.clear()
                for project in projects:
                    print('- {}'.format(project.short_repr()))
                    item = QListWidgetItem(self.projects_listWidget)
                    custom_widget = ProjectListItemWidget(self.staiotcraft_model, project, self.projects_listWidget)
                    self.projects_listWidget.addItem(item)
                    self.projects_listWidget.setItemWidget(item, custom_widget)
                    item.setSizeHint(custom_widget.sizeHint())
                
                if login_loading_dialog.dialog.isVisible():
                    login_loading_dialog.loadingDone()

                self.logged_in = True
                self.login_button.setText("Logout")
                self.login_button.setStyleSheet(STDTDL_PushButton.red)
        else:
            self.staiotcraft_client = None
            self.projects_listWidget.clear()
            self.acquisitions_listWidget.clear()
            self.logged_in = False
            self.selected_acquisitions = []
            self.acquisition_uploaded = {}
            self.login_button.setText("Login")
            self.login_button.setStyleSheet(STDTDL_PushButton.green)
            self.acq_upload_error_label.setText("")
            self.acq_upload_error_label.setVisible(False)
            self.upload_acquisition_button.setText("Upload Acquisitions")
            self.upload_acquisition_button.setIcon(QIcon(cloud_upload_path))
            self.groupBox_upload_settings.setEnabled(False)
    
    def s_model_selected(self, project_name, model_name):
        for i in range(self.projects_listWidget.count()):
            item = self.projects_listWidget.item(i)
            custom_widget = self.projects_listWidget.itemWidget(item)
            custom_widget.update_models_selected_stylesheet()
        if self.upload_acquisition_button.text() == "Acquisitions Uploaded":
            self.upload_acquisition_button.setText("Upload Acquisitions")
            self.upload_acquisition_button.setIcon(QIcon(cloud_upload_path))
            self.acq_upload_error_label.setVisible(False)
        if self.selected_acquisitions != []:
            self.groupBox_upload_settings.setEnabled(True)
        else:
            self.groupBox_upload_settings.setEnabled(False)

    def s_acquisition_selected(self, acq_folder_path):
        for i in range(self.acquisitions_listWidget.count()):
            item = self.acquisitions_listWidget.item(i)
            custom_widget = self.acquisitions_listWidget.itemWidget(item)
            if custom_widget.acq_folder_path == acq_folder_path:
                custom_widget.update_acquisition_selected_stylesheet()
        
        if len(self.selected_acquisitions) == 0:
            self.groupBox_upload_settings.setEnabled(False)
        else:
            if self.staiotcraft_model.get_selected_model_name() != "" and self.staiotcraft_model.get_selected_project_name() != "":
                self.groupBox_upload_settings.setEnabled(True)
            else:
                self.groupBox_upload_settings.setEnabled(False)

    def select_base_acquisitions_folder(self):
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
                hsd_version = HSDatalog.validate_hsd_folder(os.path.join(folder_path, folder))
                if hsd_version != HSDatalog.HSDVersion.INVALID:
                    item = QListWidgetItem(self.acquisitions_listWidget)
                    custom_widget = AcqListItemWidget(self.controller, hsd_version, folder_path, folder, item, self.acquisition_selected, self.acquisitions_listWidget)
                    self.acquisitions_listWidget.addItem(item)
                    self.acquisitions_listWidget.setItemWidget(item, custom_widget)
                    item.setSizeHint(custom_widget.sizeHint())
                else:
                    log.warning(f"Acquisition {folder}")

    async def upload_acquisitions(self):
        loading_dialog = StaticLoadingWindow("Uploading Acquisitions", "Please wait while the acquisitions are being uploaded to the ST AIoT Craft platform...", self.page_widget)
        self.controller.qt_app.processEvents()
        
        # Configuring AI.
        print('Configuring AI...')
        loading_dialog.message_label.setText("Configuring AI...")
        self.controller.qt_app.processEvents()
        await self.staiotcraft_client.configure_ai(
            model_name = self.staiotcraft_model.get_selected_model_name(),
            project_name = self.staiotcraft_model.get_selected_project_name()
        )
        print('Uploading selected local acquisitions...')
        loading_dialog.message_label.setText("Uploading selected local acquisitions...")
        self.controller.qt_app.processEvents()
        # Uploading a selected local acquisition.
        for acq_path in self.selected_acquisitions:
            acq_upload_msg = 'Uploading acquisition: {}'.format(acq_path)
            print(acq_upload_msg)
            loading_dialog.message_label.setText(acq_upload_msg)
            self.controller.qt_app.processEvents()
            try:
                await self.staiotcraft_client.upload_acquisition(acq_path, os.path.basename(acq_path), exists_ok = False)
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
        if isinstance(item, AcqListItemWidget):
            custom_widget = item
            for i in range(self.acquisitions_listWidget.count()):
                if self.acquisitions_listWidget.itemWidget(self.acquisitions_listWidget.item(i)) == custom_widget:
                    item = self.acquisitions_listWidget.item(i)
                    self.acquisitions_listWidget.setCurrentItem(item)
        else:
            custom_widget = self.acquisitions_listWidget.itemWidget(item)

        if custom_widget.acq_folder_path not in self.selected_acquisitions:
            self.selected_acquisitions.append(custom_widget.acq_folder_path)
        else:
            self.selected_acquisitions.remove(custom_widget.acq_folder_path)
        self.staiotcraft_model.sig_acquisition_selected.emit(custom_widget.acq_folder_path)
        if self.upload_acquisition_button.text() == "Acquisitions Uploaded":
            self.upload_acquisition_button.setText("Upload Acquisitions")
            self.upload_acquisition_button.setIcon(QIcon(cloud_upload_path))
            self.acq_upload_error_label.setVisible(False)