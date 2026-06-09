#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    PluginListItemWidget.py
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
Plugin list item widget used in the plugins browser.

This module defines `PluginListItemWidget`, a compact Qt widget rendering a single
plugin row inside a list-like container. It displays the plugin name and optional
notes, and forwards click interactions so that the parent view can select/focus the
corresponding item.

Responsibilities:
- Render plugin name and notes as defined by the loaded UI.
- Capture clicks on the plugin name and notify the parent container to select the
    associated list item.

Design Notes:
- The layout is loaded at runtime from `plugin_list_item_widget.ui` using `QUiLoader`.
- This file adds documentation and 100-character wrapping only; behavior is unchanged.
"""

import os

from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFrame,
)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

import stdatalog_gui

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class PluginListItemWidget(QWidget):
    """A single, clickable list item representing a plugin entry.

    Parameters
    ----------
    plugin_name : str
        Display name of the plugin to show in the row.
    plugin_item : Any
        The list item object associated with this widget (e.g., a QListWidgetItem or
        similar item) used by the parent to set the current selection.
    parent : QWidget | None, optional
        Parent widget. The parent is expected to expose a `setCurrentItem(item)`
        method to update the current selection when the plugin name is clicked.

    Attributes
    ----------
    item : Any
        Reference to the associated list item.
    plugin_name : str
        The plugin display name bound to the row.
    frame_plugin_name : QFrame
        Frame that contains the name/notes UI.
    label_plugin_name : QPushButton
        Clickable control displaying the plugin name and triggering selection.
    label_plugin_notes : QLabel
        Optional notes/description shown under or next to the name, if present.
    shrinked_size : QSize
        Cached size hint after initial layout useful for list sizing.
    """

    def __init__(self, plugin_name, plugin_item, parent=None):

        super().__init__(parent)
        self.parent = parent

        self.item = plugin_item
        self.plugin_name = plugin_name
        self.setWindowTitle(plugin_name)

        QPyDesignerCustomWidgetCollection.registerCustomWidget(
            PluginListItemWidget, module="PluginListItemWidget"
        )
        loader = QUiLoader()
        plugin_item_widget = loader.load(
            os.path.join(
                os.path.dirname(stdatalog_gui.__file__),
                "UI",
                "plugin_list_item_widget.ui",
            ),
            parent,
        )
        # self.frame_plugin:QFrame = plugin_item_widget.frame_acquisition
        self.frame_plugin_name = plugin_item_widget.findChild(QFrame, "frame_plugin_name")
        self.label_plugin_name = self.frame_plugin_name.findChild(
            QPushButton, "label_plugin_name"
        )
        self.label_plugin_name.setText(self.plugin_name)
        self.label_plugin_name.clicked.connect(self.clicked_plugin_name)
        self.label_plugin_notes = self.frame_plugin_name.findChild(
            QLabel, "label_plugin_notes"
        )

        #Main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        main_layout.addWidget(plugin_item_widget)
        self.shrinked_size = self.sizeHint()

    def clicked_plugin_name(self):
        """Handle clicks on the plugin name and notify parent for selection.

        Notes
        -----
        This method expects that the parent widget implements a
        ``setCurrentItem(item)`` method to select/focus the corresponding row.
        """
        self.parent.setCurrentItem(self.item)
