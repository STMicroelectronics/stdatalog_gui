#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    LoadingWindow.py
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
"""Loading and waiting dialog utilities for the ST DTDL GUI.

This module provides small, themed dialogs used to inform users about ongoing operations:
- ``StaticLoadingWindow``: modal dialog displaying static text while work proceeds.
- ``LoadingWindow``: indeterminate progress dialog for longer operations.
- ``WaitingDialog``: dialog with an animated loading icon and message.

Design Notes
------------
- Built with PySide6; uses reusable, consistent styling across dialogs.
- Uses 100-character wrapping for readability and consistency.
- No behavioral changes; only documentation and stylistic consistency.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressDialog
from PySide6.QtGui import QMovie
from PySide6.QtCore import Qt, QSize

import stdatalog_gui.UI.images
from pkg_resources import resource_filename
loading_gif_path = resource_filename('stdatalog_gui.UI.images', 'loading_icon.gif')

class StaticLoadingWindow:
    """Modal, non-closable dialog with a static message.

    Parameters
    ----------
    title : str
        Window title.
    text : str
        Message shown to the user.
    parent : QWidget
        Parent widget used to position and modality-scope the dialog.

    Attributes
    ----------
    dialog : QDialog
        The underlying dialog instance.
    message_label : QLabel
        Label displaying the message.
    """

    def __init__(self, title, text, parent) -> None:
        self.dialog = QDialog(parent)

        layout = QVBoxLayout()
        self.message_label = QLabel(text)
        layout.addWidget(self.message_label)
        self.dialog.setLayout(layout)
        self.dialog.setContentsMargins(24,24,24,24)

        self.dialog.setWindowTitle(title)
        self.dialog.setModal(True)
        # Remove the X button by customizing window flags
        self.dialog.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        style = '''
            QDialog
            {
                background-color: rgb(41, 45, 56);
            }
        '''

        self.dialog.setStyleSheet(style)
        self.dialog.show()

    def loadingDone(self):
        """Close the dialog when the loading operation completes.

        Returns
        -------
        None
        """
        self.dialog.close()

class LoadingWindow:
    """Indeterminate progress dialog with consistent styling.

    Parameters
    ----------
    title : str
        Window title.
    text : str
        Message shown above the progress indicator.
    parent : QWidget
        Parent widget.
    """

    def __init__(self, title, text, parent) -> None:
        self.dialog = QProgressDialog(parent)
        self.dialog.setContentsMargins(24,24,24,24)
        self.dialog.setMinimum(0)
        self.dialog.setMaximum(0)
        self.dialog.setLabelText(text)
        self.dialog.setWindowTitle(title)
        self.dialog.setCancelButton(None)
        self.dialog.setModal(True)
        style = '''
            QProgressDialog
            {
                background-color: rgb(41, 45, 56);
            }
        '''

        self.dialog.setStyleSheet(style)
        self.dialog.show()

    def loadingDone(self):
        """Close the dialog when the loading operation completes.

        Returns
        -------
        None
        """
        self.dialog.close()

class WaitingDialog(QDialog):
    """Dialog showing a centered loading animation and message.

    Parameters
    ----------
    title : str
        Window title.
    text : str
        Message shown to the user.
    parent : QWidget | None, optional
        Optional parent widget.
    """

    def __init__(self, title, text, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setWindowTitle(title)
        self.setModal(True)
        self.setStyleSheet(
            "background-color: rgb(44, 49, 60); color: rgb(210, 210, 210);"
        )
        layout = QVBoxLayout()
        self.message_label = QLabel(text)
        layout.addWidget(self.message_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(24)
        layout.setContentsMargins(24, 24, 24, 24)
        self.movie_label = QLabel(text)
        self.movie = QMovie(loading_gif_path)
        self.movie.setScaledSize(QSize(64,64))
        self.movie_label.setMovie(self.movie)
        layout.addWidget(self.movie_label, alignment=Qt.AlignmentFlag.AlignCenter)
        self.setLayout(layout)
        self.adjustSize()

    def start(self):
        """Show the dialog and start the loading animation.

        Returns
        -------
        None
        """
        self.movie.start()
        self.show()

    def stop(self):
        """Stop the loading animation and close the dialog.

        Returns
        -------
        None
        """
        self.movie.stop()
        self.close()
