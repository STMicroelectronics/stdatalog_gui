#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    PlotLinesWavWidget.py
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
Plot lines widget extension with WAV conversion and playback controls.

This module adds a side panel to `PlotLinesWidget` for microphones to convert
acquired data to a WAV file and play it back. It coordinates UI state with
logging status, invokes conversion via the controller, shows a waiting dialog,
and streams audio using `pyaudio` with a progress bar.
"""

import wave

import pyaudio
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QProgressBar, QSpinBox

from stdatalog_gui.UI.styles import STDTDL_PushButton
from stdatalog_gui.Widgets.Plots.PlotLinesWidget import PlotLinesWidget
from stdatalog_gui.Widgets.LoadingWindow import LoadingWindow

class PlotLinesWavWidget(PlotLinesWidget):
    """Line plot widget with WAV conversion and playback for mic components.

    Parameters
    ----------
    controller : QObject
        Controller/table used by the base plot for signals and threading.
    comp_name : str
        Component identifier (mic components enable the WAV UI panel).
    comp_display_name : str
        Human-friendly component name used in dialogs.
    plot_params : dict | Any
        Plot configuration forwarded to the base class.
    p_id : int, optional
        Plot identifier forwarded to the base class.
    parent : QWidget | None, optional
        Parent widget.

    Attributes
    ----------
    wav_files_paths : dict[str, str]
        Map of component name to converted WAV file path.
    waiting_dialog : LoadingWindow | None
        Dialog shown during conversion; closed on completion.
    is_wav_settings_displayed : bool
        Whether the WAV control panel is visible.
    stop_stream : bool
        Flag to stop playback loop.
    """

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        plot_params,
        p_id=0,
        parent=None,
    ):
        super().__init__(controller, comp_name, comp_display_name, plot_params, p_id, parent)
        self.app = QApplication.instance()
        self.wav_files_paths = {}
        self.parent_widget = parent

        # Waiting Dialog
        self.waiting_dialog = None

        # Show WAV conversion/playing frame for mic components
        if "_mic" in comp_name:  # or "_acc" in comp_name:
            self.pushButton_plot_settings.setVisible(True)
            self.is_wav_settings_displayed = False
            self.frame_wav_control.setVisible(False)

            self.convert_wav_frame = self.frame_wav_control.findChild(QFrame, "convert_wav_frame")
            self.convert_wav_frame.setEnabled(False)
            self.playing_wav_frame = self.frame_wav_control.findChild(QFrame, "playing_wav_frame")
            self.playing_wav_frame.setEnabled(False)

            self.pushButton_convert_wav = self.frame_wav_control.findChild(
                QPushButton, "pushButton_convert_wav"
            )
            self.pushButton_convert_wav.clicked.connect(self.clicked_convert_dat2wav_button)
            self.wav_progress_bar = self.frame_wav_control.findChild(
                QProgressBar,
                "wav_progressBar"
            )
            self.wav_progress_bar.setValue(0)
            self.start_time_spinbox = self.frame_wav_control.findChild(
                QSpinBox,
                "start_time_spinbox"
            )
            self.end_time_spinbox = self.frame_wav_control.findChild(
                QSpinBox,
                "end_time_spinbox"
            )
            self.pushButton_play_wav = self.frame_wav_control.findChild(
                QPushButton,
                "pushButton_play_wav"
            )
            self.pushButton_play_wav.clicked.connect(self.clicked_play_wav_button)
            self.pushButton_play_wav.setStyleSheet(STDTDL_PushButton.green)

            self.pushButton_stop_wav = self.frame_wav_control.findChild(
                QPushButton, "pushButton_stop_wav"
            )
            self.pushButton_stop_wav.clicked.connect(self.clicked_stop_wav_button)
            self.pushButton_stop_wav.setStyleSheet(STDTDL_PushButton.red)

            self.pushButton_close_settings = self.frame_wav_control.findChild(
                QPushButton, "pushButton_wav_close_settings"
            )
            self.pushButton_close_settings.clicked.connect(self.clicked_wav_plot_settings_button)
            self.pushButton_plot_settings.clicked.connect(self.clicked_wav_plot_settings_button)

    @Slot(bool, int)
    def s_is_logging(self, status: bool, interface: int):
        """Update timers and WAV UI state when logging starts/stops.

        Parameters
        ----------
        status : bool
            Logging status.
        interface : int
            Interface id: 1 USB, 3 Serial, 0 SD Card.
        """
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
            if status:
                if "_mic" in self.comp_name:  # or "_acc" in self.comp_name:
                    self.pushButton_convert_wav.setStyleSheet(STDTDL_PushButton.valid)
                    self.convert_wav_frame.setEnabled(False)
                    self.playing_wav_frame.setEnabled(False)
                    self.wav_progress_bar.setValue(0)
                self.update_plot_characteristics(self.plot_params)
                self.timer.start(self.timer_interval_ms)
            else:
                self.timer.stop()
                if "_mic" in self.comp_name:  # or "_acc" in self.comp_name:
                    self.convert_wav_frame.setEnabled(True)
        else: # interface == 0
            print(f"Component {self.comp_display_name} is logging on SD Card: {status}")

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        """Mirror detection status to logging to reuse the same pipeline."""
        self.s_is_logging(status, 1)

    def __play_wav_file(self, filepath):
        """Stream a WAV file to the default audio output, updating the progress.

        Parameters
        ----------
        filepath : str
            Path to the WAV file to play.
        """
        self.pushButton_stop_wav.setEnabled(True)
        self.pushButton_play_wav.setEnabled(False)
        #define stream chunk
        chunk = 1024
        #open a wav file
        f = wave.open(filepath,"rb")

        wav_max_for_progress_bar = int(f.getnframes()/chunk)*chunk
        wav_data_cnt = 0
        self.wav_progress_bar.setMaximum(wav_max_for_progress_bar)

        #instantiate PyAudio
        p = pyaudio.PyAudio()
        #open stream
        stream = p.open(
            format=p.get_format_from_width(f.getsampwidth()),
            channels=f.getnchannels(),
            rate=f.getframerate(),
            output=True,
        )
        #read data
        data = f.readframes(chunk)
        #play stream
        while data and self.stop_stream == False:
            stream.write(data)
            data = f.readframes(chunk)
            wav_data_cnt += chunk
            self.wav_progress_bar.setValue(wav_data_cnt)
            self.app_qt.processEvents()

        self.pushButton_play_wav.setEnabled(True)
        self.pushButton_stop_wav.setEnabled(False)
        #stop stream
        stream.stop_stream()
        stream.close()
        self.stop_stream = False

        #close PyAudio
        p.terminate()

    def __stop_wav_file(self, filepath):
        """Stop the current playback loop and reset the progress bar.
        Parameters
        ----------
        filepath : str
            Path to the WAV file being played (unused here but kept for signature consistency).
        """
        _ = filepath  # Unused parameter
        self.stop_stream = True
        self.wav_progress_bar.setValue(0)

    @Slot()
    def clicked_wav_plot_settings_button(self):
        """Toggle the visibility of the WAV controls panel."""
        self.is_wav_settings_displayed = not self.is_wav_settings_displayed
        if self.is_wav_settings_displayed:
            self.frame_wav_control.setVisible(True)
        else:
            self.frame_wav_control.setVisible(False)

    def on_wav_conversion_finished(self, comp_name, converted_wav_fpath):
        """Callback invoked when the WAV conversion thread has finished.

        Parameters
        ----------
        comp_name : str
            Component name associated with the converted audio.
        converted_wav_fpath : str | None
            Path of the converted WAV file, or None/empty on failure.
        """
        self.waiting_dialog.loadingDone()
        if converted_wav_fpath is None or converted_wav_fpath == "":
            self.playing_wav_frame.setEnabled(False)
            self.pushButton_convert_wav.setStyleSheet(STDTDL_PushButton.invalid)
            return
        self.wav_files_paths[comp_name] = converted_wav_fpath
        self.playing_wav_frame.setEnabled(True)

    @Slot()
    def clicked_convert_dat2wav_button(self):
        """Start conversion of acquired data to WAV using the controller.

        Shows a waiting dialog and wires the completion callback.
        """
        convert_dat2wav = getattr(self.controller, "convert_dat2wav", None)
        if convert_dat2wav is not None and callable(convert_dat2wav):
            self.pushButton_convert_wav.setStyleSheet(STDTDL_PushButton.valid)
            self.waiting_dialog = LoadingWindow(
                "Wav Conversion...",
                (
                    f"Acquired data conversion ongoing for {self.comp_display_name}. "
                    "Please wait..."
                ),
                self,
            )
            self.controller.start_wav_conversion_thread(
                self.comp_name,
                self.start_time_spinbox.value(),
                self.end_time_spinbox.value(),
                self.on_wav_conversion_finished,
            )

    @Slot()
    def clicked_play_wav_button(self):
        """Play the last converted WAV for this component."""
        self.__play_wav_file(self.wav_files_paths[self.comp_name])

    @Slot()
    def clicked_stop_wav_button(self):
        """Stop the current WAV playback and reset state."""
        self.__stop_wav_file(self.wav_files_paths[self.comp_name])
