# ******************************************************************************
#  * @file    HSDMLCConfigurationWidget.py
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
Machine Learning Core (MLC) configuration widget for HSD GUI.

This module provides `HSDMCLConfigurationWidget`, a lightweight configuration panel used
to enable/disable an MLC component from the GUI. It validates that a valid UCF has been
uploaded before allowing the user to enable the MLC, and surfaces a styled warning dialog
otherwise. It also logs a warning through the application logger.

Highlights
----------
- Binds to the base `ComponentWidget` property widgets (e.g., `enable`, `ucf_status`).
- Prevents accidental enabling of MLC without a loaded UCF file.
- Shows a themed `QMessageBox` explaining the required action.
"""
from stdatalog_gui.UI.styles import STDTDL_PushButton
from stdatalog_gui.Widgets.ComponentWidget import ComponentWidget
from PySide6.QtWidgets import QMessageBox

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class HSDMCLConfigurationWidget(ComponentWidget):
    """
    Configuration widget for enabling an MLC component safely.

    Parameters
    ----------
    controller : object
        Application controller that provides the Qt app instance and component state.
    comp_name : str
        Component name used as identifier.
    comp_display_name : str
        Human-friendly name used for the widget title.
    comp_sem_type : str
        Semantic type string used by the base `ComponentWidget`.
    comp_contents : list
        List of component content descriptors.
    c_id : int, optional
        Component id used by the base widget, by default 0.
    parent : QWidget | None, optional
        Parent widget, by default `None`.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        comp_sem_type,
        comp_contents,
        c_id=0,
        parent=None,
    ):
        super().__init__(
            controller,
            comp_name,
            comp_display_name,
            comp_sem_type,
            comp_contents,
            c_id,
            parent,
        )

        self.app = self.controller.qt_app
        self.is_logging = False
        self.parent_widget = parent
        self.comp_sem_type = comp_sem_type

        self.property_widgets["enable"].value.toggled.connect(self.enable_mlc_clicked)

    def enable_mlc_clicked(self, status):
        """
        Validate UCF presence before enabling the MLC component.

        Parameters
        ----------
        status : bool
            Desired enable state from the UI toggle. When `True` and no valid UCF is
            loaded (`ucf_status` is unchecked), a warning dialog is shown and the
            operation is blocked.
        """
        if status and not self.property_widgets["ucf_status"].value.isChecked():
            # create a QMessageBox object
            msg_box = QMessageBox()
            # set message box window title
            msg_box.setWindowTitle("Error enabling MLC")
            # set the icon
            msg_box.setIcon(QMessageBox.Warning)
            # set the message text
            msg_box.setText(
                "Please, upload a valid UCF file before enabling this MLC component."
            )
            # set the stylesheet
            msg_box.setStyleSheet(
                "QMessageBox { background-color: rgb(27, 29, 35); } "
                "QLabel { color: rgb(210,210,210); } "
                f"{STDTDL_PushButton.valid}"
            )
            # show the message box
            msg_box.exec()
            log.warning("Please, upload a valid UCF file before enabling this MLC component!")
