#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_CheckMCPConnectionWindow.py
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
Modal dialog that guides users when the Motor Control board is unreachable.

This module provides a simple, application-modal ``QDialog`` that is shown when the
application cannot establish a connection with the Motor Control (MC) board. The dialog
displays a sequence of instructional images and short checklists to help users verify
their setup. It is intentionally simple: it disables the window close button, shows a
Close action to quit the application, and cycles through a few images using a ``QTimer``.

Highlights
----------
- Uses an application-modal dialog to keep focus until the user acknowledges it.
- Cycles through static images (e.g., wiring guidance, reminders) every 2 seconds.
- Provides a "Close" button that closes the dialog and exits the application.

Notes
-----
- The dialog does not perform active re-connection attempts; it only communicates the
    error and suggests remediation steps.
- Image paths are resolved as relative paths within the repository tree and are expected
    to be available at runtime. No I/O validation is performed here.
"""

from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QSpacerItem,
    QSizePolicy,
)
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtCore import Qt, QTimer

from stdatalog_gui.UI.styles import STDTDL_PushButton

class HSD_MC_CheckMCPConnectionWindow(QDialog):
    """Dialog that explains connection failures to the MC board.

    The dialog is application-modal and disables the standard window close button to
    encourage users to read the instructions. An internal timer rotates images that
    illustrate the recommended checks.

    Parameters
    ----------
    parent : QWidget | None, optional
        Parent widget. Default is ``None``.

    Attributes
    ----------
    images : list[str]
        Paths to images displayed in a loop.
    current_image_index : int
        Index of the currently shown image within ``images``.
    timer : QTimer
        Timer that triggers image changes at a fixed cadence.
    image_label : QLabel
        The label that renders the current image.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Connection Error")
        self.setStyleSheet("background-color:  #292d38; color: #FFFFFF;")
        self.setFixedSize(580, 600)  # Fixed dialog size

        # Remove the close button from the dialog
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        # Set the dialog to be application modal
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Margins: left, top, right, bottom

        # Title Label
        title_label = QLabel(
            "Unable to establish connection with motor control board"
        )
        title_label.setFont(QFont("", 14, QFont.Bold))
        title_label.setStyleSheet("color: #e6007e; font-weight: bold;")
        layout.addWidget(title_label, alignment=Qt.AlignCenter)

        # Image Container
        image_container = QWidget()
        image_container.setFixedSize(450, 300)
        image_layout = QVBoxLayout()
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.image_label)
        image_container.setLayout(image_layout)
        layout.addWidget(image_container, alignment=Qt.AlignCenter)

        # Spacer Item
        spacer = QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        layout.addItem(spacer)

        # Instruction Label
        instruction_label = QLabel(
            "Please ensure the following:\n"
            "- Powerup all the control and power motor board.\n"
            "- Properly connect the controller and motor target board."
        )
        instruction_label.setFont(QFont("", 12))
        layout.addWidget(instruction_label, alignment=Qt.AlignLeft)

        # Add Spacer Item to layout
        layout.addItem(spacer)

        # Reset Instruction Label
        reset_label = QLabel(
            "Reset the MCP Control board and launch the application again."
        )
        reset_label.setFont(QFont("", 12))
        layout.addWidget(reset_label, alignment=Qt.AlignLeft)

        # Add Spacer Item to layout
        layout.addItem(spacer)

        # Close Button
        close_button = QPushButton("Close")
        close_button.setFont(QFont("", 10))
        close_button.setMinimumSize(100, 50)
        close_button.setStyleSheet(STDTDL_PushButton.green)
        close_button.clicked.connect(self.close_dialog)
        layout.addWidget(close_button, alignment=Qt.AlignCenter)

        self.setLayout(layout)

        # List of images
        self.images = [
            "stdatalog_gui\\HSD_MC_GUI\\UI\\images\\mcp_error_connection.png",
            "stdatalog_gui\\HSD_MC_GUI\\UI\\images\\mcp_error_connection_2.png",
            "stdatalog_gui\\HSD_MC_GUI\\UI\\images\\mcp_error_connection_1.png",
            "stdatalog_gui\\HSD_MC_GUI\\UI\\images\\mcp_error_connection_2.png"
        ]
        self.current_image_index = 0

        # Timer to change images
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.change_image)
        self.timer.start(2000)  # Change image every 2 seconds

        self.change_image()  # Set the initial image

    def change_image(self):
        """Advance to the next image and update the label.

        The method scales the current image to fit within a 400x300 area while keeping
        the aspect ratio and using a smooth transformation. It then updates the label and
        advances the internal index.

        Returns
        -------
        None
        """
        pixmap = QPixmap(self.images[self.current_image_index])
        scaled_pixmap = pixmap.scaled(
            400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.current_image_index = (self.current_image_index + 1) % len(self.images)

    def close_dialog(self):
        """Close the dialog and exit the application.

        This slot is connected to the "Close" button. It closes the dialog and then
        requests the application to quit.

        Returns
        -------
        None
        """
        self.close()
        QApplication.quit()
