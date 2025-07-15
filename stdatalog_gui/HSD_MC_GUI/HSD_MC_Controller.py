# *****************************************************************************
#  * @file    HSD_MC_Controller.py
#  * @author  SRA
# ******************************************************************************

import os
from threading import Event
from PySide6.QtCore import Signal
from stdatalog_core.HSD.utils.type_conversion import TypeConversion
from stdatalog_gui.HSD_GUI.HSD_Controller import HSD_Controller
from stdatalog_gui.STDTDL_Controller import ComponentType
from stdatalog_gui.Utils.PlotParams import LinesPlotParams, MCTelemetriesPlotParams, PlotCheckBoxParams, PlotGaugeParams, PlotLabelParams, PlotLevelParams
from stdatalog_pnpl.DTDL import dtdl_utils
from stdatalog_pnpl.PnPLCmd import PnPLCMDManager
import time
import stdatalog_pnpl.DTDL.dtdl_utils as DTDLUtils

class HSD_MC_Controller(HSD_Controller):
    #MCP Signals
    sig_is_motor_started = Signal(bool, int)
    sig_motor_fault_raised = Signal()
    sig_motor_fault_acked = Signal()
    sig_mcp_check_connection = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mc_comp_name = "motor_controller"
        self.mc_start_cmd_name = "start_motor"
        self.mc_stop_cmd_name = "stop_motor"
        self.mc_ack_fault_cmd_name = "ack_fault"
        self.mc_motor_speed_prop_name = "motor_speed"
        self.mc_speed_req_name = "speed"

    def start_plots(self):
        super().start_plots()
        self.start_plot_actuator()
    
    def start_plot_actuator(self):    
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
                        sensor_data_file_path = os.path.join(self.hsd_link.get_acquisition_folder(),(str(s_plot.comp_name) + ".dat"))
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

                    
                    dr = HSD_Controller.DataReader(self, self.add_data_to_a_plot, s_plot.comp_name, spts, dimensions, sample_size, data_format, sensitivity, interleaved_data, raw_flat_data)
                    self.data_readers.append(dr)

                    if self.save_files_flag:
                        thread = self.SensorAcquisitionThread(stopFlag, self.hsd_link, dr, self.device_id, s_plot.comp_name, sensor_data_file, usb_dps, self.sig_streaming_error)
                    else:
                        thread = self.SensorAcquisitionThread(stopFlag, self.hsd_link, dr, self.device_id, s_plot.comp_name, None, usb_dps, self.sig_streaming_error)
                    thread.start()
                    self.sensors_threads.append(thread)

    def get_plot_params(self, comp_name, comp_type, comp_interface, comp_status):
        if comp_type.name == ComponentType.ACTUATOR.name:
            return self.__get_actuator_plot_params(comp_name, comp_type, comp_interface, comp_status)
        else:
            return super().get_plot_params(comp_name, comp_type, comp_interface, comp_status)
            
    def __get_actuator_plot_params(self, comp_name, comp_type, comp_interface, comp_status):
        if comp_status is not None and comp_name in comp_status:
            if comp_type.name == ComponentType.ACTUATOR.name:
                plot_params_dict = {}
                comp_enabled = comp_status[comp_name].get("enable")
                if comp_name == DTDLUtils.MC_SLOW_TELEMETRY_COMP_NAME:
                    st_ble_stream_components = comp_status[DTDLUtils.MC_SLOW_TELEMETRY_COMP_NAME].get(DTDLUtils.ST_BLE_STREAM)
                    if st_ble_stream_components is not None:
                        for c in st_ble_stream_components.keys():
                            if c == "temperature":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                plot_params_dict["temperature"] = PlotLabelParams("temperature", t_enabled, 0, 0, 0, t_unit) # label
                            elif c == "ref_speed":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                plot_params_dict["ref_speed"] = PlotLabelParams("ref_speed", t_enabled, 0, 0, 0, t_unit) # label
                            elif c == "bus_voltage":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                plot_params_dict["bus_voltage"] = PlotLabelParams("bus_voltage", t_enabled, 0, 0, 0, t_unit) # label
                            elif c == "speed":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                t_unit  = st_ble_stream_components[c].get("unit")
                                max_speed = st_ble_stream_components[c].get("max")
                                initial_speed = st_ble_stream_components[c].get("initial_value")
                                plot_params_dict["speed"] = PlotGaugeParams("speed", t_enabled, -max_speed, max_speed, initial_speed, t_unit)
                            elif c == "fault":
                                t_enabled = st_ble_stream_components[c].get("enable")
                                plot_params_dict["fault"] = PlotCheckBoxParams("fault", t_enabled, ['No Error', 'FOC Duration', 'Over Voltage', 'Under Voltage', 'Over Heat', 'Start Up failure', 'Speed Feedback', 'Over Current', 'Software Error' ]) # label #TODO ENUM in DTDL
                    return MCTelemetriesPlotParams(comp_name, comp_enabled, plot_params_dict)
                elif comp_name == DTDLUtils.MC_FAST_TELEMETRY_COMP_NAME:
                    contents = comp_interface.contents
                    description = None
                    for c in contents:
                        if c.description is not None:
                            description = c.description if isinstance(c.description, str) else c.description.en
                            display_name = c.display_name if isinstance(c.display_name, str) else c.display_name.en
                            t_root_key = list(comp_status.keys())[0]
                            if description == DTDLUtils.MC_FAST_TELEMETRY_STRING:
                                if c.name in comp_status[t_root_key]:
                                    tele_status = comp_status[t_root_key][c.name]
                                    t_enabled = tele_status[DTDLUtils.ENABLED_STRING]
                                    t_unit = tele_status[DTDLUtils.UNIT_STRING]
                                    plot_params_dict[display_name] = LinesPlotParams(c.name, t_enabled, 1, t_unit)
                        if c.name == DTDLUtils.MC_FAST_TELEMETRY_SENSITIVITY:
                            current_scaler = comp_status[t_root_key][DTDLUtils.MC_FAST_TELEMETRY_SENSITIVITY]['current']
                            voltage_scaler = comp_status[t_root_key][DTDLUtils.MC_FAST_TELEMETRY_SENSITIVITY]['voltage']
                    return MCTelemetriesPlotParams(comp_name, comp_enabled, plot_params_dict, current_scaler, voltage_scaler)            
        return None
    
    def update_component_status(self, comp_name, comp_type = ComponentType.OTHER):
        super().update_component_status(comp_name, comp_type)
        self.__update_actuator_component_status(comp_name, comp_type)
        
    def __update_actuator_component_status(self, comp_name, comp_type):
        comp_status = self.get_component_status(comp_name)
        if comp_status is not None and comp_name in comp_status:
            self.components_status[comp_name] = comp_status[comp_name]
            if isinstance(comp_type,str):
                ct = comp_type
            else:
                ct = comp_type.name
            if ct == ComponentType.ACTUATOR.name:
                plot_params = self.get_plot_params(comp_name, comp_type, self.components_dtdl[comp_name], comp_status)
                comp_status = self.get_component_status(comp_name)
                self.sig_actuator_component_updated.emit(comp_name, plot_params)
            self.sig_component_updated.emit(comp_name, comp_status[comp_name])
            
    def start_motor(self, motor_id=0):
        """
        Start the motor.
        
        Args:
            motor_id (int): Motor ID (default is 0)
        """
        # Send Start motor cmd
        self.send_command(PnPLCMDManager.create_command_cmd(self.mc_comp_name, self.mc_start_cmd_name))
        # Emit signal
        self.sig_is_motor_started.emit(True, motor_id)

    def stop_motor(self, motor_id=0):
        """
        Stop the motor.
        
        Args:
            motor_id (int): Motor ID (default is 0)
        """
        # Send stop motor message
        res = self.send_command(PnPLCMDManager.create_command_cmd(self.mc_comp_name, self.mc_stop_cmd_name))
        # Emit signal
        self.sig_is_motor_started.emit(False, motor_id)
        return res

    def ack_fault(self, motor_id=0):
        """
        Acknowledge motor fault.
        
        Args:
            motor_id (int): Motor ID (default is 0)
        """
        res = self.send_command(PnPLCMDManager.create_command_cmd(self.mc_comp_name, self.mc_ack_fault_cmd_name))
        time.sleep(0.7)
        stop_res = self.stop_motor()
        if res is not None and stop_res is not None:
            self.sig_motor_fault_acked.emit()

    def set_motor_speed(self, value, motor_id=0):
        """
        Set the motor speed.
        
        Args:
            value (int): Speed value
            motor_id (int): Motor ID (default is 0)
        """
        self.send_command(PnPLCMDManager.create_set_property_cmd(self.mc_comp_name, self.mc_motor_speed_prop_name, value))