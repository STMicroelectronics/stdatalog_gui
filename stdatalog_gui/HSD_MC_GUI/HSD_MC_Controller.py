#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_Controller.py
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
Motor Control (MC) controller.

This module defines `HSD_MC_Controller`, a specialization of the generic
`HSD_Controller` for Motor Control use-cases. It configures actuator data streaming,
creates plot parameter sets for MC telemetries (slow and fast), updates component
status, and exposes convenience methods to control the motor (start/stop/ack fault,
set speed).
"""
import os
import time
from threading import Event

from PySide6.QtCore import Signal
from stdatalog_core.HSD.utils.type_conversion import TypeConversion
from stdatalog_gui.HSD_GUI.HSD_Controller import HSD_Controller
from stdatalog_gui.STDTDL_Controller import ComponentType
from stdatalog_gui.Utils.PlotParams import LinesPlotParams, MCTelemetriesPlotParams,\
    PlotCheckBoxParams, PlotGaugeParams, PlotLabelParams

from stdatalog_pnpl.PnPLCmd import PnPLCMDManager

import stdatalog_pnpl.DTDL.dtdl_utils as DTDLUtils

class HSD_MC_Controller(HSD_Controller):
    """Controller for Motor Control devices and telemetries.

    Responsibilities
    ---------------
    - Start actuator streams and threads for MC telemetries.
    - Build plot parameter objects for slow/fast MC telemetry components.
    - Update component status and propagate relevant signals.
    - Provide motor control commands (start, stop, ack fault, set speed).

    Signals
    -------
    sig_is_motor_started : Signal(bool, int)
        Emits the running state and motor id when start/stop occurs.
    sig_motor_fault_raised : Signal()
        Emitted when a motor fault is raised (source external to this class).
    sig_motor_fault_acked : Signal()
        Emitted after a fault is acknowledged and the motor is stopped.
    sig_mcp_check_connection : Signal()
        Emitted to trigger a connection check to the Motor Control board.
    """
    #MCP Signals
    sig_is_motor_started = Signal(bool, int)
    sig_motor_fault_raised = Signal()
    sig_motor_fault_acked = Signal()
    sig_mcp_check_connection = Signal()

    def __init__(self, parent=None):
        """Initialize controller defaults and MC command identifiers.

        Parameters
        ----------
        parent : QObject, optional
            Optional Qt parent.
        """
        super().__init__(parent)
        self.mc_comp_name = "motor_controller"
        self.mc_start_cmd_name = "start_motor"
        self.mc_stop_cmd_name = "stop_motor"
        self.mc_ack_fault_cmd_name = "ack_fault"
        self.mc_motor_speed_prop_name = "motor_speed"
        self.mc_speed_req_name = "speed"

    def start_plots(self):
        """Start plotting and actuator streams for MC components.

        Calls the base implementation to start generic plots, then starts actuator streams
        specific to Motor Control use-cases.
        """
        super().start_plots()
        self.start_plot_actuator()

    def start_plot_actuator(self):
        """Start acquisition threads for enabled MC actuators.

        For each plot widget associated with an actuator component, this method:
        - Retrieves the component status and determines if streaming is enabled.
        - Creates and registers a `DataReader` for incoming data frames.
        - Optionally opens a file for raw data saving if acquisition saving is enabled.
        - Spawns and starts a `SensorAcquisitionThread` to read from the device link.

        Notes
        -----
        - Fast telemetry (`DTDLUtils.MC_FAST_TELEMETRY_COMP_NAME`) sets `interleaved_data`
            to False to reflect channel layout differences.
        """
        for s in self.plot_widgets:
            s_plot = self.plot_widgets[s]

            c_status = self.get_component_status(s_plot.comp_name)
            self.components_status[s_plot.comp_name] = c_status[s_plot.comp_name]
            c_status_value = c_status[s_plot.comp_name]
            c_enable = c_status_value["enable"]
            c_type = c_status_value.get("c_type")

            if c_type == ComponentType.ACTUATOR.value:
                if c_enable == True:
                    if self.save_files_flag:
                        sensor_data_file_path = os.path.join(
                            self.hsd_link.get_acquisition_folder(),
                            (str(s_plot.comp_name) + ".dat"),
                        )
                        sensor_data_file = open(sensor_data_file_path, "wb+")
                        self.sensor_data_files.append(sensor_data_file)
                    stopFlag = Event()
                    self.threads_stop_flags.append(stopFlag)

                    usb_dps = c_status_value.get("usb_dps")
                    spts = c_status_value.get("samples_per_ts", 1)
                    sample_size = TypeConversion.check_type_length(c_status_value["data_type"])
                    data_format = TypeConversion.get_format_char(c_status_value["data_type"])
                    spts = c_status_value.get("samples_per_ts", 1)
                    interleaved_data = True
                    raw_flat_data = False
                    dimensions = c_status_value.get("dim", 1)
                    sensitivity = 1

                    if s_plot.comp_name == DTDLUtils.MC_FAST_TELEMETRY_COMP_NAME:
                        interleaved_data = False

                    dr = HSD_Controller.DataReader(
                        self,
                        self.add_data_to_a_plot,
                        s_plot.comp_name,
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
                            s_plot.comp_name,
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
                            s_plot.comp_name,
                            None,
                            usb_dps,
                            self.sig_streaming_error,
                        )
                    thread.start()
                    self.sensors_threads.append(thread)

    def get_plot_params(self, comp_name, comp_type, comp_interface, comp_status):
        """Return plot parameters for a component.

        Delegates to actuator-specific logic when `comp_type` is `ComponentType.ACTUATOR`.

        Parameters
        ----------
        comp_name : str
            Component name.
        comp_type : ComponentType
            Component type.
        comp_interface : Any
            DTDL component interface descriptor (contents, names, descriptions).
        comp_status : dict
            Component status dictionary with enable flags and metadata.

        Returns
        -------
        PlotParams | None
            A plot parameter object suitable for constructing widgets, or None if unsupported.
        """
        if comp_type.name == ComponentType.ACTUATOR.name:
            return self.__get_actuator_plot_params(
                comp_name, comp_type, comp_interface, comp_status
            )
        else:
            return super().get_plot_params(comp_name, comp_type, comp_interface, comp_status)

    def __get_actuator_plot_params(self, comp_name, comp_type, comp_interface, comp_status):
        """Build actuator plot parameters for MC slow/fast telemetry components.

        For the slow telemetry component (`MC_SLOW_TELEMETRY_COMP_NAME`), this builds a
        dictionary combining label, gauge, level, or checkbox plot parameters according to the
        DTDL contents and BLE stream status. For the fast telemetry component
        (`MC_FAST_TELEMETRY_COMP_NAME`), this constructs `LinesPlotParams` entries and extracts
        current/voltage scalers when provided.

        Parameters
        ----------
        comp_name : str
            Component name (e.g., slow or fast telemetry).
        comp_type : ComponentType
            Component type; must be `ACTUATOR` to reach this method.
        comp_interface : Any
            DTDL interface descriptor for the component.
        comp_status : dict
            Status dictionary containing enable/units and telemetry-specific configuration.

        Returns
        -------
        MCTelemetriesPlotParams | None
            MC plot params aggregating underlying plot parameter entries per telemetry.
        """
        if comp_status is not None and comp_name in comp_status:
            if comp_type.name == ComponentType.ACTUATOR.name:
                plot_params_dict = {}
                comp_enabled = comp_status[comp_name].get("enable")
                if comp_name == DTDLUtils.MC_SLOW_TELEMETRY_COMP_NAME:
                    st_ble_stream_components = comp_status[
                        DTDLUtils.MC_SLOW_TELEMETRY_COMP_NAME
                    ].get(DTDLUtils.ST_BLE_STREAM)
                    if st_ble_stream_components is not None:
                        for c in st_ble_stream_components.keys():
                            if c == "temperature":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                plot_params_dict["temperature"] = PlotLabelParams(
                                    "temperature", t_enabled, 0, 0, 0, t_unit
                                )  # label
                            elif c == "ref_speed":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                plot_params_dict["ref_speed"] = PlotLabelParams(
                                    "ref_speed", t_enabled, 0, 0, 0, t_unit
                                )  # label
                            elif c == "bus_voltage":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                plot_params_dict["bus_voltage"] = PlotLabelParams(
                                    "bus_voltage", t_enabled, 0, 0, 0, t_unit
                                )  # label
                            elif c == "speed":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                max_speed = st_ble_stream_components[c].get("max")
                                initial_speed = st_ble_stream_components[c].get("initial_value")
                                plot_params_dict["speed"] = PlotGaugeParams(
                                    "speed",
                                    t_enabled,
                                    -max_speed,
                                    max_speed,
                                    initial_speed,
                                    t_unit,
                                )
                            elif c == "fault":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                plot_params_dict["fault"] = PlotCheckBoxParams(
                                    "fault",
                                    t_enabled,
                                    [
                                        "No Error",
                                        "FOC Duration",
                                        "Over Voltage",
                                        "Under Voltage",
                                        "Over Heat",
                                        "Start Up failure",
                                        "Speed Feedback",
                                        "Over Current",
                                        "Software Error",
                                    ],
                                )  # label #NOTE: ENUM in DTDL in next versions
                    return MCTelemetriesPlotParams(comp_name, comp_enabled, plot_params_dict)
                elif comp_name == DTDLUtils.MC_FAST_TELEMETRY_COMP_NAME:
                    contents = comp_interface.contents
                    description = None
                    for c in contents:
                        if c.description is not None:
                            description = (
                                c.description
                                if isinstance(c.description, str)
                                else c.description.en
                            )
                            display_name = (
                                c.display_name
                                if isinstance(c.display_name, str)
                                else c.display_name.en
                            )
                            t_root_key = list(comp_status.keys())[0]
                            if description == DTDLUtils.MC_FAST_TELEMETRY_STRING:
                                if c.name in comp_status[t_root_key]:
                                    tele_status = comp_status[t_root_key][c.name]
                                    t_enabled = tele_status[DTDLUtils.ENABLED_STRING]
                                    t_unit = tele_status[DTDLUtils.UNIT_STRING]
                                    plot_params_dict[display_name] = LinesPlotParams(
                                        c.name, t_enabled, 1, t_unit
                                    )
                        if c.name == DTDLUtils.MC_FAST_TELEMETRY_SENSITIVITY:
                            current_scaler = comp_status[t_root_key][
                                DTDLUtils.MC_FAST_TELEMETRY_SENSITIVITY
                            ]["current"]
                            voltage_scaler = comp_status[t_root_key][
                                DTDLUtils.MC_FAST_TELEMETRY_SENSITIVITY
                            ]["voltage"]
                    return MCTelemetriesPlotParams(
                        comp_name, comp_enabled, plot_params_dict, current_scaler, voltage_scaler
                    )
        return None

    def update_component_status(self, comp_name, comp_type = ComponentType.OTHER):
        """Update and emit status for a component.

        Calls the base implementation to refresh status, then, for actuators, computes plot
        parameters and emits the actuator update signal.

        Parameters
        ----------
        comp_name : str
            Component name.
        comp_type : ComponentType, optional
            Component type, defaults to `ComponentType.OTHER`.
        """
        super().update_component_status(comp_name, comp_type)
        self.__update_actuator_component_status(comp_name, comp_type)

    def __update_actuator_component_status(self, comp_name, comp_type):
        """Internal helper to handle actuator component status updates.

        If the component type is actuator, computes plot params and emits
        `sig_actuator_component_updated`. Always emits `sig_component_updated` with latest status.
        """
        comp_status = self.get_component_status(comp_name)
        if comp_status is not None and comp_name in comp_status:
            self.components_status[comp_name] = comp_status[comp_name]
            if isinstance(comp_type,str):
                ct = comp_type
            else:
                ct = comp_type.name
            if ct == ComponentType.ACTUATOR.name:
                plot_params = self.get_plot_params(
                    comp_name, comp_type, self.components_dtdl[comp_name], comp_status
                )
                comp_status = self.get_component_status(comp_name)
                self.sig_actuator_component_updated.emit(comp_name, plot_params)
            self.sig_component_updated.emit(comp_name, comp_status[comp_name])

    def start_motor(self, motor_id=0):
        """Start the motor.

        Parameters
        ----------
        motor_id : int, optional
            Motor identifier, by default 0.
        """
        # Send Start motor cmd
        self.send_command(
            PnPLCMDManager.create_command_cmd(self.mc_comp_name, self.mc_start_cmd_name)
        )
        # Emit signal
        self.sig_is_motor_started.emit(True, motor_id)

    def stop_motor(self, motor_id=0):
        """Stop the motor.

        Parameters
        ----------
        motor_id : int, optional
            Motor identifier, by default 0.

        Returns
        -------
        Any
            Result object from the underlying command invocation.
        """
        # Send stop motor message
        res = self.send_command(
            PnPLCMDManager.create_command_cmd(self.mc_comp_name, self.mc_stop_cmd_name)
        )
        # Emit signal
        self.sig_is_motor_started.emit(False, motor_id)
        return res

    def ack_fault(self, motor_id=0):
        """Acknowledge a motor fault and ensure motor is stopped.

        Parameters
        ----------
        motor_id : int, optional
            Motor identifier, by default 0.
            (Unused; for future multi-motor support.)
        """
        _ = motor_id  # Unused for now
        # Send acknowledge fault command and stop motor
        res = self.send_command(
            PnPLCMDManager.create_command_cmd(self.mc_comp_name, self.mc_ack_fault_cmd_name)
        )
        time.sleep(0.7)
        stop_res = self.stop_motor()
        if res is not None and stop_res is not None:
            self.sig_motor_fault_acked.emit()

    def set_motor_speed(self, value, motor_id=0):
        """Set the motor speed.

        Parameters
        ----------
        value : int
            Target speed value.
        motor_id : int, optional
            Motor identifier, by default 0.
            (Unused; for future multi-motor support.)
        """
        _ = motor_id  # Unused for now
        # Send set motor speed command
        self.send_command(
            PnPLCMDManager.create_set_property_cmd(
                self.mc_comp_name, self.mc_motor_speed_prop_name, value
            )
        )
