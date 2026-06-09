# ******************************************************************************
#  * @file    HSDPlotLinesWidget.py
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
#
"""
Multi-sensor line plotting widget with time/FFT and ISPU support.

This module defines `HSDPlotLinesWidget`, a versatile plotting widget used by the HSD GUI
to render streaming sensor signals as line plots. It supports both time-domain and
frequency-domain (FFT) views for selected sensor types (e.g., microphone and accelerometer),
and optionally parses ISPU output formats to extract multiple curves from packed binary
frames.

Highlights
----------
- Toggles between time and FFT views with per-view legend management.
- Optional Hanning windowing and amplitude normalization for FFT rendering.
- Handles software tags by adding vertical markers when tags toggle ON/OFF.
- Integrates ISPU output format loading (JSON) to decode multi-field outputs.
"""
import json
import struct
from collections import deque
from PySide6.QtCore import Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QPushButton, QFileDialog, QFrame

import numpy as np
import pyqtgraph as pg

import stdatalog_gui.UI.icons #do not remove this import. It is used by pkg_resources
from stdatalog_gui.UI.styles import STDTDL_PushButton
from stdatalog_gui.Utils.PlotParams import PlotParams, SensorISPUPlotParams
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotLabel
from stdatalog_gui.Widgets.Plots.PlotLinesWavWidget import PlotLinesWavWidget

from pkg_resources import resource_filename

from stdatalog_core.HSD.utils.type_conversion import TypeConversion

ispu_out_fmt_ok_status_path = resource_filename(
    'stdatalog_gui.UI.icons',
    'outline_done_outline_white_18dp.png'
)
ispu_out_fmt_ko_status_path = resource_filename(
    'stdatalog_gui.UI.icons',
    'outline_close_white_36dp.png'
)

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class HSDPlotLinesWidget(PlotLinesWavWidget):
    """
    General-purpose line plotting widget with FFT and ISPU features.

    Parameters
    ----------
    controller : object
        Application controller providing signals and ISPU helpers.
    comp_name : str
        Component name; suffix determines capabilities (e.g., "_mic", "_acc", "_ispu").
    comp_display_name : str
        Human-readable plot title used by the base widget.
    plot_params : PlotParams | SensorISPUPlotParams
        Plot configuration, including ODR, dimension, time window, and optional
        ISPU output format.
    p_id : int, optional
        Plot identifier used by the base class, by default 0.
    parent : QWidget | None, optional
        Parent widget.

    Notes
    -----
    - When the component type is one of `acc` or `mic`, an FFT view is enabled with
      basic windowing controls.
    - When the component name contains "_ispu", the widget exposes controls to load a
      JSON output format descriptor used to decode the incoming data stream.
    """

    def __init__(self, controller, comp_name, comp_display_name, plot_params, p_id=0, parent=None):
        self.ispu_output_format = None
        self.mlc_output_format = None

        #Time/Freq. flags
        self.tf_time_flag = True
        self.tf_fft_flag = False

        self.fft_sensor_labels = ["acc", "mic"]
        self.comp_name = comp_name
        self.comp_type = self.comp_name.split('_')[-1]

        if self.comp_type in self.fft_sensor_labels:
            #FFT Params
            self.FFT_N = 512
            self.fft_window = np.hanning(self.FFT_N)
            self.current_x = 0
            self.x_data_fft = np.fft.rfftfreq(self.FFT_N, 1/plot_params.odr)
            self.y_queue_fft = dict() # dict of queues for fft
            self.fft_graph_curves = dict()
            self.fft_input_buff = []
            self.fft_window_flag = True

        super().__init__(controller, comp_name, comp_display_name, plot_params, p_id, parent)
        self.controller.sig_tag_done.connect(self.s_tag_done)
        self.controller.sig_mlc_config_loaded.connect(self.s_mlc_config_loaded)
        self.controller.sig_ispu_config_loaded.connect(self.s_ispu_config_loaded)

        self.active_tags = dict()
        self.tag_lines = []

        self.out_fmt_valid = None
        self.plot_params = plot_params

        if self.comp_type in self.fft_sensor_labels:
            self.is_time_freq_settings_displayed = True
            self.pushButton_plot_settings.setVisible(True)
            self.time_freq_setting_frame.setVisible(True)
            self.tf_time_pushButton = self.time_freq_setting_frame.findChild(
                QPushButton, "pushButton_tf_time"
            )
            self.tf_time_pushButton.clicked.connect(self.clicked_tf_time_button)
            self.tf_time_pushButton.setStyleSheet(STDTDL_PushButton.green)
            self.tf_fft_pushButton = self.time_freq_setting_frame.findChild(
                QPushButton, "pushButton_tf_fft"
            )
            self.tf_fft_pushButton.clicked.connect(self.clicked_tf_fft_button)
            self.frame_tf_fft_settings = self.time_freq_setting_frame.findChild(
                QFrame, "frame_tf_fft_settings"
            )
            self.frame_tf_fft_settings.setVisible(False)
            self.pushButton_hanning_window = self.frame_tf_fft_settings.findChild(
                QPushButton, "pushButton_hanning_window"
            )
            self.pushButton_hanning_window.clicked.connect(self.clicked_hanning_window_button)
            self.pushButton_hanning_window.setStyleSheet(STDTDL_PushButton.green)
            self.pushButton_close_settings = self.time_freq_setting_frame.findChild(
                QPushButton, "pushButton_time_freq_close_settings"
            )
            self.pushButton_close_settings.clicked.connect(self.clicked_tf_plot_settings_button)
            self.pushButton_plot_settings.clicked.connect(self.clicked_tf_plot_settings_button)

        #Show Output format description file loading frame
        if "_ispu" in comp_name:
            self.plot_params = SensorISPUPlotParams(
                comp_name,
                plot_params.enabled,
                plot_params.dimension,
                None,
                plot_params.time_window,
            )
            self.is_out_fmt_displayed = True
            self.pushButton_plot_settings.setVisible(True)
            self.load_output_fmt_frame.setVisible(True)
            self.out_fmt_valid = False
            load_output_fmt_pushButton = self.load_output_fmt_frame.findChild(
                QPushButton, "pushButton_load_out_fmt"
            )
            load_output_fmt_pushButton.clicked.connect(self.clicked_load_out_fmt_button)
            self.out_fmt_status = self.load_output_fmt_frame.findChild(QPushButton, "out_fmt_status")
            icon  = QPixmap(ispu_out_fmt_ko_status_path)
            self.out_fmt_status.setIcon(icon)
            self.load_output_fmt_frame.layout().addWidget(PlotLabel("OUT Format"))
            self.pushButton_close_settings = self.load_output_fmt_frame.findChild(
                QPushButton, "pushButton_close_settings"
            )
            self.pushButton_close_settings.clicked.connect(
                self.clicked_out_fmt_plot_settings_button
            )
            self.pushButton_plot_settings.clicked.connect(
                self.clicked_out_fmt_plot_settings_button
            )

        self.time_legend_shown = False
        self.fft_legend_shown = False
        self.__add_time_legend()

    def __load_ispu_ucf(self, filepath):
        """
        Ask the controller to load an ISPU UCF file.

        Parameters
        ----------
        filepath : str
            Path to the UCF file selected by the user.
        """
        self.controller.update_mlc_ispu_config_file(self.comp_name, filepath)

    def __load_ispu_out_fmt(self, filepath):
        """
        Load the ISPU output format descriptor and prepare decoding.

        Parameters
        ----------
        filepath : str
            Path to the JSON output format descriptor.

        Notes
        -----
        On success, stores format metadata and updates the status icon. Also sets
        the number of curves based on the descriptor length.
        """
        self.out_fmt_valid = self.controller.load_ispu_output_fmt_file(filepath)
        if self.out_fmt_valid:
            icon  = QPixmap(ispu_out_fmt_ok_status_path)
            self.__apply_ispu_output_format(self.controller.ispu_output_format["output"])
        else:
            icon  = QPixmap(ispu_out_fmt_ko_status_path)
        self.out_fmt_status.setIcon(icon)

    def __load_ispu_json(self, filepath):
        """
        Ask the controller to load an ISPU JSON configuration file.

        Parameters
        ----------
        filepath : str
            Path to the JSON file selected by the user.
        """
        self.controller.update_mlc_ispu_config_file(self.comp_name, filepath)

    @Slot()
    def clicked_load_out_fmt_button(self):
        """
        Prompt the user to select an ISPU output format JSON and load it.

        When a valid descriptor is loaded, refresh the legend items with the
        names defined by the descriptor.
        """
        json_filter = "JSON Output format description Files (*.json *.JSON)"
        filepath = QFileDialog.getOpenFileName(filter=json_filter)
        if filepath[0]:  # Check if a file was actually selected (not cancelled)
            self.__load_ispu_out_fmt(filepath[0])
            if self.ispu_output_format is not None:
                for id in range(len(self.legend.items)):
                    if id != 0:
                        self.legend.removeItem(self.graph_curves[id])  #
                        self.legend.layout.removeAt(id)
                self.legend.addItem(pg.PlotDataItem(pen=pg.mkPen(0, 0, 0, 0)), "")
                for i, of in enumerate(self.ispu_output_format):
                    self.legend.addItem(self.graph_curves[i], of.get("name", ""))

    @Slot()
    def clicked_out_fmt_plot_settings_button(self):
        """
        Toggle the visibility of the ISPU output-format settings panel.
        """
        self.is_out_fmt_displayed = not self.is_out_fmt_displayed
        self.load_output_fmt_frame.setVisible(self.is_out_fmt_displayed)

    @Slot()
    def clicked_tf_plot_settings_button(self):
        """
        Toggle the visibility of the time/FFT settings panel.
        """
        self.is_time_freq_settings_displayed = not self.is_time_freq_settings_displayed
        self.time_freq_setting_frame.setVisible(self.is_time_freq_settings_displayed)

    def __add_time_legend(self):
        """
        Populate the legend with labels for time-domain curves.

        Uses the component name to infer default axis labels when necessary.
        """
        if not self.time_legend_shown:
            for gc_id in range(self.plot_params.dimension):
                if gc_id not in self.graph_curves:
                    continue
                if "_mic" in self.plot_params.comp_name:
                    self.legend.addItem(self.graph_curves[gc_id], "Waveform")
                elif "_temp" in self.plot_params.comp_name:
                    self.legend.addItem(self.graph_curves[gc_id], "Temperature")
                elif "_pres" in self.plot_params.comp_name:
                    self.legend.addItem(self.graph_curves[gc_id], "Pressure")
                elif "_hum" in self.plot_params.comp_name:
                    self.legend.addItem(self.graph_curves[gc_id], "Humidity")
                elif "_voc" in self.plot_params.comp_name:
                    self.legend.addItem(self.graph_curves[gc_id], "VOC")
                elif "_mlc" in self.plot_params.comp_name:
                    self.legend.addItem(self.graph_curves[gc_id], self.__get_mlc_curve_label(gc_id))
                elif "_ispu" in self.plot_params.comp_name:
                    pass
                else:
                    self.legend.addItem(
                        self.graph_curves[gc_id],
                        "x" if gc_id == 0 else ("y" if gc_id == 1 else "z"),
                    )
            self.time_legend_shown = True
            self.fft_legend_shown = False

    def __get_mlc_curve_label(self, curve_id):
        """Return the display label for an MLC output curve."""
        if self.mlc_output_format is not None and curve_id < len(self.mlc_output_format):
            output_info = self.mlc_output_format[curve_id]
            return output_info.get("name") or output_info.get("reg_name") or f"reg_{curve_id}"
        return f"reg_{curve_id}"

    def __load_mlc_json_outputs(self, filepath):
        """Load MLC JSON configuration and return outputs from the first sensor."""
        try:
            with open(filepath, encoding="utf-8") as f:
                file_content = f.read()
        except OSError as exc:
            log.error(f'Unable to read MLC JSON file ["{filepath}"]: {exc}')
            return None

        try:
            payload = json.loads(file_content[:-1] if file_content.endswith("\x00") else file_content)
        except json.JSONDecodeError as exc:
            log.error(f'Unable to parse MLC JSON file ["{filepath}"]: {exc}')
            return None

        sensors = payload.get("sensors")
        if not isinstance(sensors, list) or len(sensors) == 0:
            log.warning(f'MLC JSON file ["{filepath}"] does not contain any sensor entry')
            return None

        outputs = sensors[0].get("outputs", [])
        if not isinstance(outputs, list):
            log.warning(f'MLC JSON file ["{filepath}"] has an invalid outputs section')
            return None

        return outputs

    def __load_ispu_json_outputs(self, filepath):
        outputs = self.__load_mlc_json_outputs(filepath)
        if outputs is None:
            return None

        normalized_outputs = []
        for output in outputs:
            if not isinstance(output, dict):
                continue
            if not output.get("name") or not output.get("type"):
                continue
            normalized_outputs.append({"name": output.get("name"), "type": output.get("type")})

        if len(normalized_outputs) == 0:
            return None

        return normalized_outputs

    def __apply_ispu_output_format(self, outputs):
        self.ispu_output_format = outputs
        self.controller.ispu_output_format = {"output": outputs}
        self.ispu_out_bytes_cnt = []
        self.ispu_out_fmt_char = []
        for output in outputs:
            self.ispu_out_bytes_cnt.append(self.controller.get_out_fmt_byte_count(output["type"]))
            self.ispu_out_fmt_char.append(self.controller.get_out_fmt_char(output["type"]))
        self.n_curves = len(outputs)
        self.out_fmt_valid = True

    def __apply_mlc_output_format(self, outputs):
        """Update curve count and legend labels from MLC outputs metadata."""
        self.mlc_output_format = outputs
        out_len = len(outputs)
        self.plot_params.dimension = out_len if out_len > 0 else 8 # default to 8 curves if outputs are not properly defined
        self.plot_params.out_fmt = outputs
        self.n_curves = out_len if out_len > 0 else 8 # default to 8 curves if outputs are not properly defined
        self.update_plot_characteristics(self.plot_params)

        for curve_id, curve in self.graph_curves.items():
            curve.setVisible(curve_id < self.plot_params.dimension)

        self.time_legend_shown = False
        for curve in self.graph_curves.values():
            self.legend.removeItem(curve)
        self.__add_time_legend()
        self.app.processEvents()

    def __add_fft_legend(self):
        """
        Populate the legend with labels for FFT-domain curves.
        """
        if not self.fft_legend_shown:
            for gc_id in self.fft_graph_curves:
                if "_mic" in self.plot_params.comp_name:
                    self.legend.addItem(self.fft_graph_curves[gc_id], "FFT_Waveform")
                else:
                    self.legend.addItem(
                        self.fft_graph_curves[gc_id],
                        "FFT_x" if gc_id == 0 else ("FFT_y" if gc_id == 1 else "FFT_z"),
                    )
            self.fft_legend_shown = True
            self.time_legend_shown = False

    def __show_time_curves_in_legend(self):
        """
        Switch legend items to time-domain labels and remove FFT entries.
        """
        self.__add_time_legend()
        for id in range(len(self.fft_graph_curves) + 1):
            if id != 0:
                self.legend.removeItem(self.fft_graph_curves[id - 1])
        self.app.processEvents()

    def __show_fft_curves_in_legend(self):
        """
        Switch legend items to FFT-domain labels and remove time entries.
        """
        self.__add_fft_legend()
        for id in range(len(self.graph_curves) + 1):
            if id != 0:
                self.legend.removeItem(self.graph_curves[id - 1])
        self.app.processEvents()

    def clicked_tf_time_button(self):
        """
        Activate the time-domain view and update curve/legend visibility.
        """
        if self.tf_time_flag == False:
            self.frame_tf_fft_settings.setVisible(False)
            for tl in self.tag_lines:
                tl.setVisible(True)
        self.tf_time_pushButton.setStyleSheet(STDTDL_PushButton.green)
        self.tf_fft_pushButton.setStyleSheet(STDTDL_PushButton.valid)
        self.tf_time_flag = True
        self.tf_fft_flag = False
        self.current_x = self.x_data[-1]
        for i in range(self.plot_params.dimension):
            self.graph_curves[i].setVisible(True)

        if len(self.fft_graph_curves) > 0:
            for i in range(self.plot_params.dimension):
                self.fft_graph_curves[i].setVisible(False)

        self.__show_time_curves_in_legend()

    def clicked_tf_fft_button(self):
        """
        Activate the FFT view and update curve/legend visibility.
        """
        if self.tf_fft_flag == False:
            self.frame_tf_fft_settings.setVisible(True)
            for tl in self.tag_lines:
                tl.setVisible(False)
        self.tf_time_pushButton.setStyleSheet(STDTDL_PushButton.valid)
        self.tf_fft_pushButton.setStyleSheet(STDTDL_PushButton.green)
        self.tf_time_flag = False
        self.tf_fft_flag = True
        self.current_x = self.x_data[-1]

        for i in range(self.plot_params.dimension):
            self.graph_curves[i].setVisible(False)

        self.app.processEvents()

        if self.comp_type in self.fft_sensor_labels:
            self.update_fft_plots(self.plot_params)
            if len(self.fft_graph_curves) > 0:
                for i in range(self.plot_params.dimension):
                    self.fft_graph_curves[i].setVisible(True)

            self.__show_fft_curves_in_legend()

    def clicked_hanning_window_button(self):
        """
        Toggle the application of a Hanning window to the FFT input signal.
        """
        if self.fft_window_flag == True:
            self.fft_window_flag = False
            self.pushButton_hanning_window.setStyleSheet(STDTDL_PushButton.red)
        else:
            self.fft_window_flag = True
            self.pushButton_hanning_window.setStyleSheet(STDTDL_PushButton.green)

    @Slot()
    def s_tag_done(self, status, tag_label:str):
        """
        Add a vertical marker for tag ON/OFF events on the current view.

        Parameters
        ----------
        status : bool
            True for tag ON, False for tag OFF.
        tag_label : str
            Human-readable tag label to show near the marker.
        """
        if status:
            if not tag_label in self.active_tags or self.active_tags[tag_label] == False:
                self.active_tags[tag_label] = True
                pen=pg.mkPen(color='#00FF00', width=1)
                tag_line = pg.InfiniteLine(
                    pos=self.x_data[-1],
                    angle=90,
                    movable=False,
                    pen=pen,
                    label=tag_label + " ON",
                )
                if self.tf_fft_flag:
                    tag_line.setVisible(False)
                else:
                    tag_line.setVisible(True)
                self.graph_widget.addItem(tag_line, ignoreBounds=True)
                self.tag_lines.append(tag_line)

        else:
            if not tag_label in self.active_tags or self.active_tags[tag_label] == True:
                self.active_tags[tag_label] = False
                pen=pg.mkPen(color='#FF0000', width=1)
                tag_line = pg.InfiniteLine(
                    pos=self.x_data[-1],
                    angle=90,
                    movable=False,
                    pen=pen,
                    label=tag_label + " OFF",
                )
                if self.tf_fft_flag:
                    tag_line.setVisible(False)
                else:
                    tag_line.setVisible(True)
                self.graph_widget.addItem(tag_line, ignoreBounds=True)
                self.tag_lines.append(tag_line)

    @Slot(str,str)
    def s_mlc_config_loaded(self, comp_name, ucf_json_path):
        """
        Handle controller notification that MLC or ISPU configuration files have been loaded.

        Parameters
        ----------
        ucf_json_path : str
            Path to the loaded UCF file.
        output_json_path : str
            Path to the loaded output format JSON file.
        """

        if comp_name != self.comp_name:
            return

        if "_mlc" in self.comp_name:
            self.controller.update_mlc_ispu_config_file(self.comp_name, ucf_json_path)
            if ucf_json_path.lower().endswith(".ucf"):
                # for MLC UCF, we just need to update the config in the controller,
                # no need to update the plot params as MLC output format is fixed (1 reg value per configured output)
                pass
            elif ucf_json_path.lower().endswith(".json"):
                # for MLC JSON, we need to update the plot params with the new output format
                # (number of outputs = number of curves)
                outputs = self.__load_mlc_json_outputs(ucf_json_path)
                if outputs is None:
                    return
                self.__apply_mlc_output_format(outputs)
        else:
            log.warning(f"Received MLC config loaded signal for {comp_name},"
                    f"but current component is {self.comp_name}. Ignoring.")

    @Slot(str, str, str)
    def s_ispu_config_loaded(self, comp_name, ucf_json_path, output_json_path = None):
        """
        Slot to handle ISPU configuration loading.

        Parameters
        ----------
        ucf_json_path : str
            Path to the loaded ISPU UCF file.
        output_json_path : str
            Path to the loaded ISPU output format JSON file.
        """
        if comp_name != self.comp_name:
            return

        if "_ispu" in self.comp_name:
            self.controller.update_mlc_ispu_config_file(self.comp_name, ucf_json_path)
            if output_json_path:
                self.controller.update_mlc_ispu_output_file(self.comp_name, output_json_path)

            if ucf_json_path.lower().endswith(".ucf"):
                self.__load_ispu_ucf(ucf_json_path)
                if output_json_path:
                    self.__load_ispu_out_fmt(output_json_path)
                if self.ispu_output_format is not None:
                    for id in range(len(self.legend.items)):
                        if id != 0:
                            self.legend.removeItem(self.graph_curves[id])  #
                            self.legend.layout.removeAt(id)
                    self.legend.addItem(pg.PlotDataItem(pen=pg.mkPen(0, 0, 0, 0)), "")
                    for i, of in enumerate(self.ispu_output_format):
                        self.legend.addItem(self.graph_curves[i], of.get("name", ""))
            elif ucf_json_path.lower().endswith(".json"):
                self.__load_ispu_json(ucf_json_path)
                outputs = self.__load_ispu_json_outputs(ucf_json_path)
                if outputs is None:
                    log.error("Missing ISPU outputs section in unified JSON configuration.")
                    self.out_fmt_valid = False
                    return

                self.__apply_ispu_output_format(outputs)
                for id in range(len(self.legend.items)):
                    if id != 0:
                        self.legend.removeItem(self.graph_curves[id])
                        self.legend.layout.removeAt(id)
                self.legend.addItem(pg.PlotDataItem(pen=pg.mkPen(0, 0, 0, 0)), "")
                for i, of in enumerate(self.ispu_output_format):
                    self.legend.addItem(self.graph_curves[i], of.get("name", ""))
        else:
            log.warning(f"Received ISPU config loaded signal for {comp_name},"
                    f"but current component is {self.comp_name}. Ignoring.")
    
    def __clean_tag_lines(self):
        """
        Remove all tag marker lines from the plot and reset internal list.
        """
        for t in self.tag_lines:
            self.graph_widget.removeItem(t)
            self.tag_lines = []

    @Slot(bool, int) #Override PlotLinesWavWidget s_is_logging
    def s_is_logging(self, status: bool, interface: int):
        """
        React to logging state changes and configure plotting accordingly.

        Parameters
        ----------
        status : bool
            True if logging is starting, False if stopping.
        interface : int
            Link/interface index: 1 for USB, 3 for Serial, 0 for SD card.
        """
        if not "_mic" in self.comp_name:# or "_acc" in self.comp_name:
            if interface == 1 or interface == 3:
                if_str = "USB" if interface == 1 else "Serial"
                print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
                if status:
                    self.__clean_tag_lines()
                    self.current_x = 0
                    if "_ispu" in self.comp_name:
                        enabled = self.plot_params.enabled
                        time_window = self.plot_params.time_window
                        if self.out_fmt_valid:
                            for iof in self.ispu_output_format:
                                data_format = TypeConversion.get_format_char(iof["type"])
                                data_byte_len = TypeConversion.check_type_length(iof["type"])
                                iof["data_format"] = data_format
                                iof["data_byte_len"] = data_byte_len
                            self.plot_params = SensorISPUPlotParams(
                                self.comp_name,
                                enabled,
                                len(self.ispu_output_format),
                                self.ispu_output_format,
                                time_window,
                            )
                            self.update_plot_characteristics(self.plot_params)
                            self.timer.start(self.timer_interval_ms)
                        else:
                            log.error("Missing ISPU JSON Output format descriptor.")
                    else:
                        self.update_plot_characteristics(self.plot_params)
                        self.timer.start(self.timer_interval_ms)
                else:
                    self.timer.stop()
            else: # interface == 0
                print(f"Sensor {self.comp_name} is logging on SD Card: {status}")
        else:
            if interface == 1:
                print(f"Sensor {self.comp_name} is logging via USB: {status}")
                if status:
                    self.__clean_tag_lines()
                    self.current_x = 0
            super().s_is_logging(status, interface)

    def update_fft_plots(self, plot_params):
        """
        Prepare or update FFT plotting structures based on plot parameters.

        Parameters
        ----------
        plot_params : PlotParams
            Parameters providing ODR and time window for FFT computations.
        """
        self.x_data_fft = np.fft.rfftfreq(self.FFT_N, 1/plot_params.odr)
        for i in range(self.plot_params.dimension):
            self._data[i] = deque(maxlen=200000)
            self.y_queue_fft[i] = deque(maxlen=int(self.FFT_N / 2) + 1)
            self.y_queue_fft[i].extend(np.zeros(int(self.FFT_N / 2) + 1))
            if len(self.fft_graph_curves) < self.plot_params.dimension:
                self.fft_graph_curves[i] = self.graph_widget.plot()
                self.fft_graph_curves[i] = pg.PlotDataItem(
                    pen={
                        'color': self.lines_colors[
                            i - (len(self.lines_colors) * int(i / len(self.lines_colors)))
                        ],
                        'width': 1,
                    },
                    skipFiniteCheck=True,
                    ignoreBounds=True,
                )
                self.graph_widget.addItem(self.fft_graph_curves[i])
        self.app_qt.processEvents()
        self.plot_t_interval_size = int(
            self.plot_len / (plot_params.time_window / self.timer_interval)
        )

    def update_plot_characteristics(self, plot_params:PlotParams):
        """
        Update base characteristics and refresh FFT state if applicable.

        Parameters
        ----------
        plot_params : PlotParams
            Plot configuration including ODR and time window.
        """
        super().update_plot_characteristics(plot_params)
        if self.comp_type in self.fft_sensor_labels:
            self.update_fft_plots(plot_params)

    @Slot(bool)
    def s_is_detecting(self, status:bool):
        """
        Mirror detection state into logging state for convenience.

        Parameters
        ----------
        status : bool
            True to start detection, False to stop.
        """
        self.s_is_logging(status, 1)

    def update_plot(self):
        """
        Consume queued samples, resample to plotting cadence, and render curves.

        Notes
        -----
        - Time-domain: resamples accumulated data for smooth updates.
        - FFT-domain: computes windowed FFT batches and updates frequency curves.
        """
        # if self.tf_time_flag:
        self.x_data = self.x_data + self.timer_interval
        # for i in range(self.n_curves):
        for i in range(self.plot_params.dimension):
            if len(self._data[i]) > 0: # If data queue is not empty
                # Extract all data from the queue (pop)
                one_reduced_t_interval = [self._data[i].popleft() for _i in range(len(self._data[i]))]
                # Resample extracted raw data to have the same plot_timer_interval size
                # (plot len / (time window / times interval(sec)))
                self.one_t_interval_resampled[i] = self.resample_linear1D(
                    one_reduced_t_interval, self.plot_t_interval_size
                )
                # Put resampled data into the y data queue
                self.y_queue[i].extend(self.one_t_interval_resampled[i])
                if self.tf_fft_flag:
                    self.fft_input_buff.extend(one_reduced_t_interval)
                    if len(self.fft_input_buff) >= self.FFT_N:
                        signal = self.fft_input_buff[:self.FFT_N]
                        if self.fft_window_flag == True:
                            # Apply windowing
                            w_signal = self.fft_window * signal
                            window_rms = np.sqrt(np.mean(self.fft_window ** 2))
                            # Normalize FFT output by window RMS to compensate for windowing effect
                            fft = (
                                np.abs(np.fft.rfft(w_signal)) / (self.FFT_N * window_rms)
                            )
                            fft[1:] *= 2  # Double only the non-DC components
                        else:
                            fft = np.abs(np.fft.rfft(signal)) / self.FFT_N
                            fft[1:] *= 2  # Double only the non-DC components
                        self.one_t_interval_resampled[i] = np.concatenate(
                            ([fft[0]], 2 * fft[1:])
                        )
                        # Put resampled data into the y data queue
                        self.y_queue_fft[i].extend(self.one_t_interval_resampled[i])
                        self.fft_input_buff = []
            else: #data queue is empty
                if self.tf_fft_flag:
                    self.y_queue_fft[i].extend(self.one_t_interval_resampled[i])
                self.y_queue[i].extend(self.one_t_interval_resampled[i])
            # set extracted resampled data into the plot curve (for each axis)
            # [x and y will have the same len = (plot len / (time window / times interval(sec)))
            # self.graph_curves[i].setData(x=self.x_data,y=np.array(self.y_queue[i]))
            if self.tf_fft_flag:
                self.fft_graph_curves[i].setData(
                    x=self.x_data_fft, y=np.array(self.y_queue_fft[i])
                )
            else:
                self.graph_curves[i].setData(
                    x=self.x_data, y=np.array(self.y_queue[i])
                )
        self.app_qt.processEvents()

    def add_data(self, data):
        """
        Ingest a new data frame and append samples to the queues.

        Parameters
        ----------
        data : Sequence
            If component is ISPU, expects a packed byte stream to decode using
            the loaded output format. Otherwise, defers to base implementation.
        """
        if "_ispu" in self.comp_name:
            if self.plot_params.out_fmt is not None:
                data_idx = 0
                for i, of in enumerate(self.plot_params.out_fmt):
                    ax_len = of["data_byte_len"]
                    ax_value_bytes = np.array(
                        data[0][data_idx : data_idx + ax_len], dtype='int8'
                    ).tobytes() # Convert to bytes
                    ax_value = struct.unpack("=" + of["data_format"], ax_value_bytes)
                    self._data[i].extend(ax_value)
                    data_idx += ax_len
        else:
            super().add_data(data)
