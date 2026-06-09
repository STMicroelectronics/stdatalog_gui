#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    AboutDialog.py
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
"""About dialog for ST DTDL GUI applications.

Provides a simple, themed dialog showing application title, credits, and version.
The dialog UI is loaded from a `.ui` file and wired to dynamic values at runtime.

Responsibilities:
- Load the Qt Designer UI for the about dialog.
- Populate labels with app metadata (title, credits, version).
- Apply consistent styling and margins.

Design Notes:
- Uses `QUiLoader` to load the UI at runtime; avoids behavior changes.
- Follows the project's Parameters/Returns docstring style and 100-character wrap.
"""

import os

from PySide6.QtWidgets import QDialog, QVBoxLayout, QWidget, QLabel
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui

class AboutDialog(QDialog):
    """Modal about dialog presenting app information.

    Parameters:
    - controller: Application controller reference (for future use/consistency).
    - app_title (str): Application title to display.
    - app_credits (str): Credits or copyright text.
    - app_version (str): Version string.
    - parent (QWidget | None): Optional parent widget.

    Attributes:
    - controller: Stored reference to the app controller.
    """
    def __init__(self, controller, app_title, app_credits, app_version, parent=None):
        """Initialize the dialog, load UI, and populate fields.

        Parameters:
        - controller: Application controller reference.
        - app_title (str): Title to show in the dialog.
        - app_credits (str): Credits/copyright string.
        - app_version (str): Version string.
        - parent (QWidget | None): Optional parent widget.

        Returns:
        - None
        """
        super().__init__(parent)
        self.controller = controller

        self.setWindowTitle("About")

        QPyDesignerCustomWidgetCollection.registerCustomWidget(AboutDialog, module="AboutDialog")
        loader = QUiLoader()
        about_dialog = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "about_dialog.ui",
            ),
            parent,
        )
        main_dialog_widget = about_dialog.findChild(QWidget,"main_dialog_widget")

        about_dialog_title = about_dialog.findChild(QLabel, "about_dialog_title")
        about_dialog_title.setText(app_title)
        label_credits = about_dialog.findChild(QLabel, "label_credits")
        label_credits.setText(app_credits)
        label_version = about_dialog.findChild(QLabel, "label_version")
        label_version.setText(app_version)

        #Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_dialog_widget.setStyleSheet(
            "background-color: rgb(44, 49, 60); color: rgb(210, 210, 210);"
        )
        self.setLayout(main_layout)
        main_layout.addWidget(main_dialog_widget)
