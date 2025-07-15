
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

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressDialog
from PySide6.QtGui import QMovie
from PySide6.QtCore import Qt, QSize

import stdatalog_gui.UI.images
from pkg_resources import resource_filename
loading_gif_path = resource_filename('stdatalog_gui.UI.images', 'loading_icon.gif')

class StaticLoadingWindow():
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
            Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint
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
        self.dialog.close()

class LoadingWindow:
    
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
        self.dialog.close()

class WaitingDialog(QDialog):
    def __init__(self, title, text, parent=None):
        """
        Constructor for the WaitingDialog class.
        This class is a custom QDialog that is used to display a waiting dialog to the user when the application is processing some data.
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint) # Set the window flags
        self.setWindowTitle(title) # Set the window title
        self.setModal(True) # Set the dialog to be modal
        # Set the background color using setStyleSheet
        self.setStyleSheet("background-color: rgb(44, 49, 60); color: rgb(210, 210, 210);")
        layout = QVBoxLayout()
        self.message_label = QLabel(text) # Create a QLabel object with the message text passed as an argument
        layout.addWidget(self.message_label, alignment=Qt.AlignmentFlag.AlignCenter) # Add the message label to the layout
        layout.setSpacing(24)
        layout.setContentsMargins(24, 24, 24, 24)
        self.movie_label = QLabel(text) # Create a QLabel object to display the loading icon
        self.movie = QMovie(loading_gif_path) # Create a QMovie object with the loading icon
        self.movie.setScaledSize(QSize(64,64)) # Set the size of the loading icon
        self.movie_label.setMovie(self.movie) # Set the movie to the movie label
        layout.addWidget(self.movie_label, alignment=Qt.AlignmentFlag.AlignCenter) # Add the movie label to the layout
        # Set the layout
        self.setLayout(layout)
        self.adjustSize() # Adjust the size of the dialog to fit the content

    def start(self):
        """
        Method to show the dialog and start the loading animation.
        """
        self.movie.start() # Start the movie
        self.show() # Show the dialog

    def stop(self):
        """
        Method to stop the loading animation and close the dialog.
        """
        self.movie.stop() # Stop the movie
        self.close() # Close the dialog