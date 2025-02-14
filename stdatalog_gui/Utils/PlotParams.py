
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

import stdatalog_pnpl.DTDL.dtdl_utils as DTDLUtils

class PlotParams(object):
    def __init__(self, comp_name, enabled) -> None:
        self.comp_name = comp_name
        self.enabled = enabled        
        
class SensorISPUPlotParams(PlotParams):
    def __init__(self, comp_name, enabled, dimension, out_fmt, time_window=30) -> None:
        super().__init__(comp_name, enabled)
        self.dimension = dimension
        self.out_fmt = out_fmt
        self.time_window = time_window

class LinesPlotParams(PlotParams):
    def __init__(self, comp_name, enabled, dimension, unit = "", time_window = 30) -> None:
        super().__init__(comp_name, enabled)
        self.dimension = dimension
        self.unit = unit
        self.time_window = time_window

class SensorPlotParams(LinesPlotParams):
    def __init__(self, comp_name, enabled, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class SensorMemsPlotParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, odr, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        self.odr = odr

class SensorAudioPlotParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, odr, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        self.odr = odr

class PlotHeatMapParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, dimension, resolution, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        self.resolution = resolution

class SensorRangingPlotParams(PlotHeatMapParams):
    def __init__(self, comp_name, enabled, dimension, resolution, output_format = None, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, resolution, unit, time_window)
        self.output_format = output_format

class SensorLightPlotParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class SensorCameraPlotParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class SensorPowerPlotParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, plots_params_dict, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, 1, unit, time_window)
        self.plots_params_dict = plots_params_dict

class SensorPresenscePlotParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, plots_params_dict, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, 1, unit, time_window)
        self.plots_params_dict = plots_params_dict

class PlotPAmbientParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class PlotPObjectParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, dimension, embedded_compensation, software_compensation, unit="", time_window=30) -> None:
        self.embedded_compensation = embedded_compensation
        self.software_compensation = software_compensation
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class PlotPPresenceParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, dimension, embedded_compensation, software_compensation, unit="", time_window=30) -> None:
        self.embedded_compensation = embedded_compensation
        self.software_compensation = software_compensation
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class PlotPMotionParams(SensorPlotParams):
    def __init__(self, comp_name, enabled, dimension, embedded_compensation, software_compensation, unit="", time_window=30) -> None:
        self.embedded_compensation = embedded_compensation
        self.software_compensation = software_compensation
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        
class ActuatorPlotParams(PlotParams):
    def __init__(self, comp_name, enabled) -> None:
        super().__init__(comp_name, enabled)

class MCTelemetriesPlotParams(ActuatorPlotParams):
    def __init__(self, comp_name, enabled, plots_params_dict, current_scaler=1, voltage_scaler=1) -> None:
        super().__init__(comp_name, enabled)
        self.plots_params_dict = plots_params_dict
        self.current_scaler = current_scaler
        self.voltage_scaler = voltage_scaler

class AlgorithmPlotParams(PlotParams):
    def __init__(self, comp_name, enabled, y_label="") -> None:
        super().__init__(comp_name, enabled)
        self.y_label = y_label

class FFTAlgPlotParams(AlgorithmPlotParams):
    def __init__(self, comp_name, enabled, fft_len, fft_sample_freq, y_label = "") -> None:
        super().__init__(comp_name, enabled, y_label)
        self.fft_len = fft_len
        self.fft_sample_freq = fft_sample_freq
        self.alg_type = DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_FFT.value

class ClassificationModelPlotParams(AlgorithmPlotParams):
    def __init__(self, comp_name, enabled, num_of_class = 1, y_label="") -> None:
        super().__init__(comp_name, enabled, y_label)
        self.num_of_class = num_of_class
        self.alg_type = DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_CLASSIFIER.value

class AnomalyDetectorModelPlotParams(ClassificationModelPlotParams):
    def __init__(self, comp_name, enabled, y_label="") -> None:
        super().__init__(comp_name, enabled, 2, y_label)
        self.num_of_class = 2
        self.alg_type = DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_ANOMALY_DETECTOR.value
        
class PlotLevelParams(PlotParams):
    def __init__(self, comp_name, enabled, min_val, max_val, init_val, unit = "") -> None:
        super().__init__(comp_name, enabled)
        self.min_val = min_val
        self.max_val = max_val
        self.init_val = init_val
        self.unit = unit

class PlotGaugeParams(PlotLevelParams):
    def __init__(self, comp_name, enabled, min_val, max_val, init_val, unit="") -> None:
        super().__init__(comp_name, enabled, min_val, max_val, init_val, unit)

class PlotLabelParams(PlotLevelParams):
    def __init__(self, comp_name, enabled, min_val, max_val, init_val=0, unit = "") -> None:
        super().__init__(comp_name, enabled, min_val, max_val, init_val, unit)

class PlotCheckBoxParams(ActuatorPlotParams):
    def __init__(self, comp_name, enabled, labels) -> None:
        super().__init__(comp_name, enabled)
        self.labels = labels