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
and streams audio using Qt Multimedia (`QAudioSink`) with a progress bar.
"""

import wave

import numpy as np
import shiboken6
from PySide6.QtCore import QBuffer, QIODevice, Slot
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices
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
                    if shiboken6.isValid(self.convert_wav_frame) and shiboken6.isValid(self.playing_wav_frame):
                        self.pushButton_convert_wav.setStyleSheet(STDTDL_PushButton.valid)
                        self.convert_wav_frame.setEnabled(False)
                        self.playing_wav_frame.setEnabled(False)
                        self.wav_progress_bar.setValue(0)
                self.update_plot_characteristics(self.plot_params)
                self.timer.start(self.timer_interval_ms)
            else:
                self.timer.stop()
                if "_mic" in self.comp_name:  # or "_acc" in self.comp_name:
                    if shiboken6.isValid(self.convert_wav_frame):
                        self.convert_wav_frame.setEnabled(True)
        else: # interface == 0
            print(f"Component {self.comp_display_name} is logging on SD Card: {status}")

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        """Mirror detection status to logging to reuse the same pipeline."""
        self.s_is_logging(status, 1)

    @staticmethod
    def __24bit_to_32bit(data):
        """Widen packed little-endian 24-bit PCM samples to signed 32-bit PCM.

        QAudioFormat has no 24-bit sample format, so each 24-bit sample is
        sign-extended and left-shifted into the 32-bit range.

        Parameters
        ----------
        data : bytes
            Raw 24-bit PCM samples (3 bytes/sample, length multiple of 3).

        Returns
        -------
        bytes
            Equivalent signed 32-bit PCM samples (4 bytes/sample).
        """
        samples = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
        samples32 = (
            samples[:, 0].astype(np.int32)
            | (samples[:, 1].astype(np.int32) << 8)
            | (samples[:, 2].astype(np.int32) << 16)
        )
        samples32[samples32 & 0x800000 != 0] -= 0x1000000
        return (samples32 << 8).astype("<i4").tobytes()

    def __play_wav_file(self, filepath):
        """Stream a WAV file to the default audio output, updating the progress.

        Parameters
        ----------
        filepath : str
            Path to the WAV file to play.
        """
        self.pushButton_stop_wav.setEnabled(True)
        self.pushButton_play_wav.setEnabled(False)
        #open a wav file
        f = wave.open(filepath,"rb")

        #map WAV sample width (bytes) to a Qt Multimedia sample format
        #24-bit has no native QAudioFormat, so it's widened to 32-bit on the fly
        sample_width = f.getsampwidth()
        is_24bit = sample_width == 3
        sample_format_map = {
            1: QAudioFormat.SampleFormat.UInt8,
            2: QAudioFormat.SampleFormat.Int16,
            3: QAudioFormat.SampleFormat.Int32,
            4: QAudioFormat.SampleFormat.Int32,
        }
        audio_format = QAudioFormat()
        audio_format.setSampleRate(f.getframerate())
        audio_format.setChannelCount(f.getnchannels())
        audio_format.setSampleFormat(
            sample_format_map.get(sample_width, QAudioFormat.SampleFormat.Int16)
        )

        #read the whole clip upfront so Qt can pull data at its own pace
        raw_data = f.readframes(f.getnframes())
        f.close()
        pcm_data = self.__24bit_to_32bit(raw_data) if is_24bit else raw_data

        self.wav_progress_bar.setMaximum(100)
        #buffer must be kept alive on self: QAudioSink pulls from it asynchronously
        self.__playback_buffer = QBuffer()
        self.__playback_buffer.setData(pcm_data)
        self.__playback_buffer.open(QIODevice.OpenModeFlag.ReadOnly)

        self.__audio_sink = QAudioSink(QMediaDevices.defaultAudioOutput(), audio_format)
        self.__audio_sink.start(self.__playback_buffer)

        #poll until playback drains or the user stops it
        while self.__audio_sink.state() != QAudio.State.StoppedState and self.stop_stream == False:
            progress = int(self.__playback_buffer.pos() * 100 / max(self.__playback_buffer.size(), 1))
            self.wav_progress_bar.setValue(progress)
            self.app_qt.processEvents()
            if self.__audio_sink.state() == QAudio.State.IdleState:
                break

        self.pushButton_play_wav.setEnabled(True)
        self.pushButton_stop_wav.setEnabled(False)
        self.__audio_sink.stop()
        self.__playback_buffer.close()
        self.wav_progress_bar.setValue(0)
        self.stop_stream = False

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
