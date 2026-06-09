#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    PlotParams.py
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
"""Plot parameter data structures for ST DTDL GUI.

This module defines lightweight parameter classes used to describe how components should
be plotted in the GUI (lines, heatmaps, gauges, labels, etc.). Classes capture basic
attributes such as dimensions, units, time windows, and algorithm-specific metadata.

Design Notes:
- Simple containers without behavior; constructed by controllers/widgets and passed to
    plotting views.
- Follows the project's docstring style and 100-character wrap where feasible.
"""

import stdatalog_pnpl.DTDL.dtdl_utils as DTDLUtils

class PlotParams(object):
    """Base parameters for plotting a component.

    Parameters
    ----------
    comp_name : str
        Component name associated with the plot.
    enabled : bool
        Whether the plot should be visible/enabled.

    Attributes
    ----------
    comp_name : str
        Component identifier.
    enabled : bool
        Plot enable flag.
    """
    def __init__(self, comp_name, enabled) -> None:
        self.comp_name = comp_name
        self.enabled = enabled
class SensorISPUPlotParams(PlotParams):
    """Parameters for ISPU sensor plots with output format.

    Parameters
    ----------
    comp_name : str
        Component name.
    enabled : bool
        Plot visibility.
    dimension : int
        Number of channels/lines.
    out_fmt : Any
        Output format descriptor used by ISPU sensors.
    time_window : int, optional
        Time window in seconds. Default is 30.
    """
    def __init__(self, comp_name, enabled, dimension, out_fmt, time_window=30) -> None:
        super().__init__(comp_name, enabled)
        self.dimension = dimension
        self.out_fmt = out_fmt
        self.time_window = time_window

class LinesPlotParams(PlotParams):
    """Parameters for line-based plots.

    Parameters
    ----------
    comp_name : str
        Component name.
    enabled : bool
        Plot visibility.
    dimension : int
        Number of channels/lines.
    unit : str, optional
        Measurement unit for the y-axis label. Default is "".
    time_window : int, optional
        Time window in seconds. Default is 30.
    """
    def __init__(self, comp_name, enabled, dimension, unit = "", time_window = 30) -> None:
        super().__init__(comp_name, enabled)
        self.dimension = dimension
        self.unit = unit
        self.time_window = time_window

class SensorPlotParams(LinesPlotParams):
    """Parameters for generic sensor line plots.

    Inherits all fields from `LinesPlotParams`.
    """
    def __init__(self, comp_name, enabled, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class SensorMemsPlotParams(SensorPlotParams):
    """Parameters for MEMS sensor line plots.

    Parameters
    ----------
    comp_name : str
        Component name.
    enabled : bool
        Plot visibility.
    odr : Any
        Output data rate for the sensor.
    dimension : int
        Number of channels.
    unit : str, optional
        Measurement unit. Default is "".
    time_window : int, optional
        Time window in seconds. Default is 30.
    """
    def __init__(self, comp_name, enabled, odr, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        self.odr = odr

class SensorAudioPlotParams(SensorPlotParams):
    """Parameters for audio sensor line plots.

    Parameters
    ----------
    comp_name : str
        Component name.
    enabled : bool
        Plot visibility.
    odr : Any
        Output data rate (sample rate) for audio.
    dimension : int
        Number of channels.
    unit : str, optional
        Measurement unit. Default is "".
    time_window : int, optional
        Time window in seconds. Default is 30.
    """
    def __init__(self, comp_name, enabled, odr, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        self.odr = odr

class PlotHeatMapParams(SensorPlotParams):
    """Parameters for heatmap-style sensor plots.

    Parameters
    ----------
    comp_name : str
        Component name.
    enabled : bool
        Plot visibility.
    dimension : int
        Heatmap dimension (e.g., rows or aggregate size).
    resolution : Any
        Resolution or scaling factor for the heatmap.
    unit : str, optional
        Measurement unit. Default is "".
    time_window : int, optional
        Time window in seconds. Default is 30.
    """
    def __init__(self, comp_name, enabled, dimension, resolution, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        self.resolution = resolution

class SensorRangingPlotParams(PlotHeatMapParams):
    """Parameters for ranging sensor heatmap plots with output format.

    Parameters
    ----------
    comp_name : str
        Component name.
    enabled : bool
        Plot visibility.
    dimension : int
        Heatmap dimension.
    resolution : Any
        Resolution or scaling for the heatmap.
    output_format : Any, optional
        Optional output format description.
    unit : str, optional
        Measurement unit. Default is "".
    time_window : int, optional
        Time window in seconds. Default is 30.
    """
    def __init__(self, comp_name, enabled, dimension, resolution,
                output_format = None, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, resolution, unit, time_window)
        self.output_format = output_format

class SensorLightPlotParams(SensorPlotParams):
    """Parameters for ambient light sensor plots."""
    def __init__(self, comp_name, enabled, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class SensorCameraPlotParams(SensorPlotParams):
    """Parameters for camera sensor plots (metadata-level)."""
    def __init__(self, comp_name, enabled, dimension, width, height, pixel_format, resolution, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)
        self.resolution = resolution
        self.pixel_format = pixel_format
        self.width = width
        self.height = height

class SensorPowerPlotParams(SensorPlotParams):
    """Parameters for power sensor plots aggregating multiple sub-plot params.

    Parameters
    ----------
    plots_params_dict : dict
        Mapping of plot names to parameter objects for grouped power views.
    """
    def __init__(self, comp_name, enabled, plots_params_dict, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, 1, unit, time_window)
        self.plots_params_dict = plots_params_dict

class SensorPresenscePlotParams(SensorPlotParams):
    """Parameters for presence sensor plots aggregating sub-plot params."""
    def __init__(self, comp_name, enabled, plots_params_dict, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, 1, unit, time_window)
        self.plots_params_dict = plots_params_dict

class PlotPAmbientParams(SensorPlotParams):
    """Parameters for ambient pressure/temperature sensor plots."""
    def __init__(self, comp_name, enabled, dimension, unit="", time_window=30) -> None:
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class PlotPObjectParams(SensorPlotParams):
    """Parameters for object temperature sensor plots.

    Parameters
    ----------
    embedded_compensation : Any
        Device-side compensation mode/flag.
    software_compensation : Any
        Software-side compensation mode/flag.
    """
    def __init__(self, comp_name, enabled, dimension, embedded_compensation,
                software_compensation, unit="", time_window=30) -> None:
        self.embedded_compensation = embedded_compensation
        self.software_compensation = software_compensation
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class PlotPPresenceParams(SensorPlotParams):
    """Parameters for presence detection sensor plots.

    Parameters
    ----------
    embedded_compensation : Any
        Device-side compensation mode.
    software_compensation : Any
        Software-side compensation mode.
    """
    def __init__(self, comp_name, enabled, dimension, embedded_compensation,
                software_compensation, unit="", time_window=30) -> None:
        self.embedded_compensation = embedded_compensation
        self.software_compensation = software_compensation
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class PlotPMotionParams(SensorPlotParams):
    """Parameters for motion detection sensor plots.

    Parameters
    ----------
    embedded_compensation : Any
        Device-side compensation mode.
    software_compensation : Any
        Software-side compensation mode.
    """
    def __init__(self, comp_name, enabled, dimension, embedded_compensation,
                software_compensation, unit="", time_window=30) -> None:
        self.embedded_compensation = embedded_compensation
        self.software_compensation = software_compensation
        super().__init__(comp_name, enabled, dimension, unit, time_window)

class ActuatorPlotParams(PlotParams):
    """Base parameters for actuator-related plots."""
    def __init__(self, comp_name, enabled) -> None:
        super().__init__(comp_name, enabled)

class MCTelemetriesPlotParams(ActuatorPlotParams):
    """Parameters for motor control telemetry plots.

    Parameters
    ----------
    plots_params_dict : dict
        Mapping of telemetry names to their plot parameters.
    current_scaler : float, optional
        Scaling factor applied to current values. Default is 1.
    voltage_scaler : float, optional
        Scaling factor applied to voltage values. Default is 1.
    """
    def __init__(self,
                comp_name,
                enabled,
                plots_params_dict,
                current_scaler=1,
                voltage_scaler=1
                ) -> None:
        super().__init__(comp_name, enabled)
        self.plots_params_dict = plots_params_dict
        self.current_scaler = current_scaler
        self.voltage_scaler = voltage_scaler

class AlgorithmPlotParams(PlotParams):
    """Parameters for algorithm output plots.

    Parameters
    ----------
    comp_name : str
        Component name.
    enabled : bool
        Plot visibility.
    y_label : str, optional
        Y-axis label. Default is "".
    """
    def __init__(self, comp_name, enabled, y_label="") -> None:
        super().__init__(comp_name, enabled)
        self.y_label = y_label

class FFTAlgPlotParams(AlgorithmPlotParams):
    """Parameters for FFT algorithm plots.

    Parameters
    ----------
    fft_len : int
        FFT length (number of points).
    fft_sample_freq : float
        Sampling frequency used by the FFT.
    y_label : str, optional
        Y-axis label. Default is "".
    """
    def __init__(self, comp_name, enabled, fft_len, fft_sample_freq, y_label = "") -> None:
        super().__init__(comp_name, enabled, y_label)
        self.fft_len = fft_len
        self.fft_sample_freq = fft_sample_freq
        self.alg_type = DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_FFT.value

class ClassificationModelPlotParams(AlgorithmPlotParams):
    """Parameters for classifier model output plots.

    Parameters
    ----------
    num_of_class : int, optional
        Number of output classes. Default is 1.
    y_label : str, optional
        Y-axis label. Default is "".
    """
    def __init__(self, comp_name, enabled, num_of_class = 1, y_label="") -> None:
        super().__init__(comp_name, enabled, y_label)
        self.num_of_class = num_of_class
        self.alg_type = DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_CLASSIFIER.value

class AnomalyDetectorModelPlotParams(ClassificationModelPlotParams):
    """Parameters for anomaly detector model output plots.

    Notes
    -----
    Sets `num_of_class` to 2 and `alg_type` appropriately.
    """
    def __init__(self, comp_name, enabled, y_label="") -> None:
        super().__init__(comp_name, enabled, 2, y_label)
        self.num_of_class = 2
        self.alg_type = DTDLUtils.AlgorithmTypeEnum.IALGORITHM_TYPE_ANOMALY_DETECTOR.value

class PlotLevelParams(PlotParams):
    """Parameters for level-style plots (single value in a range).

    Parameters
    ----------
    min_val : float
        Minimum value of the level range.
    max_val : float
        Maximum value of the level range.
    init_val : float
        Initial value to display.
    unit : str, optional
        Measurement unit. Default is "".
    """
    def __init__(self, comp_name, enabled, min_val, max_val, init_val, unit = "") -> None:
        super().__init__(comp_name, enabled)
        self.min_val = min_val
        self.max_val = max_val
        self.init_val = init_val
        self.unit = unit

class PlotGaugeParams(PlotLevelParams):
    """Parameters for analog gauge plots (derived from level params)."""
    def __init__(self, comp_name, enabled, min_val, max_val, init_val, unit="") -> None:
        super().__init__(comp_name, enabled, min_val, max_val, init_val, unit)

class PlotLabelParams(PlotLevelParams):
    """Parameters for label-style plots showing a numeric value and unit."""
    def __init__(self, comp_name, enabled, min_val, max_val, init_val=0, unit = "") -> None:
        super().__init__(comp_name, enabled, min_val, max_val, init_val, unit)

class PlotCheckBoxParams(ActuatorPlotParams):
    """Parameters for checkbox list plots used by actuators.

    Parameters
    ----------
    labels : list[str]
        Labels used to render checkboxes.
    """
    def __init__(self, comp_name, enabled, labels) -> None:
        super().__init__(comp_name, enabled)
        self.labels = labels
