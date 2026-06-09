#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    AcqListItemWidget.py
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
"""Acquisition list item widget for the ST DTDL GUI.

This module implements a clickable list item representing a single local acquisition folder.
It displays the acquisition name and, when expanded, shows chips for detected components
within the acquisition (e.g., sensors), including their enable state. The widget toggles
selection styles and calls back to the parent when selected.

Responsibilities:
- Load the Qt Designer UI for the acquisition item.
- Display acquisition metadata and component chips with consistent styles.
- Toggle expansion on click and update the parent list item's size hint.
- Maintain selection state and apply selected/unselected styles.

Design Notes:
- Uses `QUiLoader` to load the `.ui` file at runtime.
- Relies on `HSDatalog` helpers to enumerate sensors detected in the folder.
- Follows the project's Parameters/Returns docstring style and 100-character line wrap.
"""

import os
from functools import partial

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget, QFrame
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui

from stdatalog_gui.UI.styles import STDTDL_Chip
from stdatalog_core.HSD.HSDatalog import HSDatalog
import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

selected_acquisition_stylesheet = (
    "border: 2px solid rgb(255, 210, 0); background-color: rgb(255, 221, 64);"
    "color: rgb(3, 35, 75);"
)
unselected_acquisition_stylesheet = (
    "border: transparent; background-color: rgb(39, 44, 54);"
    "color: rgb(210,210,210);"
)
class AcqListItemWidget(QWidget):
    """List item widget representing a local acquisition.

    Parameters:
    - staiot_model: Model/controller used to coordinate selection callbacks.
    - hsd_version: HSD version enum for the acquisition folder (V1/V2).
    - folder_path (str): Path to the base acquisitions folder.
    - acq_name (str): Acquisition folder name.
    - item (QListWidgetItem): Backing list item instance.
    - acquisition_selected_cb (Callable): Callback invoked when the item is selected.
    - parent (QWidget | None): Optional parent widget.

    Attributes:
    - acq_folder_path (str): Full path to the acquisition folder.
    - is_selected (bool): Whether the item is currently selected.
    - is_expanded (bool): Whether components are visible.
    - hsd (HSDatalog | None): HSD object instantiated lazily.
    - components (list | None): Components enumerated for the acquisition.
    - chip_colors (list[QColor]): Color palette for component chips.
    """
    def __init__(
        self,
        staiot_model,
        hsd_version,
        folder_path,
        acq_name,
        item,
        acquisition_selected_cb,
        parent=None,
    ):

        super().__init__(parent)
        self.parent = parent
        self.staiot_model = staiot_model
        self.acquisition_selected_cb = acquisition_selected_cb

        self.folder_path = folder_path
        self.acq_name = acq_name
        self.acq_folder_path = os.path.join(folder_path, acq_name)
        self.item = item
        self.is_selected = False
        self.is_expanded = False

        self.setWindowTitle(acq_name)

        self.chip_colors = [QColor('#B6CE5F'),
                            QColor('#62C3EB'),
                            QColor('#EB3297'),
                            QColor('#6AC1A4')]

        self.hsd_factory = HSDatalog()
        self.hsd = None
        self.components = None

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            AcqListItemWidget, module="AcqListItemWidget"
        )
        loader = QUiLoader()
        acq_item_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "acq_list_item_widget.ui",
            ),
            parent,
        )
        self.frame_acquisition:QFrame = acq_item_widget.frame_acquisition
        self.frame_acq_name = acq_item_widget.frame_acquisition.findChild(QFrame,"frame_acq_name")
        self.label_acq_name = self.frame_acq_name.findChild(QPushButton,"label_acq_name")
        self.label_acq_name.setText(self.acq_name)
        self.label_acq_name.clicked.connect(self.on_act_title_clicked)
        self.label_acq_notes = self.frame_acq_name.findChild(QLabel,"label_acq_notes")
        if hsd_version == HSDatalog.HSDVersion.V1:
            self.label_acq_notes.setText("HSDv1")
        elif hsd_version == HSDatalog.HSDVersion.V2:
            self.label_acq_notes.setText("HSDv2")
        self.frame_acq_components = acq_item_widget.frame_acquisition.findChild(
            QFrame,
            "frame_acq_components",
        )
        self.frame_acq_components.setVisible(self.is_expanded)

        #Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(acq_item_widget)
        self.shrinked_size = self.sizeHint()

    def on_act_title_clicked(self):
        """Forward title click to the acquisition-selected callback.

        Parameters:
        - None

        Returns:
        - None
        """
        self.acquisition_selected_cb(self)

    def clicked_acq_title(self):
        """Toggle expansion and lazily build component chips if needed.

        Parameters:
        - None

        Returns:
        - None
        """
        # self.parent.setCurrentItem(self.item)
        # self.item.setSizeHint(self.sizeHint())
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            if self.hsd is None:
                print(f"Creating HSD object for {self.acq_folder_path}")
                self.hsd= self.hsd_factory.create_hsd(self.acq_folder_path)
                # print(HSDatalog.present_sensor_list(self.hsd))
                print("Getting sensor list")
                self.components = HSDatalog.get_sensor_list(self.hsd)
                print(self.components)
                for i, c in enumerate(self.components):
                    s_chip = QPushButton(list(c.keys())[0])
                    s_chip.setStyleSheet(
                        STDTDL_Chip.color(self.chip_colors[i % len(self.chip_colors)])
                    )
                    s_chip.setCheckable(True)
                    s_chip.setEnabled(False)
                    s_chip.setChecked(c[list(c.keys())[0]]["enable"])
                    s_chip.clicked.connect(partial(self.component_chip_checked, s_chip, c))
                    row = i // 3
                    col = i % 3
                    self.frame_acq_components.layout().addWidget(s_chip, row, col)

            self.frame_acq_components.setVisible(True)
            # Update the size hint of the item
            self.item.setSizeHint(self.sizeHint())
        else:
            self.frame_acq_components.setVisible(False)
            # Update the size hint of the item
            self.item.setSizeHint(self.shrinked_size)

    def update_acquisition_selected_stylesheet(self):
        """Toggle selection style and expand/collapse accordingly.

        Parameters:
        - None

        Returns:
        - None
        """
        self.clicked_acq_title()
        if self.is_selected:
            #to be unselected
            self.frame_acq_name.setStyleSheet(unselected_acquisition_stylesheet)
        else:
            #to be selected
            self.frame_acq_name.setStyleSheet(selected_acquisition_stylesheet)
        self.is_selected = not self.is_selected
    def component_chip_checked(self, comp_chip:QPushButton, comp_name):
        """Handle clicks on component chips (currently a placeholder).

        Parameters:
        - comp_chip (QPushButton): The clicked chip button.
        - comp_name (dict): Component metadata for the clicked chip.

        Returns:
        - None
        """
