# *****************************************************************************
#  * @file    Controller.py
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
HSD GUI controller for device communication, logging, detection, and plotting.

This module provides the `HSD_Controller` class, which orchestrates the device link,
real-time acquisitions, plotting pipeline, AI algorithm outputs, and configuration
management for ST data logging devices. It encapsulates threads for sensor datas
acquisition, serial reading, and asynchronous conversions (e.g., DAT → WAV), while
exposing a Qt signal-based API for UI components to react to state changes.

Highlights
----------
- Establishes and manages the HSD link (USB/serial) and device template loading.
- Starts/stops logging and detection, including auto-mode and bandwidth checks.
- Builds plot parameters per sensor/algorithm using DTDL and device status.
- Feeds plot widgets and a DataToolkit pipeline with streaming data.
- Handles PNPL command requests/responses and configuration persistence.
- Supports offline plots and DAT-to-WAV conversion with timestamp recovery.
"""
import shutil
import struct
import time
import warnings
import os
import json
import copy
from threading import Thread, Event
from functools import partial
import sys
from enum import Enum

from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtWidgets import QFileDialog

from stdatalog_pnpl.DTDL.device_template_manager import DeviceCatalogManager
from stdatalog_pnpl.PnPLCmd import PnPLCMDManager
from stdatalog_pnpl.DTDL.device_template_model import ContentSchema, SchemaEnum
from stdatalog_pnpl.DTDL.dtdl_utils import UnitMap
import stdatalog_pnpl.DTDL.dtdl_utils as DTDLUtils

from stdatalog_core.HSD_utils.DataClass import DataClass
from stdatalog_core.HSD_utils.DataReader import DataReader

from stdatalog_gui.STDTDL_Controller import ComponentType, STDTDL_Controller
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotLinesWidget import HSDPlotLinesWidget
from stdatalog_gui.Utils.PlotParams import (
    AnomalyDetectorModelPlotParams,
    ClassificationModelPlotParams,
    FFTAlgPlotParams,
    PlotPAmbientParams,
    PlotPMotionParams,
    PlotPObjectParams,
    PlotPPresenceParams,
    SensorLightPlotParams,
    SensorMemsPlotParams,
    SensorAudioPlotParams,
    SensorPowerPlotParams,
    SensorPresenscePlotParams,
    SensorRangingPlotParams,
    SensorPlotParams,
    SensorCameraPlotParams
)

from stdatalog_core.HSD.HSDatalog import HSDatalog
from stdatalog_core.HSD_link.HSDLink import HSDLink
from stdatalog_core.HSD_link.HSDLink_v1 import HSDLink_v1
from stdatalog_core.HSD_link.HSDLink_v2 import HSDLink_v2_Serial, HSDLinkV2SerialError
from stdatalog_dtk.HSD_DataToolkit import HSD_DataToolkit
from stdatalog_core.HSD.utils.type_conversion import TypeConversion

import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

log_file_name = None
for handler in log.parent.handlers:
    if hasattr(handler, "baseFilename"):
        log_file_name = os.path.basename(getattr(handler, "baseFilename"))


class AutomodeStatus(Enum):
    """
    Enumeration of auto-mode statuses.

    Attributes
    ----------
        AUTOMODE_UNSTARTED : int
            Auto-mode has not been started.
        AUTOMODE_IDLE : int
            Auto-mode is idling between acquisitions.
        AUTOMODE_LOGGING : int
            Auto-mode is actively logging data.
    """

    AUTOMODE_UNSTARTED = -1
    AUTOMODE_IDLE = 1
    AUTOMODE_LOGGING = 2

class FastTelemetryStateEnum(Enum):
    """
    Enumeration of Fast Telemetry states.

    Attributes
    ----------
        MCP_FT_DISABLE : int
            Fast Telemetry is disabled.
        MCP_FT_ENABLE : int
            Fast Telemetry is enabled.
    """

    MCP_FT_DISABLE = 0
    MCP_FT_ENABLE = 1

class WavConversionThread(QThread):
    """
    Thread to convert binary DAT segments into WAV audio files.

    Parameters
    ----------
    controller : STDTDL_Controller
        Controller instance used to access acquisition folders and conversion APIs.
    comp_name : str
        Component name to convert (typically an audio sensor).
    start_time : int
        Start timestamp in microseconds for the conversion range.
    end_time : int
        End timestamp in microseconds for the conversion range.

    Signals
    -------
    sig_finished : Signal(str, str)
        Emitted when conversion completes, carrying the component name and the
        generated WAV file path.

    Notes
    -----
    The thread delegates conversion to `HSDatalog.convert_dat_to_wav` and emits
    the `sig_finished` signal upon completion. No device-side behavior changes.
    """

    sig_finished = Signal(str, str)  # Signal emitted when the segmentation thread finishes

    def __init__(self, controller, comp_name, start_time, end_time):
        """
        Initializes the segmentation algorithm thread.

        Args:
            controller (STDTDL_Controller): Controller object
            comp_name (str): Component name
            start_time (int): Start time
            end_time (int): End time
        """
        super().__init__()
        self.controller = controller
        self.comp_name = comp_name
        self.start_time = start_time
        self.end_time = end_time

    def run(self):
        """
        Runs the wav conversion thread.
        """
        print("Wav Conversion Thread started")
        wav_file_path = self.controller.convert_dat2wav(
            self.comp_name, self.start_time, self.end_time
        )
        print("Wav Conversion Thread finished")
        # Emit the finished signal with the controller object reference
        # as argument to be used in the finish callback
        self.sig_finished.emit(self.comp_name, wav_file_path)

class HSD_Controller(STDTDL_Controller):
    """
    Main GUI controller coordinating link, logging, plots, and PNPL commands.

    Responsibilities
    ----------------
    - Initialize HSD link (USB/serial) and load the device template (DTDL).
    - Manage logging/detection lifecycles, auto-mode, and bandwidth checks.
    - Build plot parameters from device status and DTDL schemas.
    - Feed plot widgets and the DataToolkit pipeline with streaming data.
    - Handle PNPL commands and UI signals for configuration and feedback.

    Attributes
    ----------
    hsd_link : HSDLink | HSDLink_v1 | HSDLink_v2_Serial
        Active device link instance or `None` when disconnected.
    is_hsd_link_up : bool
        True when a device link is ready.
    is_logging : bool
        True when logging is active.
    is_detecting : bool
        True when detection mode is active.
    automode_enabled : bool
        Auto-mode feature toggle (False: disabled, True: enabled).
    automode_status : AutomodeStatus
        Current auto-mode status enum.
    components_dtdl : dict
        DTDL component interfaces keyed by component name.
    components_status : dict
        Current device status components keyed by component name.
    plot_widgets : dict
        Registered plot widgets keyed by component name.
    data_pipeline : object | None
        Optional data processing pipeline (DataToolkit).

    Signals
    -------
    sig_is_waiting_auto_start : Signal(bool)
        Emitted when auto-mode enters/leaves "waiting to start" state.
    sig_is_waiting_idle : Signal(bool)
        Emitted when auto-mode is idling between acquisitions.
    sig_is_auto_started : Signal(bool)
        Emitted when auto-mode externally toggles start/stop.
    sig_is_auto_started_inner : Signal(bool)
        Emitted when auto-mode internally triggers logging start/stop.
    sig_tag_done : Signal(bool, str)
        Emitted after tag operations with status and label.
    sig_hsd_bandwidth_exceeded : Signal(bool)
        Emitted when computed bandwidth exceeds the configured maximum.
    sig_lock_start_button : Signal(bool, str)
        Requests UI to enable/disable Start based on configuration validity.
    sig_streaming_error : Signal(bool, str)
        Reports streaming errors with a human-readable description.

    Notes
    -----
    Public API and method behavior remain unchanged. Docstrings are added for
    clarity and consistency with other modules.
    """

    MAX_HSD_BANDWIDTH = 6000000
    # Signals
    sig_is_waiting_auto_start = Signal(bool)
    sig_is_waiting_idle = Signal(bool)
    sig_is_auto_started = Signal(bool)
    sig_is_auto_started_inner = Signal(bool)
    sig_tag_done = Signal(bool, str)  # (on|off),tag_label
    sig_hsd_bandwidth_exceeded = Signal(bool)
    sig_lock_start_button = Signal(bool, str)
    sig_streaming_error = Signal(bool, str)

    # dataToolKit
    sig_new_spt_data_ready = Signal(DataClass)

    sig_key_pressed = Signal(Qt.Key)
    sig_key_released = Signal(Qt.Key)
    
    class DataReader(DataReader):
        """
        Data reader that forwards samples to both the plot pipeline and toolkit.

        Parameters
        ----------
        controller : HSD_Controller
            Owning controller used to emit toolkit signals.
        output_function : callable
            Callback invoked with `DataClass` as new data arrives.
        comp_name : str
            Component name associated with this reader.
        samples_per_ts : int
            Samples per timestamp; zero for algorithm streams without timestamps.
        dimensions : int
            Number of channels/points per sample.
        sample_size : int
            Byte length of each sample value.
        data_format : str
            `struct`-compatible format character for packing/unpacking.
        sensitivity : float, optional
            Scale factor applied to raw values; defaults to 1.
        interleaved_data : bool, optional
            True if data for multiple channels are interleaved in the stream.
        flat_raw_data : bool, optional
            True to treat raw bytes as a flat payload without per-sample parsing.
        """

        def __init__(
            self,
            controller,
            output_function,
            comp_name,
            samples_per_ts,
            dimensions,
            sample_size,
            data_format,
            sensitivity=1,
            interleaved_data=True,
            flat_raw_data=False,
        ):
            self.controller = controller
            super().__init__(
                output_function,
                comp_name,
                samples_per_ts,
                dimensions,
                sample_size,
                data_format,
                sensitivity,
                interleaved_data,
                flat_raw_data,
            )

        def feed_data(self, data):
            """
            Feed a `DataClass` instance to the output and emit toolkit signals.

            Parameters
            ----------
            data : DataClass
                New data chunk for `comp_name`, containing raw bytes.

            Notes
            -----
            When DataToolkit is enabled, emits a copy via `sig_new_spt_data_ready`
            before delegating to the base `DataReader.feed_data`.
            """
            if self.controller.dt_plugins_folder_path is not None:
                a_data = copy.copy(data)
                self.controller.sig_new_spt_data_ready.emit(a_data)
            super().feed_data(data)

    class SensorAcquisitionThread(Thread):
        """
        Thread that pulls sensor data from the device link and forwards it.

        Parameters
        ----------
        event : threading.Event
            Stop flag used to terminate the acquisition loop.
        hsd_link : HSDLink
            Active device link used to request sensor data.
        data_reader : HSD_Controller.DataReader
            Reader used to parse and pass data to plots/pipeline.
        d_id : int
            Device identifier.
        comp_name : str
            Component name for the sensor or algorithm stream.
        sensor_data_file : io.BufferedWriter | None
            Optional file to persist raw stream bytes.
        usb_dps : int
            USB data payload size per packet (used for integrity checks).
        sig_streaming_error : Signal(bool, str), optional
            Signal to report streaming errors to the UI.

        Notes
        -----
        Starts an internal Qt timer object to detect prolonged lack of data and
        raises a streaming error if necessary.
        """

        def __init__(
            self,
            event,
            hsd_link,
            data_reader,
            d_id,
            comp_name,
            sensor_data_file,
            usb_dps,
            sig_streaming_error=None,
        ):

            class EmptyDataTimer(QObject):
                """
                Lightweight timer object used to detect prolonged lack of data.

                This helper runs in its own `QThread` and emits a `timeout_signal` when
                no samples arrive for a configurable period. The owning acquisition
                thread can reset the interruption event to cancel/skip the timeout when
                data resumes.

                Signals
                -------
                timeout_signal : Signal()
                    Emitted after the timeout elapses without interruption.

                Notes
                -----
                - Designed to be moved to a dedicated `QThread`.
                - The wait uses `time.sleep(timeout)` and checks an interrupt flag.
                """

                timeout_signal = Signal()

                def __init__(self, comp_name):
                    """
                    Initialize the timer with a component-specific name.

                    Parameters
                    ----------
                    comp_name : str
                        Component name used to build a readable timer identifier.
                    """
                    super().__init__()
                    self.interrupt_event = Event()
                    self.timeout = 5  # if "_tof" in comp_name else 3
                    self.name = f"edt_{comp_name}"

                def run_wait(self):
                    """
                    Sleep for the configured timeout and emit on no interruption.

                    Notes
                    -----
                    Recreates the `interrupt_event` each run. If the event is not set by
                    the acquisition loop before the sleep completes, `timeout_signal` is
                    emitted to notify about missing incoming data.
                    """
                    self.interrupt_event = Event()
                    time.sleep(self.timeout)
                    if not self.interrupt_event.is_set():
                        self.timeout_signal.emit()

            Thread.__init__(self)
            self.name = comp_name
            self.stopped = event
            self.hsd_link = hsd_link
            self.data_reader = data_reader
            self.d_id = d_id
            self.comp_name = comp_name
            self.sensor_data_file = sensor_data_file
            self.sig_streaming_error = sig_streaming_error
            self.usb_dps = usb_dps
            self.over_proto = 0
            self.t0 = 0
            self.prev_cnt = 0

            self.objThread = QThread()
            self.obj = EmptyDataTimer(comp_name)
            self.obj.moveToThread(self.objThread)
            self.obj.timeout_signal.connect(self.raise_empty_data_error)
            self.objThread.started.connect(self.obj.run_wait)

        def raise_empty_data_error(self):
            """
            Emit a streaming error when no data arrives for the component.

            Notes
            -----
            Suggests lowering component ODR to improve acquisition reliability.
            """
            app_log = log_file_name if log_file_name is not None else "application"
            error_msg = (
                f"No data from {self.comp_name} Component.\n"
                "Restart the acquisition lowering component ODR to acquire data "
                "correctly.\n"
                "Have a look in "
                f"{app_log} "
                "log file for more detailed info."
            )

            if not ("_mlc" in self.comp_name or "_ispu" in self.comp_name):
                # MLC/ISPU components can have long processing times causing data gaps,
                # so we skip the error in that case
                log.error(error_msg)
                if self.sig_streaming_error is not None:
                    self.sig_streaming_error.emit(True, error_msg)

        def run(self):
            """
            Main acquisition loop reading device packets and forwarding payloads.

            Notes
            -----
            - Checks USB packet counters to detect losses and emits errors.
            - Writes raw bytes to `sensor_data_file` when configured.
            - Starts an empty-data timer when the device returns no data.
            """
            while not self.stopped.wait(0.02):
                # while not self.stopped.wait(1):
                sensor_data = self.hsd_link.get_sensor_data(self.d_id, self.comp_name)
                if sensor_data is not None:
                    if self.objThread.isRunning():
                        self.obj.interrupt_event.set()
                    nof_usb_packet = len(sensor_data[1]) / (self.usb_dps + 4)
                    for p in range(int(nof_usb_packet)):
                        curr_cnt = struct.unpack(
                            "=i",
                            sensor_data[1][p * (self.usb_dps + 4) : p * (self.usb_dps + 4) + 4],
                        )[0]
                        diff = curr_cnt - self.prev_cnt
                        if curr_cnt != 0 and diff != self.usb_dps:
                            app_log = (
                                log_file_name if log_file_name is not None else "application"
                            )
                            error_msg = (
                                f"Streaming errors in {self.comp_name} component!\n"
                                f"{int(diff//self.usb_dps)} USB packets ({diff} bytes) lost.\n"
                                "Have a look in "
                                f"{app_log} "
                                "log file for more detailed info."
                            )
                            if self.sig_streaming_error is not None:
                                self.sig_streaming_error.emit(True, error_msg)
                            log.error(error_msg)
                        self.prev_cnt = curr_cnt

                        self.data_reader.feed_data(
                            DataClass(
                                self.comp_name,
                                sensor_data[1][
                                    p * (self.usb_dps + 4) + 4 : (p + 1) * (self.usb_dps + 4)
                                ],
                            )
                        )
                    if self.sensor_data_file is not None:
                        self.sensor_data_file.write(sensor_data[1])
                else:
                    self.objThread.start()
            if self.objThread.isRunning():
                self.obj.interrupt_event.set()
                self.objThread.quit()

    class SensorAcquisitionThread_test_v1(SensorAcquisitionThread):
        """
        v1-compatible sensor acquisition thread using legacy HSDLink APIs.

        Parameters
        ----------
        event : threading.Event
            Stop flag to terminate the loop.
        hsd_link : HSDLink_v1
            Legacy link instance providing `get_sensor_data(s_id, ss_id)`.
        data_reader : HSD_Controller.DataReader
            Reader used to forward data to plots/pipeline.
        d_id : int
            Device identifier.
        s_id : int
            Sensor identifier.
        ss_id : int
            Sub-sensor identifier.
        comp_name : str
            Component name associated to the stream.
        sensor_data_file : io.BufferedWriter | None
            Optional file sink for raw bytes.
        """

        def __init__(
            self, event, hsd_link, data_reader, d_id, s_id, ss_id, comp_name, sensor_data_file
        ):
            self.s_id = s_id
            self.ss_id = ss_id
            super().__init__(self, event, hsd_link, data_reader, d_id, comp_name, sensor_data_file)

        def run(self):
            """
            Acquisition loop for HSDLink v1 using sensor/sub-sensor indices.
            """
            while not self.stopped.wait(0.2):
                sensor_data = self.hsd_link.get_sensor_data(self.d_id, self.s_id, self.ss_id)
                if sensor_data is not None:
                    self.data_reader.feed_data(DataClass(self.comp_name, sensor_data[1]))
                    if self.sensor_data_file is not None:
                        self.sensor_data_file.write(sensor_data[1])
   
    class ReadSerialDataThread(Thread):
        """
        Thread that continuously reads serial packets and dispatches payloads.

        Parameters
        ----------
        hsd_link : HSDLink_v2_Serial
            Serial link instance providing `get_serial_data()` and channels.

        Notes
        -----
        Validates channel counters to detect streaming errors and writes raw data
        to files when configured in `data_reader_params`.
        """

        def __init__(self, hsd_link, controller, sig_streaming_error=None):
            Thread.__init__(self)
            self.hsd_link = hsd_link
            self.name = "data_reader_thread"
            self.stop_event = Event()
            self.data_reader_params = None
            self.sig_streaming_error = sig_streaming_error
            self.controller = controller    
            self.prev_cnts = []

        def set_data_reader_params(self, data_reader_params):
            """
            Configure per-channel data readers and optional file sinks.

            Parameters
            ----------
            data_reader_params : dict
                Dictionary keyed by channel number containing entries:
                `{"comp_name", "data_reader", "file"}`.
            """
            self.data_reader_params = data_reader_params
            self.prev_cnts = [0] * len(data_reader_params)

        def set_sig_streaming_error(self, sig_streaming_error):
            """
            Set the UI error signal used to report serial streaming issues.
            """
            self.sig_streaming_error = sig_streaming_error

        def run(self):
            """
            Read and dispatch serial data packets until the stop flag is set.

            Notes
            -----
            - Checks per-channel counters for integrity.
            - Forwards payload to `data_reader.feed_data` and writes to file.
            - Flushes the link and closes files on exit.
            """
            while not self.stop_event.is_set():
                try:
                    pkt = self.hsd_link.get_serial_data()
                    if pkt is None:
                        continue
                    data = pkt.data
                    if pkt.header.cr == 0 and len(data) > 0:
                        curr_cnt = struct.unpack("=i", data[0:4])[0]
                        data_ch = pkt.header.ch_num                        
                        comp_name = self.data_reader_params[data_ch].get("comp_name")
                        self.data_reader_params[data_ch].get("data_reader").feed_data(DataClass(comp_name, data[4:]))
                        file = self.data_reader_params[data_ch].get("file")
                        if file is not None:
                            if not file.closed:
                                file.write(data)
                        self.prev_cnts[data_ch] = curr_cnt
                except HSDLinkV2SerialError as e:
                    if self.stop_event.is_set():
                        break
                    error_msg = ("No data from Serial Link.\n"
                                  "The PC is overloaded or running too many processes.\n"
                                  "Close other applications and run only the datalog application, then restart the acquisition.\n"
                                  "Have a look in {} log file for more detailed info."
                                  .format(log_file_name if log_file_name is not None else "application")
                                )
                    log.error(error_msg)
                    log.exception("HSDLinkV2SerialError caught while receiving serial data")
                    self.hsd_link.stop_log(self.controller.device_id)
                    self.hsd_link.flush()
                    # self.controller.stop_log()
                    if self.sig_streaming_error is not None:
                        self.sig_streaming_error.emit(True, error_msg)
                except Exception as e:
                    if self.stop_event.is_set():
                        break
                    log.error(f"Serial reader unexpected error: {e}")
                    log.exception(e)
                    break

            try:
                self.hsd_link.flush()
            except Exception:
                pass
            time.sleep(1)
            file = self.data_reader_params[0].get("file")
            if file is not None:
                file.close()

        def stop(self):
            """
            Request thread termination.
            """
            self.stop_event.set()

    def __init__(self, parent=None):
        super().__init__(parent)
        # HSD
        self.hsd = None
        self.hsd_link = None
        self.is_hsd_link_up = False
        self.is_logging = False
        self.is_detecting = False
        self.automode_enabled = False  # False:DISABLED, True:ENABLED
        self.automode_status = AutomodeStatus.AUTOMODE_UNSTARTED
        self.curr_bandwidth = 0
        self.config_error_dict = {}
        self.enabled_stream_comp_set = set()
        self.save_files_flag = True
        self.auto_started = False
        # Motor Control
        self.mcp_is_connected = False
        self.is_motor_started = False  # @is_motor_started saves motor state
        self.mcp_fast_telemetries_state = FastTelemetryStateEnum.MCP_FT_DISABLE
        self.mc_comp_name = "motor_controller"
        self.mc_start_cmd_name = "start_motor"
        self.mc_stop_cmd_name = "stop_motor"
        self.mc_ack_fault_cmd_name = "ack_fault"
        self.mc_motor_speed_prop_name = "motor_speed"
        self.mc_speed_req_name = "speed"
        # DataToolkit
        self.dt_plugins_folder_path = None
        # Serial communication
        self.data_reader_params = {}
        self.MAX_HSD_SRL_BANDWIDTH = 6000000
        self.MAX_HSD_BANDWIDTH = self.MAX_HSD_SRL_BANDWIDTH


        self.refresh()

    def is_com_ok(self):
        """
        Return whether the device communication link is up.

        Returns
        -------
        bool
            True if the HSD link has been initialized successfully.
        """
        return self.is_hsd_link_up

    # HSD
    def get_logging_status(self):
        """
        Check if logging is currently active.

        Returns
        -------
        bool
            True when logging session is active.
        """
        return self.is_logging

    def get_device_formatted_name(self, device):
        """
        Build a human-readable device label from status or link info.

        Parameters
        ----------
        device : dict | object
            Device status dictionary for v2 or device object for v1/serial.

        Returns
        -------
        str | None
            Formatted label including alias, serial/part number, FW name/version.
        """
        if isinstance(device, dict) and "devices" in device:
            fw_info_tmp = [
                c
                for c in device["devices"][0]["components"]
                if list(c.keys()) != [] and "firmware_info" in list(c.keys())[0]
            ]
            if len(fw_info_tmp) == 1:
                fw_info = fw_info_tmp[0]["firmware_info"]
                d_alias = fw_info["alias"]
                d_sn = "N/A"
                if "serial_number" in fw_info:
                    d_sn = fw_info["serial_number"]
                elif "part_number" in fw_info:
                    d_sn = fw_info["part_number"]
                d_fw_name = fw_info["fw_name"]
                d_fw_version = fw_info["fw_version"]
                return f"({d_alias}) - [{d_sn}] {d_fw_name} v{d_fw_version}"
            else:
                if "board_id" in device["devices"][0]:
                    b_id = device["devices"][0]["board_id"]
                    if b_id == 14:
                        d_alias = "STWIN.box"
                    if b_id == 13:
                        d_alias = "SensorTile.box PRO"
                    return d_alias
        elif isinstance(self.hsd_link, HSDLink_v1):
            return (
                f"{device.device_info.alias} - [{device.device_info.part_number}] "
                f"{device.device_info.fw_name} v{device.device_info.fw_version}"
            )
        elif self.is_hsd_link_serial():
            return f"[{device.device}] - {device.description}"

    def enable_start_log_button(self):
        """
        Ask UI to enable the Start button.
        """
        self.sig_lock_start_button.emit(False, "")

    def disable_start_log_button(self):
        """
        Ask UI to disable the Start button, providing a reason.

        Notes
        -----
        Uses "no sensors enabled" as the default message.
        """
        self.sig_lock_start_button.emit(True, "no sensors enabled")

    def refresh(self):
        """
        Initialize or reinitialize the HSD link and reset controller state.

        Notes
        -----
        - Closes any previous link.
        - Creates a new link via `HSDLink.create_hsd_link()`.
        - Resets threads, readers, file handles, and ISPU metadata.
        - Emits `sig_com_init_error` on errors without raising.
        """
        try:
            if self.hsd_link is not None:
                self.hsd_link.close()
            hsd_link_factory = HSDLink()
            self.hsd_link = hsd_link_factory.create_hsd_link()


            if self.hsd_link is not None:
                self.is_hsd_link_up = True
        except Exception as err:
            log.error(f"Error: {err}")
            if self.hsd_link is not None:
                self.hsd_link.close()
            self.is_hsd_link_up = False
            self.sig_com_init_error.emit()
        self.sensors_threads = []
        self.threads_stop_flags = []
        self.sensor_data_files = []
        self.data_readers = []
        # self.ispu_output_format = None
        # self.ispu_output_format_path = None
        self.mlc_ispu_configs = {}
        self.log_msg = ""

    def get_device_list(self):
        """
        Retrieve available devices from the active link.

        Returns
        -------
        list
            List of device descriptors or an empty list if link is missing.
        """
        devices = []
        if self.hsd_link is not None:
            devices = self.hsd_link.get_devices()
        return devices

    def get_device_presentation_string(self, d_id=0):
        """
        Return a presentation string for the selected device.

        Parameters
        ----------
        d_id : int, optional
            Device index, by default 0.

        Returns
        -------
        str | None
            A presentation string for v2 links; `None` for v1.
        """
        if isinstance(self.hsd_link, HSDLink_v1):
            return None
        return self.hsd_link.get_device_presentation_string(d_id)

    def get_device_info(self, d_id=0):
        """
        Get the device info dictionary.
        """
        return self.hsd_link.get_device_info(d_id)

    def get_firmware_info(self, d_id=0):
        """
        Get the firmware info dictionary for the device.
        """
        return self.hsd_link.get_firmware_info(d_id)

    def get_acquisition_info(self, d_id = 0):
        return self.hsd_link.get_acquisition_info(d_id)

    def get_device_status(self):
        """
        Retrieve the full device status (Twin) from firmware.
        """
        return self.hsd_link.get_device_status(self.device_id)

    def load_device_template(self, board_id, fw_id):
        """
        Load a DTDL device template matching `board_id` and `fw_id`.

        Parameters
        ----------
        board_id : int
            Board identifier reported by the device.
        fw_id : int
            Firmware identifier reported by the device.

        Notes
        -----
        - Emits `sig_dtm_loading_started` and `sig_dtm_loading_completed`.
        - Chooses template variant based on firmware name normalization.
        - Sets the template on both controller and link.
        """
        self.sig_dtm_loading_started.emit()
        dev_template_json = DeviceCatalogManager.query_dtdl_model(board_id, fw_id)
        if dev_template_json == "":
            log.error("Connected device not supported (Unrecognized board_id, fw_id)")
        if isinstance(dev_template_json, dict):
            fw_name = (
                self.hsd_link.get_firmware_info(self.device_id).get("firmware_info").get("fw_name")
            )
            reformatted_fw_name = "N/A"
            if fw_name is not None:
                splitted_fw_name = fw_name.lower().split("-")
                reformatted_fw_name = "".join(
                    [splitted_fw_name[0]] + [f.capitalize() for f in splitted_fw_name[1:]]
                )
            for dt in dev_template_json:
                if reformatted_fw_name.lower() in dev_template_json[dt][0].get("@id").lower():
                    dev_template_json = dev_template_json[dt]
                    break
        super().load_local_device_template(dev_template_json)
        self.hsd_link.set_device_template(dev_template_json)
        self.sig_dtm_loading_completed.emit()

    def load_local_device_template(self, dev_template_json):
        """
        Load a DTDL template from a local JSON file path.

        Parameters
        ----------
        dev_template_json : str
            Path to the DTDL JSON file.
        """
        with open(dev_template_json, "r", encoding="utf-8") as json_file:
            dev_template_json = json.load(json_file)
            json_file.close()
        super().load_local_device_template(dev_template_json)
        self.hsd_link.set_device_template(dev_template_json)

    def add_custom_device_template(self, input_dt_file_path, board_id=255, fw_id=255):
        """
        Add a custom DTDL template to the catalog.

        Parameters
        ----------
        input_dt_file_path : str
            Path to the DTDL JSON file to add.
        board_id : int, optional
            Custom board identifier, by default 255.
        fw_id : int, optional
            Custom firmware identifier, by default 255.
        """
        with open(input_dt_file_path, "r", encoding="utf-8") as json_file:
            dev_template_json = json.load(json_file)
            dtdl_model_name = os.path.splitext(os.path.basename(input_dt_file_path))[0]
            json_file.close()
            dev_template_json_str = json.dumps(dev_template_json)
            DeviceCatalogManager.add_dtdl_model(
                board_id, fw_id, dtdl_model_name, dev_template_json_str
            )

    def is_sensor_enabled(self, comp_name, d_id=0):
        """
        Return whether a given sensor component is enabled.
        """
        return self.hsd_link.get_sensor_enable(d_id, comp_name)

    def get_component_status(self, comp_name):
        """
        Get the current status for a specific component.

        Parameters
        ----------
        comp_name : str
            Component name.

        Returns
        -------
        dict
            Status dictionary containing component properties.
        """
        return self.hsd_link.get_component_status(self.device_id, comp_name)

    def __get_property_enum_value(self, prop_name, comp_status, comp_interface):
        """
        Retrieve the value of a enumerative property from the component status and interface.
        Args:
            prop_name (str): The name of the property to retrieve.
            comp_status (dict): A dictionary containing the status of various components.
            comp_interface (object): An object representing the component interface, which
                contains the property schema.
        Returns:
            The value of the property if it exists and has an associated schema.
        """
        if prop_name in comp_status:
            prop_index = comp_status[prop_name]
            prop_schema = [c for c in comp_interface.contents if c.name == prop_name][0].schema
            if not isinstance(prop_schema, ContentSchema):
                return prop_index
            prop_value = prop_schema.enum_values[prop_index].enum_value
            return prop_value
        else:
            return None

    def __get_hsd_comp_property_enum_number_value(self, prop_name, comp_status, comp_interface):
        """
        Resolve a numeric value for an enum-like property from status/schema.

        Parameters
        ----------
        prop_name : str
            Property name to resolve (e.g., "odr", "fs").
        comp_status : dict
            Component status dictionary containing current values.
        comp_interface : object
            DTDL interface providing the enum schema mapping.

        Returns
        -------
        int | float | None
            Numeric value if resolvable, else `None`.
        """
        if prop_name in comp_status:
            prop_index = comp_status[prop_name]
            prop_schema = [c for c in comp_interface.contents if c.name == prop_name][0].schema
            if not isinstance(prop_schema, ContentSchema):
                return prop_index
            prop_enum_dname = prop_schema.enum_values[prop_index].display_name
            prop_enum_value_schema = prop_schema.value_schema            
            prop_value = prop_enum_dname if isinstance(prop_enum_dname, str) else prop_enum_dname.en
            prop_value = prop_value.replace(',','.')
            if prop_enum_value_schema == SchemaEnum.INTEGER:
                try:
                    return float(prop_value)
                except ValueError as e:
                    print(e)
                    return prop_index
            else:
                return prop_value
        else:
            return None

    def __get_hsd_comp_property_enum_string_value(self, prop_name, comp_status, comp_interface):
        """
        Resolve a string label for an enum-like property from status/schema.

        Parameters
        ----------
        prop_name : str
            Property name to resolve (e.g., "resolution", "ranging_mode").
        comp_status : dict
            Component status dictionary containing current values.
        comp_interface : object
            DTDL interface providing the enum schema mapping.

        Returns
        -------
        str | None
            String label if resolvable, else `None`.
        """
        if prop_name in comp_status:
            prop_index = comp_status[prop_name]
            prop_schema = [c for c in comp_interface.contents if c.name == prop_name][0].schema
            if not isinstance(prop_schema, ContentSchema):
                return prop_index
            prop_enum_dname = prop_schema.enum_values[prop_index].display_name
            prop_value = prop_enum_dname if isinstance(prop_enum_dname, str) else prop_enum_dname.en
            return prop_value
        else:
            return None

    def __get_mems_sensor_odr(self, comp_status, comp_interface):
        ret = self.__get_hsd_comp_property_enum_number_value("odr", comp_status, comp_interface)
        if ret is not None:
            return ret
        return 1

    def __get_ranging_sensor_odr(self, comp_status):
        """
        Get ODR for ranging sensors using raw status fields.

        Parameters
        ----------
        comp_status : dict
            Component status for the ranging sensor.

        Returns
        -------
        int | float | None
            ODR value if available, otherwise `None`.
        """
        if "odr" in comp_status:
            odr_value = comp_status["odr"]
            return float(odr_value)
        return None

    def __get_presence_sensor_odr(self, comp_status, comp_interface):
        """
        Get ODR for presence sensors from enum schema.

        Parameters
        ----------
        comp_status : dict
            Component status.
        comp_interface : object
            DTDL interface.

        Returns
        -------
        int | float | None
            ODR value if available, else `None`.
        """
        return self.__get_hsd_comp_property_enum_number_value("odr", comp_status, comp_interface)

    def __get_light_sensor_odr(self, comp_status):
        """
        Compute effective ODR for light sensors using intermeasurement time.

        Parameters
        ----------
        comp_status : dict
            Component status including "intermeasurement_time".

        Returns
        -------
        float | None
            ODR value as 1/intermeasurement_time if available, else `None`.
        """
        if "intermeasurement_time" in comp_status:
            extime_value = comp_status["exposure_time"] / 1000
            itime_value = comp_status["intermeasurement_time"]
            if itime_value > extime_value + 6:
                return float(1 / (itime_value))
            else:
                return float(1 / (extime_value + 6))
        return None

    def __get_light_sensor_channel1_gain(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value(
            "channel1_gain", comp_status, comp_interface
        )

    def __get_light_sensor_channel2_gain(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value(
            "channel2_gain", comp_status, comp_interface
        )

    def __get_light_sensor_channel3_gain(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value(
            "channel3_gain", comp_status, comp_interface
        )

    def __get_light_sensor_channel4_gain(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value(
            "channel4_gain", comp_status, comp_interface
        )

    def __get_light_sensor_channel5_gain(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value(
            "channel5_gain", comp_status, comp_interface
        )

    def __get_light_sensor_channel6_gain(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value(
            "channel6_gain", comp_status, comp_interface
        )

    def __get_powermeter_sensor_odr(self, comp_status, comp_interface):
        ret = self.__get_hsd_comp_property_enum_number_value(
            "adc_conversion_time", comp_status, comp_interface
        )
        if ret is not None:
            return float(1000000 / float(ret))
        return None

    def __get_audio_sensor_odr(self, comp_status, comp_interface):
        return self.__get_mems_sensor_odr(comp_status, comp_interface)

    def __get_mems_sensor_fs(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value("fs", comp_status, comp_interface)

    def __get_audio_sensor_aop(self, comp_status, comp_interface):
        return self.__get_hsd_comp_property_enum_number_value("aop", comp_status, comp_interface)

    def __get_sensor_unit(self, prop_w_unit_name, comp_status, comp_interface):
        """
        Resolve display unit string from a property with unit metadata.

        Parameters
        ----------
        prop_w_unit_name : str
            Property name carrying unit info (e.g., "fs", "aop").
        comp_status : dict
            Component status containing the property.
        comp_interface : object
            DTDL interface with schema and unit descriptors.

        Returns
        -------
        str
            Unit symbol or empty string if not resolvable.
        """
        if prop_w_unit_name in comp_status:
            prop_content = [c for c in comp_interface.contents if c.name == prop_w_unit_name][0]

            if prop_content.unit is not None:
                unit = prop_content.unit
            elif prop_content.display_unit is not None:
                unit = (
                    prop_content.display_unit
                    if isinstance(prop_content.display_unit, str)
                    else prop_content.display_unit.en
                )

            unit_dict = UnitMap().unit_dict
            if unit in unit_dict:
                unit = unit_dict[unit]

            return unit
        return ""

    def __get_mems_sensor_unit(self, comp_status, comp_interface):
        """
        Get unit for MEMS sensors from their full-scale property.

        Parameters
        ----------
        comp_status : dict
            Component status.
        comp_interface : object
            DTDL interface.

        Returns
        -------
        str
            Unit symbol or empty string.
        """
        return self.__get_sensor_unit("fs", comp_status, comp_interface)

    def __get_audio_sensor_unit(self, comp_status, comp_interface):
        """
        Get unit for audio sensors from their AOP property.

        Parameters
        ----------
        comp_status : dict
            Component status.
        comp_interface : object
            DTDL interface.

        Returns
        -------
        str
            Unit symbol or empty string.
        """
        return self.__get_sensor_unit("aop", comp_status, comp_interface)

    def __get_ranging_sensor_unit(self, comp_status, comp_interface):
        """
        Get display unit for ranging sensors.

        Parameters
        ----------
        comp_status : dict
            Component status dictionary.
        comp_interface : object
            DTDL interface for the component.

        Returns
        -------
        str
            Unit symbol if known, otherwise an empty string.

        Notes
        -----
        Not implemented: currently logs context and returns an empty string.
        """
        # Not implemented: log context and return empty unit string
        _ = comp_interface  # Unused parameter
        try:
            status_keys = list(comp_status.keys()) if isinstance(comp_status, dict) else []
            log.warning(
                "Not implemented: ranging sensor unit extraction; status_keys=%s (returning '')",
                status_keys,
            )
        except Exception:
            pass
        return ""

    def __get_ranging_sensor_resolution(self, comp_status, comp_interface):
        """
        Get resolution label for ranging sensors from enum schema.

        Parameters
        ----------
        comp_status : dict
            Component status.
        comp_interface : object
            DTDL interface.

        Returns
        -------
        str | None
            Resolution label if available, else `None`.
        """
        return self.__get_hsd_comp_property_enum_string_value(
            "resolution", comp_status, comp_interface
        )

    def __get_ranging_sensor_ranging_mode(self, comp_status, comp_interface):
        """
        Get ranging mode label for ranging sensors from enum schema.

        Parameters
        ----------
        comp_status : dict
            Component status.
        comp_interface : object
            DTDL interface.

        Returns
        -------
        str | None
            Mode label if available, else `None`.
        """
        return self.__get_hsd_comp_property_enum_string_value(
            "ranging_mode", comp_status, comp_interface
        )

    def __get_presence_sensor_avg_tobject_num(self, comp_status, comp_interface):
        """
        Get averaging window for object temperature in presence sensors.
        """
        return self.__get_hsd_comp_property_enum_number_value(
            "avg_tobject_num", comp_status, comp_interface
        )

    def __get_presence_sensor_avg_tambient_num(self, comp_status, comp_interface):
        """
        Get averaging window for ambient temperature in presence sensors.
        """
        return self.__get_hsd_comp_property_enum_number_value(
            "avg_tambient_num", comp_status, comp_interface
        )

    def __get_presence_sensor_lpf_p_m_bandwidth(self, comp_status, comp_interface):
        """
        Get LPF bandwidth for presence P-M (presence-motion) channel.
        """
        return self.__get_hsd_comp_property_enum_number_value(
            "lpf_p_m_bandwidth", comp_status, comp_interface
        )

    def __get_presence_sensor_lpf_p_bandwidth(self, comp_status, comp_interface):
        """
        Get LPF bandwidth for presence P (presence) channel.
        """
        return self.__get_hsd_comp_property_enum_number_value(
            "lpf_p_bandwidth", comp_status, comp_interface
        )

    def __get_presence_sensor_lpf_m_bandwidth(self, comp_status, comp_interface):
        """
        Get LPF bandwidth for presence M (motion) channel.
        """
        return self.__get_hsd_comp_property_enum_number_value(
            "lpf_m_bandwidth", comp_status, comp_interface
        )

    def __get_presence_sensor_compensation_type(self, comp_status, comp_interface):
        """
        Get compensation type label for presence sensors from enum schema.
        """
        return self.__get_hsd_comp_property_enum_string_value(
            "compensation_type", comp_status, comp_interface
        )

    def __get_mc_telemetry_unit(self, telemetry_status, comp_interface):
        """
        Get display unit for Motor Control telemetry fields.

        Parameters
        ----------
        telemetry_status : dict
            Telemetry status dictionary.
        comp_interface : object
            DTDL interface for telemetry component.

        Notes
        -----
        Not implemented: currently logs context for future implementation.
        """
        # Not implemented: log context for future implementation
        _ = comp_interface  # Unused parameter
        try:
            status_keys = (
                list(telemetry_status.keys()) if isinstance(telemetry_status, dict) else []
            )
            log.warning(
                "Not implemented: MC telemetry unit extraction; status_keys=%s",
                status_keys,
            )
        except Exception:
            pass

    def get_description_string(self, content):
        """
        Return a localized description string from a DTDL content object.

        Parameters
        ----------
        content : object
            DTDL content element possibly exposing `description` as str or
            localized object (e.g., with `.en`).

        Returns
        -------
        str | None
            Description string if available, else `None`.
        """
        if content.description is not None:
            return (
                content.description
                if isinstance(content.description, str)
                else content.description.en
            )
        return None

    def get_plot_params(self, comp_name, comp_type, comp_interface, comp_status):
        """
        Build plotting parameters from DTDL interface and component status.

        Parameters
        ----------
        comp_name : str
            Component name.
        comp_type : ComponentType
            Component type enum (Sensor/Algorithm).
        comp_interface : object
            DTDL interface object describing component properties.
        comp_status : dict
            Device status dictionary for components.

        Returns
        -------
        SensorPlotParams | FFTAlgPlotParams | AnomalyDetectorModelPlotParams |
        ClassificationModelPlotParams | None
            Plot parameter object describing labels, units, dimensions, etc., or
            `None` if not applicable.

        Notes
        -----
        - Supports MEMS, Audio, Ranging, Light, Presence, Powermeter sensors.
        - Supports FFT, Anomaly Detector, and Classifier algorithms.
        - Maintains compatibility with older firmware lacking categories.
        """
        if comp_status is not None and comp_name in comp_status:
            if comp_type.name == ComponentType.SENSOR.name:
                comp_status_value = comp_status[comp_name]
                enabled = comp_status_value["enable"]
                s_category = comp_status_value.get("sensor_category")

                dimension = comp_status_value.get("dim", 1)

                if s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_MEMS.value:
                    odr = self.__get_mems_sensor_odr(comp_status_value, comp_interface)
                    unit = self.__get_mems_sensor_unit(comp_status_value, comp_interface)
                    return SensorMemsPlotParams(comp_name, enabled, odr, dimension, unit)
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_AUDIO.value:
                    odr = self.__get_audio_sensor_odr(comp_status_value, comp_interface)
                    unit = self.__get_audio_sensor_unit(comp_status_value, comp_interface)
                    return SensorAudioPlotParams(comp_name, enabled, odr, dimension, unit)
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_RANGING.value:
                    resolution = comp_status_value.get("resolution")
                    output_format = comp_status_value.get("output_format")
                    return SensorRangingPlotParams(
                        comp_name, enabled, dimension, resolution, output_format
                    )
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_LIGHT.value:
                    return SensorLightPlotParams(comp_name, enabled, dimension)
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_PRESENCE.value:
                    plots_params_dict = {}
                    embedded_compensation = comp_status[comp_name].get("embedded_compensation")
                    software_compensation = comp_status[comp_name].get("software_compensation")
                    plots_params_dict["Ambient"] = PlotPAmbientParams(comp_name, enabled, 1)
                    plots_params_dict["Object"] = PlotPObjectParams(
                        comp_name, enabled, 4, embedded_compensation, software_compensation
                    )
                    plots_params_dict["Presence"] = PlotPPresenceParams(
                        comp_name, enabled, 1, embedded_compensation, software_compensation
                    )
                    plots_params_dict["Motion"] = PlotPMotionParams(
                        comp_name, enabled, 1, embedded_compensation, software_compensation
                    )
                    return SensorPresenscePlotParams(comp_name, enabled, plots_params_dict)
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_CAMERA.value:
                    pixel_format = comp_status_value.get("pixel_format")
                    resolution = comp_status_value.get("resolution")
                    return SensorCameraPlotParams(comp_name, enabled, dimension, 320, 240, pixel_format, resolution)
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_POWERMETER.value:
                    plots_params_dict = {}
                    plots_params_dict["Voltage"] = SensorPlotParams(comp_name, enabled, 1, "mV")
                    plots_params_dict["Voltage(VShunt)"] = SensorPlotParams(
                        comp_name, enabled, 1, "mV"
                    )
                    plots_params_dict["Current"] = SensorPlotParams(comp_name, enabled, 1, "A")
                    plots_params_dict["Power"] = SensorPlotParams(comp_name, enabled, 1, "mW")
                    return SensorPowerPlotParams(comp_name, enabled, plots_params_dict)
                else:  # Maintain compatibility with OLD versions
                    # (< SensorManager v3 [NO SENSOR CATEGORIES])
                    odr = self.__get_mems_sensor_odr(comp_status_value, comp_interface)
                    unit = self.__get_mems_sensor_unit(comp_status_value, comp_interface)
                    if unit == "":
                        unit = self.__get_audio_sensor_unit(comp_status_value, comp_interface)
                    return SensorMemsPlotParams(comp_name, enabled, odr, dimension, unit)

            elif comp_type.name == ComponentType.ALGORITHM.name:
                comp_status_value = comp_status[comp_name]
                enabled = comp_status_value["enable"]
                if "algorithm_type" in comp_status_value:
                    alg_type = comp_status_value["algorithm_type"]
                else:
                    alg_type = 0

                if alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_FFT.value:
                    return FFTAlgPlotParams(
                        comp_name,
                        enabled,
                        fft_len=comp_status_value["fft_length"],
                        fft_sample_freq=comp_status_value["fft_sample_freq"],
                        y_label="db",
                    )
                elif alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_ANOMALY_DETECTOR.value:
                    return AnomalyDetectorModelPlotParams(comp_name, enabled)
                elif alg_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_CLASSIFIER.value:
                    return ClassificationModelPlotParams(
                        comp_name, enabled, num_of_class=comp_status_value["dim"]
                    )
        return None

    def fill_component_status(self, comp_name):
        """
        Query and store a component's status, updating UI widgets.

        Parameters
        ----------
        comp_name : str
            Component name to refresh.
        """
        try:
            comp_status = self.get_component_status(comp_name)
            if comp_status is not None and comp_name in comp_status:
                self.components_status[comp_name] = comp_status[comp_name]
                self.sig_component_updated.emit(comp_name, comp_status[comp_name])
            else:
                log.warning(
                    f"The component [{comp_name}] defined in DeviceTemplate has not a Twin in "
                    "Device Status from the FW"
                )
                self.sig_component_updated.emit(comp_name, None)
                self.remove_component_config_widget(comp_name)
        except:
            log.warning(
                f"The component [{comp_name}] defined in DeviceTemplate has not a Twin in "
                "Device Status from the FW"
            )
            self.remove_component_config_widget(comp_name)
            return

    def update_component_status(self, comp_name, comp_type=ComponentType.OTHER):
        """
        Update internal status for a component and emit UI update signals.

        Parameters
        ----------
        comp_name : str
            Component name.
        comp_type : ComponentType | str, optional
            Component type enum or name, by default `ComponentType.OTHER`.
        """
        comp_status = self.get_component_status(comp_name)
        if comp_status is not None and comp_name in comp_status:
            self.components_status[comp_name] = comp_status[comp_name]
            if isinstance(comp_type, str):
                ct = comp_type
            else:
                ct = comp_type.name
            if ct == ComponentType.SENSOR.name:
                plot_params = self.get_plot_params(
                    comp_name, comp_type, self.components_dtdl[comp_name], comp_status
                )
                self.sig_sensor_component_updated.emit(comp_name, plot_params)
                self.check_hsd_bandwidth()
            elif ct == ComponentType.ALGORITHM.name:
                plot_params = self.get_plot_params(
                    comp_name, comp_type, self.components_dtdl[comp_name], comp_status
                )
                self.sig_algorithm_component_updated.emit(comp_name, plot_params)
            self.sig_component_updated.emit(comp_name, comp_status[comp_name])
        else:
            log.warning(
                f"The component [{comp_name}] defined in DeviceTemplate has not a Twin in "
                "Device Status from the FW"
            )
            self.sig_component_updated.emit(comp_name, None)

    def update_pipeline_component_status(self):
        """
        Expand component status values for DataToolkit pipeline consumption.

        Notes
        -----
        Enriches `components_status` with numeric/enum-expanded values such as
        ODR, FS, AOP, gains, resolutions, and modes, depending on category.
        """
        if self.data_pipeline is not None:
            components_status_exp = copy.deepcopy(self.components_status)
            for cs in components_status_exp:
                comp_interface = self.components_dtdl[cs]
                comp_status_value = self.components_status[cs]
                s_category = comp_status_value.get("sensor_category")

                if s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_MEMS.value:
                    components_status_exp[cs]["odr"] = self.__get_mems_sensor_odr(
                        comp_status_value, comp_interface
                    )
                    components_status_exp[cs]["fs"] = self.__get_mems_sensor_fs(
                        comp_status_value, comp_interface
                    )
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_AUDIO.value:
                    components_status_exp[cs]["odr"] = self.__get_audio_sensor_odr(
                        comp_status_value, comp_interface
                    )
                    components_status_exp[cs]["aop"] = self.__get_audio_sensor_aop(
                        comp_status_value, comp_interface
                    )
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_RANGING.value:
                    components_status_exp[cs]["resolution"] = self.__get_ranging_sensor_resolution(
                        comp_status_value, comp_interface
                    )
                    components_status_exp[cs]["ranging_mode"] = (
                        self.__get_ranging_sensor_ranging_mode(comp_status_value, comp_interface)
                    )
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_LIGHT.value:
                    components_status_exp[cs]["channel1_gain"] = (
                        self.__get_light_sensor_channel1_gain(comp_status_value, comp_interface)
                    )
                    components_status_exp[cs]["channel2_gain"] = (
                        self.__get_light_sensor_channel2_gain(comp_status_value, comp_interface)
                    )
                    components_status_exp[cs]["channel3_gain"] = (
                        self.__get_light_sensor_channel3_gain(comp_status_value, comp_interface)
                    )
                    components_status_exp[cs]["channel4_gain"] = (
                        self.__get_light_sensor_channel4_gain(comp_status_value, comp_interface)
                    )
                    components_status_exp[cs]["channel5_gain"] = (
                        self.__get_light_sensor_channel5_gain(comp_status_value, comp_interface)
                    )
                    components_status_exp[cs]["channel6_gain"] = (
                        self.__get_light_sensor_channel6_gain(comp_status_value, comp_interface)
                    )
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_PRESENCE.value:
                    components_status_exp[cs]["odr"] = self.__get_presence_sensor_odr(
                        comp_status_value, comp_interface
                    )
                    components_status_exp[cs]["avg_tobject_num"] = (
                        self.__get_presence_sensor_avg_tobject_num(
                            comp_status_value, comp_interface
                        )
                    )
                    components_status_exp[cs]["avg_tambient_num"] = (
                        self.__get_presence_sensor_avg_tambient_num(
                            comp_status_value, comp_interface
                        )
                    )
                    components_status_exp[cs]["lpf_p_m_bandwidth"] = (
                        self.__get_presence_sensor_lpf_p_m_bandwidth(
                            comp_status_value, comp_interface
                        )
                    )
                    components_status_exp[cs]["lpf_p_bandwidth"] = (
                        self.__get_presence_sensor_lpf_p_bandwidth(
                            comp_status_value, comp_interface
                        )
                    )
                    components_status_exp[cs]["lpf_m_bandwidth"] = (
                        self.__get_presence_sensor_lpf_m_bandwidth(
                            comp_status_value, comp_interface
                        )
                    )
                    components_status_exp[cs]["compensation_type"] = (
                        self.__get_presence_sensor_compensation_type(
                            comp_status_value, comp_interface
                        )
                    )
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_CAMERA.value:
                    pass
                elif s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_POWERMETER.value:
                    components_status_exp[cs]["adc_conversion_time"] = (
                        self.__get_powermeter_sensor_odr(comp_status_value, comp_interface)
                    )
                else:  # Maintain compatibility with OLD versions
                    # (< SensorManager v3 [NO SENSOR CATEGORIES])
                    components_status_exp[cs]["odr"] = self.__get_mems_sensor_odr(
                        comp_status_value, comp_interface
                    )
                    components_status_exp[cs]["fs"] = self.__get_mems_sensor_fs(
                        comp_status_value, comp_interface
                    )

            self.data_pipeline.update_components_status(components_status_exp)

    def update_device_status(self):
        """
        Refresh and broadcast status for all components on the device.
        """
        dev_status = self.hsd_link.get_device_status(self.device_id)
        for c in dev_status["devices"][self.device_id]["components"]:
            c_dict = list(c.values())[0]
            c_name = list(c.keys())[0]
            c_type = c_dict.get("c_type", ComponentType.NONE)
            if c_type == DTDLUtils.ComponentTypeEnum.SENSOR.value:
                c_type = ComponentType.SENSOR
            elif c_type == DTDLUtils.ComponentTypeEnum.ALGORITHM.value:
                c_type = ComponentType.ALGORITHM
            elif c_type == DTDLUtils.ComponentTypeEnum.ACTUATOR.value:
                c_type = ComponentType.ACTUATOR
            elif c_type == DTDLUtils.ComponentTypeEnum.OTHER.value:
                c_type = ComponentType.OTHER
            self.update_component_status(c_name, c_type)

    def start_log(self, interface=1, acq_folder=None, sub_folder=True):
        """
        Start a logging session and plot threads when appropriate.

        Parameters
        ----------
        interface : int, optional
            Link interface index for v2 devices, by default 1.
        acq_folder : str | None, optional
            Custom acquisition folder path, if supported.
        sub_folder : bool, optional
            Whether to create a sub-folder in the acquisition directory.

        Notes
        -----
        - For serial links, starts plot threads before the device logging.
        - Emits `sig_logging(True, interface)` on success and starts pipeline.
        """
        if isinstance(self.hsd_link, HSDLink_v1):
            res = self.hsd_link.start_log(self.device_id, save_files=self.save_files_flag)
        else:
            for s in self.plot_widgets:
                s_plot = self.plot_widgets[s]
                c_name = s_plot.comp_name
                if c_name is not None:
                    c_status = self.get_component_status(c_name)
                    if c_status is not None:
                        self.components_status[c_name] = c_status[c_name]
            if self.is_hsd_link_serial():
                # In case of serial communication, plots are started before the log
                self.start_plots()
            res = self.hsd_link.start_log(
                self.device_id,
                interface,
                acq_folder=acq_folder,
                sub_folder=sub_folder,
                save_files=self.save_files_flag,
            )
        if res:
            self.sig_logging.emit(True, interface)
            if self.data_pipeline is not None:
                self.data_pipeline.start()
            self.sig_streaming_error.emit(False, "")
            self.is_logging = True

    def start_waiting_auto_log(self):
        """
        Emit the waiting-to-start auto-mode state.
        """
        self.sig_is_waiting_auto_start.emit(True)

    def stop_waiting_auto_log(self):
        """
        Clear the waiting-to-start auto-mode state.
        """
        self.sig_is_waiting_auto_start.emit(False)

    def start_idle_auto_log(self):
        """
        Emit the idle state for auto-mode.
        """
        self.sig_is_waiting_idle.emit(True)

    def stop_idle_auto_log(self):
        self.sig_is_waiting_idle.emit(False)

    def start_auto_log(self):
        self.sig_is_auto_started.emit(True)

    def start_auto_log_inner(self, interface=1, acq_folder=None, sub_folder=True):
        """
        Start logging triggered by auto-mode logic and emit inner signal.
        """
        self.start_log(interface, acq_folder, sub_folder)
        self.sig_is_auto_started_inner.emit(True)

    def start_detect(self):
        """
        Start detection mode via device logging, using interface 1 on v2.
        """
        if isinstance(self.hsd_link, HSDLink_v1):
            res = self.hsd_link.start_log(self.device_id)
        else:
            res = self.hsd_link.start_log(self.device_id, 1)
        if res:
            self.sig_detecting.emit(True)
            self.is_detecting = True

    def get_save_files_flag(self):
        """
        Return whether raw stream files should be saved during logging.
        """
        return self.save_files_flag

    def set_save_files_flag(self, status):
        """
        Set whether raw stream files should be saved.

        Parameters
        ----------
        status : bool
            True to persist `.dat` files, False to disable.
        """
        self.save_files_flag = status

    def __start_component_plot_serial(self, comp_status, comp_name):
        """
        Prepare data readers for serial link and optionally open `.dat` files.

        Parameters
        ----------
        comp_status : dict
            Status dictionary for the component.
        comp_name : str
            Component name.

        Notes
        -----
        Sets `data_reader_params` keyed by stream id for the serial thread.
        """
        c_enable = comp_status["enable"]

        if c_enable == True:
            c_stream_id = comp_status.get("stream_id")
            if c_stream_id is not None:
                if self.save_files_flag:
                    sensor_data_file_path = os.path.join(".", str(comp_name) + ".dat")
                    sensor_data_file = open(sensor_data_file_path, "wb+")
                    self.sensor_data_files.append(sensor_data_file)
                else:
                    sensor_data_file = None

                c_type = comp_status.get("c_type")
                # serial_dps = comp_status.get("serial_dps")
                dimensions = comp_status.get("dim", 1)
                sensitivity = comp_status.get("sensitivity", 1)
                spts = comp_status.get("samples_per_ts", 1)
                sample_size = TypeConversion.check_type_length(comp_status["data_type"])
                data_format = TypeConversion.get_format_char(comp_status["data_type"])

                interleaved_data = True
                raw_flat_data = False
                s_category = None

                if c_type == ComponentType.SENSOR.value:
                    if not isinstance(spts, int):
                        spts = spts["val"] if spts and "val" in spts else spts
                    s_category = comp_status.get("sensor_category")

                elif c_type == ComponentType.ALGORITHM.value:
                    spts = 0  # spts override (no timestamps in algorithms @ the moment)
                    algorithm_type = comp_status.get("algorithm_type")
                    if (
                        algorithm_type
                        == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_ANOMALY_DETECTOR.value
                    ):
                        dimensions = comp_status["dim"]
                    if algorithm_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_FFT.value:
                        dimensions = comp_status.get("fft_length")
                    if (
                        algorithm_type
                        == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_CLASSIFIER.value
                    ):
                        # Get  ai classifier sub properties
                        ai_classifier_sub_properties = comp_status[DTDLUtils.ST_BLE_STREAM]
                        dimensions = 0
                        for t in ai_classifier_sub_properties:
                            if t != 'id':
                            # Check enable condition
                                t_enabled = ai_classifier_sub_properties[t].get("enable")
                                if t_enabled:
                                    #get format 
                                    t_format = ai_classifier_sub_properties[t].get("format")
                                    dimensions += TypeConversion.check_type_length(t_format)
                    interleaved_data = False

                if "_ispu" in comp_name:
                    data_format = "b"
                    dimensions *= sample_size
                    sample_size = 1
                    raw_flat_data = True

                if s_category is not None:
                    if s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_RANGING.value:
                        raw_flat_data = True

                dr = HSD_Controller.DataReader(
                    self,
                    self.add_data_to_a_plot,
                    comp_name,
                    spts,
                    dimensions,
                    sample_size,
                    data_format,
                    sensitivity,
                    interleaved_data,
                    raw_flat_data,
                )
                self.data_readers.append(dr)

                self.data_reader_params[c_stream_id] = {
                    "comp_name": comp_name,
                    "data_reader": dr,
                    "file": sensor_data_file,
                }

    def __start_component_plots_hsddll(self, comp_status, comp_name, create_thread=False):
        """
        Prepare data readers and start sensor threads for non-serial links.

        Parameters
        ----------
        comp_status : dict
            Status dictionary for the component.
        comp_name : str
            Component name.
        create_thread : bool, optional
            Force thread creation for certain categories, by default False.
        """
        c_enable = comp_status["enable"]

        if c_enable == True:
            if self.save_files_flag:
                sensor_data_file_path = os.path.join(self.hsd_link.get_acquisition_folder(),(str(comp_name) + ".dat"))
                sensor_data_file = open(sensor_data_file_path, "wb+")
                self.sensor_data_files.append(sensor_data_file)
            stopFlag = Event()
            self.threads_stop_flags.append(stopFlag)
            
            c_type = comp_status.get("c_type")
            usb_dps = comp_status.get("usb_dps")
            dimensions = comp_status.get("dim", 1)
            sensitivity = comp_status.get("sensitivity", 1)
            spts = comp_status.get("samples_per_ts", 1)
            sample_size = TypeConversion.check_type_length(comp_status["data_type"])
            data_format = TypeConversion.get_format_char(comp_status["data_type"])
            s_category = None

            interleaved_data = True
            raw_flat_data = False

            if c_type == ComponentType.SENSOR.value:
                if not isinstance(spts, int):
                    spts = spts["val"] if spts and "val" in spts else spts
                s_category = comp_status.get("sensor_category")
                create_thread = True

            elif c_type == ComponentType.ALGORITHM.value:
                spts = 0  # spts override (no timestamps in algorithms @ the moment)
                algorithm_type = comp_status.get("algorithm_type")
                if (
                    algorithm_type
                    == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_ANOMALY_DETECTOR.value
                ):
                    dimensions = comp_status["dim"]
                if algorithm_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_FFT.value:
                    dimensions = comp_status.get("fft_length")
                if algorithm_type == DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_CLASSIFIER.value:
                    # Get  ai classifier sub properties
                    ai_classifier_sub_properties = comp_status[DTDLUtils.ST_BLE_STREAM]
                    dimensions = 0
                    for t in ai_classifier_sub_properties:
                        if t != "id":
                            # Check enable condition
                            t_enabled = ai_classifier_sub_properties[t].get("enable")
                            if t_enabled:
                                # get format
                                t_format = ai_classifier_sub_properties[t].get("format")
                                dimensions += TypeConversion.check_type_length(t_format)
                interleaved_data = False
                create_thread = True

            if "_ispu" in comp_name:
                data_format = "b"
                dimensions *= sample_size
                sample_size = 1
                raw_flat_data = True
                create_thread = True

            if s_category is not None:
                if s_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_RANGING.value:
                    raw_flat_data = True
                create_thread = True

            if create_thread == True:
                dr = HSD_Controller.DataReader(
                    self,
                    self.add_data_to_a_plot,
                    comp_name,
                    spts,
                    dimensions,
                    sample_size,
                    data_format,
                    sensitivity,
                    interleaved_data,
                    raw_flat_data,
                )
                self.data_readers.append(dr)

                if self.save_files_flag:
                    thread = self.SensorAcquisitionThread(
                        stopFlag,
                        self.hsd_link,
                        dr,
                        self.device_id,
                        comp_name,
                        sensor_data_file,
                        usb_dps,
                        self.sig_streaming_error,
                    )
                else:
                    thread = self.SensorAcquisitionThread(
                        stopFlag,
                        self.hsd_link,
                        dr,
                        self.device_id,
                        comp_name,
                        None,
                        usb_dps,
                        self.sig_streaming_error,
                    )
                thread.start()
                self.sensors_threads.append(thread)

    def start_plots(self):
        """
        Start plot-related threads and DataToolkit if configured.

        Notes
        -----
        - For v1 links, uses legacy acquisition thread per plot.
        - For serial v2, defers to the serial reader thread.
        - For non-serial v2, creates per-component threads.
        """
        if self.dt_plugins_folder_path is not None:
            # Initialize DataToolkit
            self.dataToolKit = HSD_DataToolkit(
                self.components_status, self.data_pipeline, self.sig_new_spt_data_ready
            )
            # self.consumer_thread.daemon = True
            self.dataToolKit.start()

        for s in self.plot_widgets:
            s_plot = self.plot_widgets[s]
            # create_thread = False

            if isinstance(self.hsd_link, HSDLink_v1):
                if self.save_files_flag:
                    sensor_data_file_path = os.path.join(
                        self.hsd_link.get_acquisition_folder(), (str(s_plot.comp_name) + ".dat")
                    )
                    sensor_data_file = open(sensor_data_file_path, "wb+")
                    self.sensor_data_files.append(sensor_data_file)
                stopFlag = Event()
                self.threads_stop_flags.append(stopFlag)

                dimensions = s_plot.n_curves
                sample_size = s_plot.sample_size
                spts = s_plot.spts
                data_format = s_plot.data_format

                dr = DataReader(
                    self.add_data_to_a_plot,
                    s_plot.comp_name,
                    spts,
                    dimensions,
                    sample_size,
                    data_format,
                )
                self.data_readers.append(dr)

                thread = self.SensorAcquisitionThread_test_v1(
                    stopFlag,
                    self.hsd_link,
                    dr,
                    self.device_id,
                    s_plot.s_id,
                    s_plot.ss_id,
                    s_plot.comp_name,
                    sensor_data_file,
                )
                thread.start()
                self.sensors_threads.append(thread)
            else:
                c_name = s_plot.comp_name
                if c_name is not None:
                    c_status_value = self.components_status.get(c_name)
                    if c_status_value.get("sensor_category") == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_RANGING.value:
                        # Ranging sensor: need to get updated status from device
                        c_status = self.get_component_status(c_name)
                        c_status_value = c_status[c_name]
                    if c_status_value is not None:
                        if self.is_hsd_link_serial():
                            self.__start_component_plot_serial(c_status_value, c_name)
                            self.sensors_threads[0].set_data_reader_params(self.data_reader_params)
                        else:
                            self.__start_component_plots_hsddll(c_status_value, c_name)

    def stop_log(self, interface=1):
        """
        Stop logging and persist acquisition metadata and auxiliary files.

        Parameters
        ----------
        interface : int, optional
            Interface index for the `sig_logging` emission, by default 1.
            this parameter is not needed to stop the logging, but it is
            maintained for compatibility with start_log signature.
        """
        _ = interface  # Unused parameter
        if self.is_logging == True:
            self.hsd_link.stop_log(self.device_id)
            if isinstance(self.hsd_link, HSDLink_v1):
                if self.save_files_flag:
                    self.hsd_link.save_json_device_file(self.device_id)
                    self.hsd_link.save_json_acq_info_file(self.device_id)
            else:

                time.sleep(0.5)
                if self.save_files_flag:
                    self.hsd_link.save_json_acq_info_file(self.device_id)
                    self.hsd_link.save_json_device_file(self.device_id)
                    
                    self.__copy_mlc_ispu_config_files()

                    # if self.ispu_output_format_path is not None:
                    #     shutil.copyfile(
                    #         self.ispu_output_format_path,
                    #         os.path.join(
                    #             self.hsd_link.get_acquisition_folder(), "ispu_output_format.json"
                    #         ),
                    #     )
                    #     log.info("ispu_output_format.json File correctly saved")
                    
                    # if self.ispu_ucf_file_path is not None:
                    #     ucf_filename = os.path.basename(self.ispu_ucf_file_path)
                    #     shutil.copyfile(
                    #         self.ispu_ucf_file_path,
                    #         os.path.join(self.hsd_link.get_acquisition_folder(), ucf_filename),
                    #     )
                    #     log.info(f"{ucf_filename} File correctly saved")

                self.update_component_status("acquisition_info", ComponentType.OTHER)
                self.sig_logging.emit(False, 1)
                if self.data_pipeline is not None:
                    self.data_pipeline.stop()
                self.is_logging = False

    def stop_auto_log(self):
        """
        Clear the auto-mode started state.
        """
        self.sig_is_auto_started.emit(False)

    def stop_auto_log_inner(self, interface=1):
        """
        Stop logging triggered by auto-mode and emit inner signal.
        """
        if self.is_logging == True:
            self.sig_autologging_is_stopping.emit(True)
            self.hsd_link.stop_log(self.device_id)
            if isinstance(self.hsd_link, HSDLink_v1):
                if self.save_files_flag:
                    self.hsd_link.save_json_device_file(self.device_id)
                    self.hsd_link.save_json_acq_info_file(self.device_id)
            else:
                time.sleep(0.5)

                if self.save_files_flag:
                    self.hsd_link.save_json_acq_info_file(self.device_id)
                    self.hsd_link.save_json_device_file(self.device_id)
                    
                    self.__copy_mlc_ispu_config_files()

                    # if self.ispu_output_format_path is not None:
                    #     shutil.copyfile(
                    #         self.ispu_output_format_path,
                    #         os.path.join(
                    #             self.hsd_link.get_acquisition_folder(), "ispu_output_format.json"
                    #         ),
                    #     )
                    #     log.info("ispu_output_format.json File correctly saved")
                    # if self.ispu_ucf_file_path is not None:
                    #     ucf_filename = os.path.basename(self.ispu_ucf_file_path)
                    #     shutil.copyfile(
                    #         self.ispu_ucf_file_path,
                    #         os.path.join(self.hsd_link.get_acquisition_folder(), ucf_filename),
                    #     )
                    #     log.info(f"{ucf_filename} File correctly saved")
                self.update_component_status("acquisition_info", ComponentType.OTHER)
                self.sig_logging.emit(False, interface)
                if self.data_pipeline is not None:
                    self.data_pipeline.stop()
                self.is_logging = False
                self.sig_autologging_is_stopping.emit(False)
        self.sig_is_auto_started_inner.emit(False)
        self.is_logging = False

    def stop_detect(self):
        """
        Stop detection mode and persist acquisition metadata if enabled.
        """
        if self.is_detecting == True:
            self.hsd_link.stop_log(self.device_id)
            if isinstance(self.hsd_link, HSDLink_v1):
                if self.save_files_flag:
                    self.hsd_link.save_json_device_file(self.device_id)
                    self.hsd_link.save_json_acq_info_file(self.device_id)
            else:
                if self.save_files_flag:
                    self.hsd_link.save_json_device_file(self.device_id)
                    self.hsd_link.save_json_acq_info_file(self.device_id)
                    
                    self.__copy_mlc_ispu_config_files()
                            
                    # if self.ispu_output_format_path is not None:
                    #     shutil.copyfile(
                    #         self.ispu_output_format_path,
                    #         os.path.join(
                    #             self.hsd_link.get_acquisition_folder(), "ispu_output_format.json"
                    #         ),
                    #     )
                    #     log.info("ispu_output_format.json File correctly saved")
                    # if self.ispu_ucf_file_path is not None:
                    #     ucf_filename = os.path.basename(self.ispu_ucf_file_path)
                    #     shutil.copyfile(
                    #         self.ispu_ucf_file_path,
                    #         os.path.join(self.hsd_link.get_acquisition_folder(), ucf_filename),
                    #     )
                    #     log.info(f"{ucf_filename} File correctly saved")
                    self.update_component_status("acquisition_info", ComponentType.OTHER)
            self.sig_detecting.emit(False)
            self.is_detecting = False

    def stop_plots(self):
        """
        Stop all plot acquisition threads and move `.dat` files if needed.
        """
        if self.dt_plugins_folder_path is not None:
            # stop dataToolKit thread
            self.dataToolKit.stop()

        for sf in self.threads_stop_flags:
            sf.set()

        if not self.is_hsd_link_serial():
            for t in self.sensors_threads:
                t.join()

        if self.save_files_flag:
            acquisition_folder = self.hsd_link.get_acquisition_folder()
            for f in self.sensor_data_files:
                try:
                    fpath = f.name
                    f.close()
                    # Move the file to the acquisition folder if not already there
                    dest_path = os.path.join(acquisition_folder, os.path.basename(fpath))
                    if os.path.abspath(fpath) != os.path.abspath(dest_path):
                        shutil.move(fpath, dest_path)
                except Exception as e:
                    log.error(f"Error moving file {f.name}: {e}")
            self.sensor_data_files.clear()

    def plot_window_changed(self, plot_window_time):
        """
        Emit plot window time updates for listening widgets.

        Parameters
        ----------
        plot_window_time : float
            Plot window span in seconds.
        """
        self.sig_plot_window_time_updated.emit(plot_window_time)

    def get_plot_widget(self, comp_name):
        """
        Return the registered plot widget for a component, if any.
        """
        if comp_name in self.plot_widgets:
            return self.plot_widgets[comp_name]
        else:
            return None

    def add_plot_widget(self, plot_widget, enabled=None):
        """
        Register a plot widget and show/hide based on `enabled`.

        Parameters
        ----------
        plot_widget : QWidget
            Plot widget instance exposing `comp_name` and controls.
        enabled : bool | None, optional
            If provided, toggles initial visibility and controls accordingly.
        """
        self.plot_widgets[plot_widget.comp_name] = plot_widget
        if enabled is not None:
            if enabled:
                self.cconfig_widgets[plot_widget.comp_name].enable_plot_control()
                self.cconfig_widgets[plot_widget.comp_name].show_plot_widget()
            else:
                self.cconfig_widgets[plot_widget.comp_name].disable_plot_control()
                self.cconfig_widgets[plot_widget.comp_name].hide_plot_widget()

    def __calculate_hsd_bandwidth(self):
        """
        Compute current bandwidth across enabled sensors in bits per second.

        Notes
        -----
        Bandwidth formula: `ODR * (type_size * dim) * 8` summed across sensors.
        """
        self.curr_bandwidth = 0
        sensors_status = {
            s: self.components_status[s]
            for s in self.components_status
            if self.components_status[s].get("c_type") == DTDLUtils.ComponentTypeEnum.SENSOR.value
            and self.components_status[s].get("enable")
        }
        for ss in sensors_status:
            # bnd = ODR*(data_type*dim)*8
            ss_status = sensors_status[ss]
            ss_dtdl_comp = self.components_dtdl[ss]
            ss_category = ss_status.get("sensor_category")
            if ss_category is not None:
                odr = 0  # Safe default (No odr, no bandwidth contribution)
                if (
                    ss_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_MEMS.value
                    or ss_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_AUDIO.value
                    or ss_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_PRESENCE.value
                ):
                    odr = self.__get_mems_sensor_odr(ss_status, ss_dtdl_comp)
                elif ss_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_RANGING.value:
                    odr = self.__get_ranging_sensor_odr(ss_status)
                elif ss_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_LIGHT.value:
                    odr = self.__get_light_sensor_odr(ss_status)
                elif ss_category == DTDLUtils.SensorCategoryEnum.ISENSOR_CLASS_POWERMETER.value:
                    odr = self.__get_powermeter_sensor_odr(ss_status, ss_dtdl_comp)
                data_byte_len = TypeConversion.check_type_length(ss_status.get("data_type"))
                dim = ss_status.get("dim")
                self.curr_bandwidth += odr * data_byte_len * dim * 8

    def check_hsd_bandwidth(self):
        """
        Emit whether the current bandwidth exceeds the configured maximum.
        """
        self.__calculate_hsd_bandwidth()
        # print("self.curr_bandwidth", self.curr_bandwidth)
        self.sig_hsd_bandwidth_exceeded.emit(self.curr_bandwidth > HSD_Controller.MAX_HSD_BANDWIDTH)

    def get_sd_mounted_status(self):
        """
        Check if the SD card is mounted on the device.
        """
        return self.hsd_link.get_boolean_property(0, "log_controller", "sd_mounted")

    def update_plot_widget(self, comp_name, plot_params, visible):
        """
        Update plot widget characteristics and visibility.

        Parameters
        ----------
        comp_name : str
            Component name.
        plot_params : SensorPlotParams | FFTAlgPlotParams | ...
            Plot parameter object produced by `get_plot_params`.
        visible : bool
            True to enable controls and show the widget; False to hide.
        """
        if comp_name in self.plot_widgets:
            self.plot_widgets[comp_name].update_plot_characteristics(plot_params)
            if visible:
                self.cconfig_widgets[comp_name].enable_plot_control()
                self.cconfig_widgets[comp_name].show_plot_widget()
            else:
                self.cconfig_widgets[comp_name].disable_plot_control()
                self.cconfig_widgets[comp_name].hide_plot_widget()
        else:
            log.warning(f"{comp_name} is not in plot widget list yet")

    def remove_plot_widget(self, comp_name) -> HSDPlotLinesWidget:
        """
        Remove and return a plot widget by component name.

        Parameters
        ----------
        comp_name : str
            Component name.

        Returns
        -------
        HSDPlotLinesWidget | None
            Removed widget or `None` if not present.
        """
        if comp_name in self.plot_widgets:
            return self.plot_widgets.pop(comp_name)
        else:
            log.warning(f"{comp_name} is not in plot widget list yet")

    def add_data_to_a_plot(self, data: DataClass):
        """
        Append incoming `DataClass` payload to the corresponding plot widget.

        Parameters
        ----------
        data : DataClass
            Data wrapper containing `comp_name` and raw bytes.
        """
        self.plot_widgets[data.comp_name].add_data(data.data)

    def connect_to(self, d_id: int, d_text: str = None, com_speed: int = None):
        """
        Connect to a device either via serial COM or USB link.

        Parameters
        ----------
        d_id : int
            Device id for non-serial links.
        d_text : str, optional
            Presentation string containing COM id for serial links.
        com_speed : int, optional
            Baud rate for serial links.

        Notes
        -----
        - Emits `sig_device_connected(True)` on success.
        - Starts a serial reader thread for serial links.
        """
        if self.is_hsd_link_serial():
            com_id = d_text.split("]")[0][1:]
            is_open = self.hsd_link.open(com_id, com_speed)
            if is_open:
                # Ensure error suppression is disabled for normal operation
                try:
                    com_mgr = self.hsd_link.get_com_manager()
                    if hasattr(com_mgr, "set_suppress_errors"):
                        com_mgr.set_suppress_errors(False)
                except Exception:
                    pass
                self.sig_device_connected.emit(True)
            else:
                log.error("COM port {} not connected!".format(com_id))
            
            # If hsd_link being used is a serial link, start a thread to read data from the serial port
            self.serial_thread_stop_flag = Event()
            serial_thread = self.ReadSerialDataThread(self.hsd_link, self, self.sig_streaming_error)
            serial_thread.start()
            self.sensors_threads.append(serial_thread)
        else:
            self.sig_device_connected.emit(True)
            self.device_id = d_id

    def disconnect(self):
        """
        Disconnect from the device and clean up widgets/state.

        Notes
        -----
        - Emits `sig_device_connected(False)`.
        - Deletes plot and config widgets and clears component maps.
        """
        self.sig_device_connected.emit(False)
        for pw in self.plot_widgets:
            self.plot_widgets[pw].deleteLater()
        self.plot_widgets.clear()

        for cw in self.cconfig_widgets:
            self.cconfig_widgets[cw].deleteLater()
        self.cconfig_widgets.clear()

        self.components_dtdl.clear()  # From DTDL DeviceModel
        self.components_status.clear()  # From FW

    def stop_serial_reader_thread(self):
        """
        Stop the active serial reader thread, if present.
        """
        serial_threads = [t for t in self.sensors_threads if isinstance(t, self.ReadSerialDataThread)]
        # Suppress low-level serial errors during shutdown
        try:
            if self.hsd_link is not None:
                com_mgr = self.hsd_link.get_com_manager()
                if hasattr(com_mgr, "set_suppress_errors"):
                    com_mgr.set_suppress_errors(True)
        except Exception:
            pass
        for thread in serial_threads:
            thread.stop()
        for thread in serial_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)

        # After threads are stopped, flush and close the port if still open
        try:
            if self.hsd_link is not None:
                com_mgr = self.hsd_link.get_com_manager()
                serial_port = getattr(com_mgr, "serial_port", None)
                if serial_port and serial_port.is_open:
                    try:
                        self.hsd_link.flush()
                    except Exception:
                        pass
                    try:
                        serial_port.timeout = 0.1
                        serial_port.close()
                    except Exception:
                        pass
        except Exception as e:
            log.warning(f"Error while closing serial port for shutdown: {e}")
        # Drop stopped serial threads from the list
        self.sensors_threads = [t for t in self.sensors_threads if t not in serial_threads]

    def send_command(self, json_command):
        """
        Send a PNPL JSON command to the device and emit the response.

        Parameters
        ----------
        json_command : dict
            PNPL command payload.

        Returns
        -------
        dict | None
            Response dictionary if available.
        """
        log.info(f"PnPL Message: {json_command}")
        response = self.hsd_link.send_command(self.device_id, json_command)
        if response is not None:
            self.sig_pnpl_response_received.emit(json_command, response)
        return response

    def save_config(self, on_pc: bool, on_sd: bool):
        """
        Persist current device configuration to PC and/or device SD.

        Parameters
        ----------
        on_pc : bool
            True to export JSON to a PC-selected path.
        on_sd : bool
            True to request firmware to save configuration to SD.
        """
        if on_pc:
            fname = QFileDialog.getSaveFileName(
                None, "Save Current Device Configuration", "device_config", "JSON (*.json)"
            )
            with open(fname[0], "w", encoding="utf-8") as f:
                device_status = self.get_device_status()
                components = device_status["devices"][self.device_id]["components"]
                for i, c in enumerate(components):
                    if list(c.keys())[0] == "acquisition_info":
                        del device_status["devices"][self.device_id]["components"][i]
                json.dump(device_status, f, ensure_ascii=False, indent=4)
        if on_sd:
            self.hsd_link.save_config(self.device_id)

    def load_config(self, fpath):
        """
        Load a configuration JSON from disk and apply it to the device.
        """
        self.hsd_link.update_device(self.device_id, fpath)
        self.update_device_status()

    def update_mlc_ispu_config_file(self, comp_name, fpath):
        """
        Update the stored path for an MLC or ISPU UCF file.

        Parameters
        ----------
        comp_name : str
            Component name associated with the MLC or ISPU configuration.
        fpath : str
            File path to the MLC or ISPU UCF file.
        """
        if comp_name not in self.mlc_ispu_configs:
            self.mlc_ispu_configs[comp_name] = {}
        self.mlc_ispu_configs[comp_name]["path"] = fpath

    def update_mlc_ispu_output_file(self, comp_name, fpath):
        """Update the stored auxiliary output-format path for an ISPU component."""
        if comp_name not in self.mlc_ispu_configs:
            self.mlc_ispu_configs[comp_name] = {}
        self.mlc_ispu_configs[comp_name]["output_path"] = fpath

    def __copy_mlc_ispu_config_files(self):
        copied_paths = set()
        for config_entry in self.mlc_ispu_configs.values():
            for path_key in ("path", "output_path"):
                config_path = config_entry.get(path_key)
                if config_path is None or config_path in copied_paths or not os.path.exists(config_path):
                    continue

                copied_paths.add(config_path)
                config_name = os.path.basename(config_path)
                shutil.copyfile(
                    config_path,
                    os.path.join(self.hsd_link.get_acquisition_folder(), config_name),
                )
                log.info(f"{config_name} File correctly saved")

    def load_ispu_output_fmt_file(self, fpath):
        """
        Load an ISPU output format JSON file, accounting for trailing NUL.

        Parameters
        ----------
        fpath : str
            JSON file path containing ISPU output format.

        Returns
        -------
        bool
            True on successful parsing and storage.
        """
        try:
            with open(fpath, encoding="utf-8") as f:
                file_content = f.read()
                if file_content[-1] == "\x00":
                    ispu_out_json_dict = json.loads(file_content[:-1])
                else:
                    ispu_out_json_dict = json.loads(file_content)

            outputs = ispu_out_json_dict.get("output")
            if not isinstance(outputs, list) or len(outputs) == 0:
                return False

            for output in outputs:
                if not isinstance(output, dict):
                    return False
                if not output.get("name") or not output.get("type"):
                    return False

            ispu_out_json_str = json.dumps(ispu_out_json_dict)
            self.ispu_output_format = json.loads(ispu_out_json_str)
            self.ispu_output_format_path = fpath
            return True
        except Exception:
            return False

    def get_out_fmt_byte_count(self, of_type):
        """
        Return the byte length of an ISPU output type.
        """
        return TypeConversion.check_type_length(of_type)

    def get_out_fmt_char(self, of_type):
        """
        Return the struct format character for an ISPU output type.
        """
        return TypeConversion.get_format_char(of_type)

    def upload_file(self, comp_name, fpath):
        """
        Placeholder for generic file upload to a component.

        Notes
        -----
        Not implemented.
        """
        # to be implemented in future for other component types
        log.error(
            "Not implemented: generic file upload; component=%s, file=%s. "
            "Use specific helpers (e.g., upload_mlc_ucf_file, "
            "upload_ispu_ucf_file) when applicable.",
            comp_name,
            fpath,
        )

    def upload_mlc_ucf_file(self, comp_name, ucf_fpath):
        """
        Upload an MLC UCF file to the specified component.
        NOTE: The method is named for MLC UCFs but can handle both .ucf and .json formats
            based on file extension.

        Parameters
        ----------
        comp_name : str
            Target component name for the UCF upload.
        ucf_fpath : str
            File path to the UCF, which can be either .ucf or .json.
            > .ucf files will be processed as traditional UCFs, while .json files will be treated
            as pre-parsed UCF content in JSON format. The method will route to the appropriate
            upload function based on the file extension.    
        """
        upload_result = None
        ucf_fpath_lower = ucf_fpath.lower()
        if ucf_fpath_lower.endswith(".ucf"):
            upload_result = self.hsd_link.upload_mlc_ucf_file(self.device_id, comp_name, ucf_fpath)
        elif ucf_fpath_lower.endswith(".json"):
            upload_result = self.hsd_link.upload_mlc_json_file(self.device_id, comp_name, ucf_fpath)

        if upload_result is not None:
            self.update_mlc_ispu_config_file(comp_name, ucf_fpath)
            self.sig_mlc_config_loaded.emit(comp_name, ucf_fpath)

    def upload_ispu_ucf_file(self, comp_name, ucf_fpath, output_json_fpath=None):
        """
        Upload an ISPU UCF and output format JSON, then emit a notify signal.

        Parameters
        ----------
        comp_name : str
            Target component name for the ISPU UCF upload.
        ucf_fpath : str
            File path to the ISPU UCF, which can be either .ucf or .json.
            > .ucf files will be processed as traditional UCFs, while .json
            files will be treated as pre-parsed UCF content in JSON format. The method will route
            to the appropriate upload function based on the file extension.
        output_json_fpath : str, optional
            File path to the ISPU output format JSON, required if `ucf_fpath` is a .ucf file,
            ignored if `ucf_fpath` is a .json file
        """
        upload_result = None
        ucf_fpath_lower = ucf_fpath.lower()
        output_json_fpath_lower = output_json_fpath.lower() if output_json_fpath else ""

        if ucf_fpath_lower.endswith(".ucf"):
            if not output_json_fpath_lower.endswith(".json"):
                log.error("ISPU UCF upload requires an output format JSON descriptor")
                return
            upload_result = self.hsd_link.upload_ispu_ucf_file(
                self.device_id, comp_name, ucf_fpath, output_json_fpath
            )
        elif ucf_fpath_lower.endswith(".json"):
            upload_result = self.hsd_link.upload_ispu_json_file(
                self.device_id, comp_name, ucf_fpath, output_json_fpath
            )

        if upload_result is not None:
            self.update_mlc_ispu_config_file(comp_name, ucf_fpath)
            if output_json_fpath:
                self.update_mlc_ispu_output_file(comp_name, output_json_fpath)
            self.sig_ispu_config_loaded.emit(comp_name, ucf_fpath, output_json_fpath or "")

    def upload_mlc_json_file(self, comp_name, json_fpath):
        """
        Upload an MLC JSON file to the specified component.

        Parameters
        ----------
        comp_name : str
            Target component name for the MLC JSON upload.
        json_fpath : str
            File path to the MLC JSON configuration.
        """
        upload_result = self.hsd_link.upload_mlc_json_file(self.device_id, comp_name, json_fpath)
        if upload_result is not None:
            self.update_mlc_ispu_config_file(comp_name, json_fpath)
            self.sig_mlc_config_loaded.emit(comp_name, json_fpath)

    def upload_ispu_json_file(self, comp_name, json_fpath, output_json_fpath=None):
        """
        Upload an ISPU JSON file to the specified component.

        Parameters
        ----------
        comp_name : str
            Target component name for the ISPU JSON upload.
        json_fpath : str
            File path to the ISPU JSON configuration.
        """
        upload_result = self.hsd_link.upload_ispu_json_file(
            self.device_id, comp_name, json_fpath, output_json_fpath
        )
        if upload_result is not None:
            self.update_mlc_ispu_config_file(comp_name, json_fpath)
            if output_json_fpath:
                self.update_mlc_ispu_output_file(comp_name, output_json_fpath)
            self.sig_ispu_config_loaded.emit(comp_name, json_fpath, output_json_fpath or "")

    def doTag(self, sw_tag_name, status):
        if status is True:
            self.hsd_link.set_sw_tag_on(self.device_id, sw_tag_name)
        else:
            self.hsd_link.set_sw_tag_off(self.device_id, sw_tag_name)
        self.update_component_status("tags_info")
        tag_label = self.components_status["tags_info"][sw_tag_name]["label"]
        if self.data_pipeline is not None:
            self.data_pipeline.do_tag(status, tag_label)
        self.sig_tag_done.emit(status, tag_label)

    def changeSWTagClassEnabled(self, sw_tag_name, new_status):
        """
        Enable or disable a software tag class on the device.
        """
        self.hsd_link.set_sw_tag_class_enabled(self.device_id, sw_tag_name, new_status)

    def changeHWTagClassEnabled(self, hw_tag_name, new_status):
        """
        Deprecated: enable or disable a hardware tag class on the device.

        This API is deprecated and retained for backward compatibility only. HW tagging is
        configured directly via PnPL SET messages and there is no dedicated API call here.
        The method performs no operation and emits a deprecation warning.

        Parameters
        ----------
        hw_tag_name : str
            Hardware tag class identifier.
        new_status : bool
            Desired enable state (ignored).

        Notes
        -----
        To update HW tag enable state, use `send_command` with an appropriate PnPL payload
        targeting the HW tag component. Refer to the device DTDL for exact property names.
        Example shape:

        {"<comp_name>": {"<hw_tag_name>": {"enable": <new_status>}}}
        """
        _ = hw_tag_name  # to avoid unused parameter warning
        _ = new_status  # to avoid unused parameter warning
        try:
            warnings.warn(
                "changeHWTagClassEnabled is deprecated; use PnPL SET commands via "
                "send_command instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        except Exception:
            pass
        # Intentionally no-op

    def changeSWTagClassLabel(self, sw_tag_name, new_label):
        """
        Change the display label of a software tag class.
        """
        self.hsd_link.set_sw_tag_class_label(self.device_id, sw_tag_name, new_label)

    def changeHWTagClassLabel(self, hw_tag_name, new_label):
        """
        Deprecated: change the display label of a hardware tag class.

        This API is deprecated and kept for backward compatibility only. HW tagging is
        configured directly via PnPL SET messages and there is no dedicated API call
        here. The method performs no operation and emits a deprecation warning.

        Parameters
        ----------
        hw_tag_name : str
            Hardware tag class identifier.
        new_label : str
            Desired display label (ignored).

        Notes
        -----
        To update HW tag labels, use `send_command` with an appropriate PnPL payload
        targeting the HW tag component, e.g.:

        {"comp_name": {"<hw_tag_name>": {"label": "<new_label>"}}}
        """
        _ = hw_tag_name  # to avoid unused parameter warning
        _ = new_label  # to avoid unused parameter warning
        try:
            warnings.warn(
                "changeHWTagClassLabel is deprecated; use PnPL SET commands via "
                "send_command instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        except Exception:
            pass
        # Intentionally no-op

    def set_anomaly_classes(self, anomaly_classes):
        """
        Set the list of anomaly classes used by the anomaly detector.
        """
        self.anomaly_classes = anomaly_classes

    def get_anomaly_classes(self):
        """
        Get the configured anomaly classes.
        """
        return self.anomaly_classes

    def set_output_classes(self, output_classes):
        """
        Set classifier output class labels.
        """
        self.output_classes = output_classes

    def get_output_classes(self):
        """
        Get configured classifier output classes.
        """
        return self.output_classes

    def set_ai_anomaly_tool(self, ai_anomaly_tool):
        """
        Set the AI anomaly tool used by the controller.
        """
        self.ai_anomaly_tool = ai_anomaly_tool

    def get_ai_anomaly_tool(self):
        """
        Get the current AI anomaly tool.
        """
        return self.ai_anomaly_tool

    def set_ai_classifier_tool(self, ai_classifier_tool):
        """
        Set the AI classifier tool used by the controller.
        """
        self.ai_classifier_tool = ai_classifier_tool

    def get_ai_classifier_tool(self):
        """
        Get the current AI classifier tool.
        """
        return self.ai_classifier_tool

    def set_rtc_time(self):
        """
        Set the device Real-Time Clock (RTC) to the current host time.
        """
        self.hsd_link.set_rtc_time(self.device_id)

    def do_offline_plots(
        self,
        cb_sensor_value,
        tag_label,
        start_time,
        end_time,
        active_sensor_list,
        active_algorithm_list,
        debug_flag,
        sub_plots_flag,
        raw_data_flag,
        active_actuator_list=None,
        fft_flag=None,
    ):
        """
        Generate offline plots from recorded data into a dedicated output folder.

        Parameters
        ----------
        cb_sensor_value : str
            Component name or "all" to plot all components.
        tag_label : str
            Optional tag filter label; use "None" or '' for no filter.
        start_time : int
            Start timestamp in microseconds.
        end_time : int
            End timestamp in microseconds.
        active_sensor_list : list
            Active sensors configuration list.
        active_algorithm_list : list
            Active algorithms configuration list.
        debug_flag : bool
            Enable timestamp recovery debugging.
        sub_plots_flag : bool
            True to split series into subplots.
        raw_data_flag : bool
            True to plot raw data.
        active_actuator_list : list | None, optional
            Active actuators configuration list.
        fft_flag : bool | None, optional
            Enable FFT plots when available.

        Notes
        -----
        Emits `sig_offline_plots_completed` when plotting finishes.
        """

        if self.hsd is not None:
            self.hsd.close_plot_threads()

        acquisition_folder = self.hsd_link.get_acquisition_folder()
        hsd_factory = HSDatalog()
        self.hsd = hsd_factory.create_hsd(acquisition_folder)

        self.hsd.enable_timestamp_recovery(debug_flag)
        if tag_label == "None" or tag_label == "":
            tag_label = None
        if cb_sensor_value == "all":
            for s in active_sensor_list:
                s_key = list(s.keys())[0]
                s[s_key]["is_first_chunk"] = True
                ioffset = s[s_key].get("ioffset", 0)
                try:
                    self.hsd.get_sensor_plot(
                        s_key,
                        s[s_key],
                        start_time,
                        end_time,
                        tag_label if tag_label != "None" else None,
                        [],
                        sub_plots_flag,
                        raw_data_flag,
                        fft_flag,
                    )
                except Exception as e:
                    log.error(f"Error in {s_key} get_sensor_plot: {e}")
                HSDatalog.reset_status_conversion_side_info(s[s_key], ioffset)
            for a in active_algorithm_list:
                a_key = list(a.keys())[0]
                self.hsd.get_algorithm_plot(
                    a_key,
                    a[a_key],
                    start_time,
                    end_time,
                    tag_label if tag_label != "None" else None,
                    [],
                    sub_plots_flag,
                    raw_data_flag,
                )
            if active_actuator_list is not None:
                for act in active_actuator_list:
                    act_key = list(act.keys())[0]
                    self.hsd.get_actuator_plot(
                        act_key,
                        act[act_key],
                        start_time,
                        end_time,
                        tag_label if tag_label != "None" else None,
                        [],
                        True,
                        raw_data_flag,
                    )
        else:
            s_list = self.hsd.get_sensor_list(only_active=True)
            a_list = self.hsd.get_algorithm_list(only_active=True)
            act_list = self.hsd.get_actuator_list(only_active=True)
            sensor_comp = [s for s in s_list if cb_sensor_value in s]
            algo_comp = [a for a in a_list if cb_sensor_value in a]
            act_comp = [act for act in act_list if cb_sensor_value in act]
            if len(sensor_comp) > 0:  # == 1
                sensor_comp = sensor_comp[0][cb_sensor_value]
                sensor_comp["is_first_chunk"] = True
                ioffset = sensor_comp.get("ioffset", 0)
                try:
                    self.hsd.get_sensor_plot(
                        cb_sensor_value,
                        sensor_comp,
                        start_time,
                        end_time,
                        tag_label if tag_label != "None" else None,
                        [],
                        sub_plots_flag,
                        raw_data_flag,
                        fft_flag,
                    )
                except Exception as e:
                    log.error(f"Error in {sensor_comp} get_sensor_plot: {e}")
                HSDatalog.reset_status_conversion_side_info(sensor_comp, ioffset)
            elif len(algo_comp) > 0:  # == 1
                a_key = list(algo_comp[0].keys())[0]

                self.hsd.get_algorithm_plot(
                    a_key,
                    algo_comp,
                    start_time,
                    end_time,
                    tag_label if tag_label != "None" else None,
                    sub_plots_flag,
                    raw_data_flag,
                )
            elif len(act_comp) > 0:  # == 1
                act_comp = act_comp[0][cb_sensor_value]
                self.hsd.get_actuator_plot(
                    cb_sensor_value,
                    act_comp,
                    start_time,
                    end_time,
                    tag_label if tag_label != "None" else None,
                    [],
                    True,
                    raw_data_flag,
                )

        self.sig_offline_plots_completed.emit()

    def start_wav_conversion_thread(self, comp_name, start_time, end_time, finish_callback):
        """
        Start the wav conversion process.
        """
        # Start the segmentation thread
        self.worker_thread = WavConversionThread(self, comp_name, start_time, end_time)
        self.worker_thread.sig_finished.connect(
            partial(self.__inner_finish_callback, finish_callback)
        )  # Connect the finish callback
        self.worker_thread.start()  # Start the segmentation thread

    def __inner_finish_callback(self, finish_callback, comp_name, wav_file_name):
        """
        Inner finish callback function.
        """
        finish_callback(comp_name, wav_file_name)

    def convert_dat2wav(self, comp_name, start_time, end_time):
        """
        Convert recorded DAT stream to WAV for the specified time range.

        Parameters
        ----------
        comp_name : str
            Component name to convert.
        start_time : int
            Start timestamp in microseconds.
        end_time : int
            End timestamp in microseconds.

        Returns
        -------
        str | None
            Path to the generated WAV file or `None` on error.
        """
        acquisition_folder = self.hsd_link.get_acquisition_folder()
        hsd_factory = HSDatalog()
        hsd = hsd_factory.create_hsd(acquisition_folder)
        if hsd is None:
            log.error("Error creating HSDatalog object")
            return None

        output_folder = acquisition_folder + "_Exported"
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        hsd.enable_timestamp_recovery(True)
        component = HSDatalog.get_component(hsd, comp_name)
        if component is not None:
            HSDatalog.convert_dat_to_wav(hsd, component, start_time, end_time, output_folder)

        return HSDatalog.get_wav_file_path(hsd, comp_name, output_folder)

    def set_automode_enabled(self, status):
        """
        Enable or disable auto-mode feature.
        """
        self.automode_enabled = status

    def is_automode_enabled(self):  # False:DISABLED, True:ENABLED
        """
        Return whether auto-mode is enabled.
        """
        return self.automode_enabled

    def set_automode_status(self, status: AutomodeStatus):
        """
        Set the current auto-mode status enum.
        """
        self.automode_status = status

    def get_automode_status(self):  # False:IDLE, True:LOGGING
        """
        Get the current auto-mode status.
        """
        return self.automode_status

    def get_automode_settings(self):
        """
        Retrieve auto-mode settings from the device.

        Returns
        -------
        tuple
            `(n, m, x, y)` → number of acquisitions, start delay (ms/s), logging
            period, and idle period.
        """
        automode_status = self.get_component_status("automode")["automode"]
        n = automode_status.get("nof_acquisitions")
        m = automode_status.get("start_delay_s")
        m = automode_status.get("start_delay_ms") if m is None else m
        x = automode_status.get("logging_period_s")
        x = automode_status.get("datalog_time_length") if x is None else x
        y = automode_status.get("idle_period_s")
        y = automode_status.get("idle_time_length") if y is None else y
        return (n, m, x, y)

    def get_acquisition_folder(self):
        """
        Return the current acquisition folder path.
        """
        return self.hsd_link.get_acquisition_folder()

    def add_error_in_configuration(self, error_key):
        """
        Track a configuration error and lock the Start button.
        """
        if not error_key in self.config_error_dict:
            self.config_error_dict[error_key] = True
            self.sig_lock_start_button.emit(True, "Errors in config")

    def remove_error_in_configuration(self, error_key):
        """
        Clear a configuration error and unlock Start if no errors remain.
        """
        if error_key in self.config_error_dict:
            del self.config_error_dict[error_key]
            if len(self.config_error_dict) == 0:
                self.sig_lock_start_button.emit(False, "")

    # Data Toolkit functions
    def set_dt_plugins_folder(self, path: str):
        """
        Enable DataToolkit plugins by adding a folder to `sys.path`.
        """
        self.dt_plugins_folder_path = path
        # Add the provided path to sys.path
        sys.path.insert(0, self.dt_plugins_folder_path)

    def get_dt_plugin_folder_path(self):
        """
        Return the configured DataToolkit plugins folder path.
        """
        return self.dt_plugins_folder_path

    def remove_dt_plugins_folder(self):
        """
        Disable DataToolkit plugins by removing the folder from `sys.path`.
        """
        if self.dt_plugins_folder_path in sys.path:
            sys.path.remove(self.dt_plugins_folder_path)

    def is_hsd_link_serial(self):
        """
        Check whether the active link is a serial v2 link.
        """
        if self.hsd_link is None:
            return False
        return isinstance(self.hsd_link, HSDLink_v2_Serial)

