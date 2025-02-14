
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

import pyaudio
import wave

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QProgressBar, QSpinBox

from stdatalog_gui.UI.styles import STDTDL_PushButton
from stdatalog_gui.Widgets.Plots.PlotLinesWidget import PlotLinesWidget
from stdatalog_gui.Widgets.LoadingWindow import LoadingWindow

class PlotLinesWavWidget(PlotLinesWidget):
    
    def __init__(self, controller, comp_name, comp_display_name, plot_params, p_id=0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, plot_params, p_id, parent)
        self.app = QApplication.instance()
        self.wav_files_paths = {}
        self.parent_widget = parent

        # Waiting Dialog
        self.waiting_dialog = None
        
        #Show Wav conversion/playing frame
        if "_mic" in comp_name:# or "_acc" in comp_name:
            self.pushButton_plot_settings.setVisible(True)
            self.is_wav_settings_displayed = False
            self.frame_wav_control.setVisible(False)
            
            self.convert_wav_frame = self.frame_wav_control.findChild(QFrame, "convert_wav_frame")
            self.convert_wav_frame.setEnabled(False)
            self.playing_wav_frame = self.frame_wav_control.findChild(QFrame, "playing_wav_frame")
            self.playing_wav_frame.setEnabled(False)
            
            self.pushButton_convert_wav = self.frame_wav_control.findChild(QPushButton, "pushButton_convert_wav")
            self.pushButton_convert_wav.clicked.connect(self.clicked_convert_dat2wav_button)
            self.wav_progress_bar = self.frame_wav_control.findChild(QProgressBar, "wav_progressBar")
            self.wav_progress_bar.setValue(0)
            self.start_time_spinbox = self.frame_wav_control.findChild(QSpinBox, "start_time_spinbox")
            self.end_time_spinbox = self.frame_wav_control.findChild(QSpinBox, "end_time_spinbox")
            
            self.pushButton_play_wav = self.frame_wav_control.findChild(QPushButton, "pushButton_play_wav")
            self.pushButton_play_wav.clicked.connect(self.clicked_play_wav_button)
            self.pushButton_play_wav.setStyleSheet(STDTDL_PushButton.green)
            
            self.pushButton_stop_wav = self.frame_wav_control.findChild(QPushButton, "pushButton_stop_wav")
            self.pushButton_stop_wav.clicked.connect(self.clicked_stop_wav_button)
            self.pushButton_stop_wav.setStyleSheet(STDTDL_PushButton.red)
            
            self.pushButton_close_settings = self.frame_wav_control.findChild(QPushButton, "pushButton_wav_close_settings")
            self.pushButton_close_settings.clicked.connect(self.clicked_wav_plot_settings_button)
            self.pushButton_plot_settings.clicked.connect(self.clicked_wav_plot_settings_button)
    
    @Slot(bool, int)
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
            if status:
                if "_mic" in self.comp_name:# or "_acc" in self.comp_name:
                    self.pushButton_convert_wav.setStyleSheet(STDTDL_PushButton.valid)
                    self.convert_wav_frame.setEnabled(False)
                    self.playing_wav_frame.setEnabled(False)
                    self.wav_progress_bar.setValue(0)
                self.update_plot_characteristics(self.plot_params)
                self.timer.start(self.timer_interval_ms)
            else:
                self.timer.stop()
                if "_mic" in self.comp_name: # or "_acc" in self.comp_name:
                    self.convert_wav_frame.setEnabled(True)
        else: # interface == 0
            print("Component {} is logging on SD Card: {}".format(self.comp_name,status))
            
    @Slot(bool)
    def s_is_detecting(self, status:bool):
        self.s_is_logging(status, 1)
            
    def __play_wav_file(self, filepath):
        self.pushButton_stop_wav.setEnabled(True)
        self.pushButton_play_wav.setEnabled(False)
        #define stream chunk
        chunk = 1024
        #open a wav file
        f = wave.open(filepath,"rb")
        
        wav_max_for_progress_bar = (int(f.getnframes()/chunk)*chunk)
        wav_data_cnt = 0
        self.wav_progress_bar.setMaximum(wav_max_for_progress_bar)
        
        #instantiate PyAudio
        p = pyaudio.PyAudio()
        #open stream
        stream = p.open(format = p.get_format_from_width(f.getsampwidth()),
                        channels = f.getnchannels(),
                        rate = f.getframerate(),
                        output = True)
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
        self.stop_stream = True
        self.wav_progress_bar.setValue(0)
        
    @Slot()
    def clicked_wav_plot_settings_button(self):
        self.is_wav_settings_displayed = not self.is_wav_settings_displayed
        if self.is_wav_settings_displayed:
            self.frame_wav_control.setVisible(True)
        else:
            self.frame_wav_control.setVisible(False)

    def on_wav_conversion_finished(self, comp_name, converted_wav_fpath):
        """
        Callback method that is called when the wav conversion is finished.
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
        convert_dat2wav = getattr(self.controller, "convert_dat2wav", None)
        if convert_dat2wav is not None and callable(convert_dat2wav):
            self.pushButton_convert_wav.setStyleSheet(STDTDL_PushButton.valid)
            self.waiting_dialog = LoadingWindow("Wav Conversion...", "Acquired data conversion ongoing for {}. Please wait...".format(self.comp_display_name), self)
            self.controller.start_wav_conversion_thread(self.comp_name, self.start_time_spinbox.value(), self.end_time_spinbox.value(), self.on_wav_conversion_finished)
    
    @Slot()
    def clicked_play_wav_button(self):
        self.__play_wav_file(self.wav_files_paths[self.comp_name])
        
    @Slot()
    def clicked_stop_wav_button(self):
        self.__stop_wav_file(self.wav_files_paths[self.comp_name])
