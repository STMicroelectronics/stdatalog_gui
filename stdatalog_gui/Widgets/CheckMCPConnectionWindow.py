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

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QPushButton, QApplication, QSpacerItem, QSizePolicy
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtCore import Qt, QTimer

from stdatalog_gui.UI.styles import STDTDL_PushButton

class CheckMCPConnectionWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Connection Error")
        self.setStyleSheet("background-color:  #292d38; color: #FFFFFF;")
        self.setFixedSize(580, 600)  # Set fixed size to 550x500

        # Remove the close button from the dialog
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        # Set the dialog to be application modal
        self.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)  # Add margins: left, top, right, bottom

        # Title Label
        title_label = QLabel("Unable to establish connection with motor control board")
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
            "HSD_MC_GUI\\UI\\images\\mcp_error_connection.png",
            "HSD_MC_GUI\\UI\\images\\mcp_error_connection_2.png",
            "HSD_MC_GUI\\UI\\images\\mcp_error_connection_1.png",
            "HSD_MC_GUI\\UI\\images\\mcp_error_connection_2.png"
        ]
        self.current_image_index = 0

        # Timer to change images
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.change_image)
        self.timer.start(2000)  # Change image every 2 seconds

        self.change_image()  # Set the initial image

    def change_image(self):
        pixmap = QPixmap(self.images[self.current_image_index])
        scaled_pixmap = pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self.current_image_index = (self.current_image_index + 1) % len(self.images)

    def close_dialog(self):
        self.close()
        QApplication.quit()