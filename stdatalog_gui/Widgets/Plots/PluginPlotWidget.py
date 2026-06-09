#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    PluginPlotWidget.py
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
Plugin plot widgets and factory for testing and examples.

This module provides a small wrapper around the base plotting widgets to allow quick
instantiation without a full application controller. It defines:

- `PluginPlotType`: An enum of supported plot types (`Line`, `Label`, `Heatmap`).
- `PluginPlotWidget`: A factory container with nested classes that build ready-to-use
    plot widgets for plugins and examples. Each nested class creates its own lightweight
    `STDTDL_Controller` so the plot can run independently.
"""
from enum import Enum

from PySide6.QtWidgets import QLabel, QFrame
from PySide6.QtGui import QPixmap
from stdatalog_gui.STDTDL_Controller import STDTDL_Controller
from stdatalog_gui.UI.styles import STDTDL_PushButton
from stdatalog_gui.Utils.PlotParams import LinesPlotParams, PlotLabelParams
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget
from stdatalog_gui.Widgets.Plots.LabelPlotWidget import LabelPlotWidget
from stdatalog_gui.Widgets.Plots.PlotLinesWidget import PlotLinesWidget
from stdatalog_gui.Widgets.Plots.PlotHeatmapWidget import PlotHeatmapWidget

import stdatalog_gui.UI.icons
from pkg_resources import resource_filename
plugin_img_path = resource_filename('stdatalog_gui.UI.icons', 'power_18dp_E8EAED.svg')

class PluginPlotType(Enum):
    """Enumeration of plot types accepted by the plugin factory.

    Values
    ------
    LINE : str
        Line plot constructed via `LinesWidget`.
    LABEL : str
        Label-style plot constructed via `LabelWidget`.
    HEATMAP : str
        Heatmap plot constructed via `HeatmapWidget`.
    """
    LINE = "Line"
    LABEL = "Label"
    HEATMAP = "Heatmap"

class PluginPlotWidget:
    """Container/factory for plugin-friendly plot widgets.

    This class hosts nested helpers that mirror existing plot widgets, but with a
    self-contained controller so they can be used in plugin contexts, tests, or simple
    examples without wiring the full application state.

    Nested Classes
    --------------
    PlotWidget : QWidget
        Base plot wrapper using `PlotWidget` with a local controller.
    LinesWidget : PlotLinesWidget
        Multi-line time-series plot using `LinesPlotParams`.
    LabelWidget : LabelPlotWidget
        Label-style plot displaying a numeric value with unit.
    HeatmapWidget : PlotHeatmapWidget
        Heatmap visualization of distance/validity data.

    Methods
    -------
    _add_plugin_icon(title_frame)
        Add a small plugin icon to the plot title frame and apply styling.
    create_plot(plot_name, plot_type, dimension, unit="")
        Factory method that returns the right plot widget given a type.
    """

    class PlotWidget(PlotWidget):
        """Base plot wrapper that creates an internal controller.

        Parameters
        ----------
        plot_name : str
            Name used both as component and display name.
        p_id : int, optional
            Plot identifier (forwarded to base). Default is 0.
        parent : QWidget | None, optional
            Parent widget.
        """
        def __init__(self, plot_name, p_id=0, parent=None):
            self.controller = STDTDL_Controller()
            super().__init__(self.controller, plot_name, plot_name, p_id, parent)
            PluginPlotWidget._add_plugin_icon(self.title_frame)
    class LinesWidget(PlotLinesWidget):
        """Line plot wrapper that builds `LinesPlotParams` and a local controller.

        Parameters
        ----------
        plot_name : str
            Name used for component and display.
        dimension : int
            Number of line series to render.
        unit : str, optional
            Measurement unit shown in the left axis label. Default is "".
        p_id : int, optional
            Plot identifier. Default is 0.
        parent : QWidget | None, optional
            Parent widget.
        """

        def __init__(self, plot_name, dimension, unit="", p_id=0, parent=None):
            self.controller = STDTDL_Controller()
            plot_params = LinesPlotParams(plot_name, True, dimension, unit)
            super().__init__(self.controller, plot_name, plot_name, plot_params, p_id, parent)
            PluginPlotWidget._add_plugin_icon(self.title_frame)
    class LabelWidget(LabelPlotWidget):
        """Label plot wrapper that builds `PlotLabelParams` with a local controller.

        Parameters
        ----------
        plot_name : str
            Name used for component and display.
        dimension : int
            Dimension for the label plot (typically 1).
        unit : str, optional
            Measurement unit appended to the value label. Default is "".
        p_id : int, optional
            Plot identifier. Default is 0.
        parent : QWidget | None, optional
            Parent widget.
        """

        def __init__(self, plot_name, dimension, unit="", p_id=0, parent=None):
            self.controller = STDTDL_Controller()
            plot_params = PlotLabelParams(plot_name, True, dimension, unit)
            super().__init__(self.controller, plot_name, plot_name, plot_params, p_id, parent)
            PluginPlotWidget._add_plugin_icon(self.title_frame)

    class HeatmapWidget(PlotHeatmapWidget):
        """Heatmap plot wrapper that sets the shape and a local controller.

        Parameters
        ----------
        plot_name : str
            Name used for component and display.
        heatmap_shape : tuple[int, int]
            Heatmap shape `(rows, cols)`.
        unit : str, optional
            Measurement unit for left axis label. Default is "".
        p_id : int, optional
            Plot identifier. Default is 0.
        parent : QWidget | None, optional
            Parent widget.
        """

        def __init__(self, plot_name, heatmap_shape, unit="", p_id=0, parent=None):
            self.controller = STDTDL_Controller()
            super().__init__(
                self.controller,
                plot_name,
                plot_name,
                heatmap_shape,
                unit,
                p_id,
                parent,
            )
            PluginPlotWidget._add_plugin_icon(self.title_frame)

    @staticmethod
    def _add_plugin_icon(title_frame:QFrame):
        """Add the plugin icon and style to the plot title frame.

        Parameters
        ----------
        title_frame : QFrame
            The plot title frame where the icon is inserted.
        """
        pixmap = QPixmap(plugin_img_path)
        icon_label = QLabel()
        icon_label.setPixmap(pixmap)
        style_title = (
            STDTDL_PushButton.valid
            + "\n QFrame { background-color: rgb(45, 87, 87);}"
        )
        title_frame.setStyleSheet(style_title)
        title_frame.layout().addWidget(icon_label)

    @staticmethod
    def create_plot(plot_name, plot_type: PluginPlotType, dimension, unit=""):
        """Create a plot widget from a `PluginPlotType` and parameters.

        Parameters
        ----------
        plot_name : str
            Name used for component and display.
        plot_type : PluginPlotType
            Plot type enum; one of `LINE`, `LABEL`, or `HEATMAP`.
        dimension : int
            For lines: number of series; for heatmap: used as rows=cols.
        unit : str, optional
            Measurement unit for the plot. Default is "".

        Returns
        -------
        QWidget | None
            The constructed plot widget, or None on invalid type.

        Notes
        -----
        - For `LINE`, a `LinesWidget` is created using `LinesPlotParams`.
        - For `LABEL`, a `LabelWidget` is created using `PlotLabelParams`.
        - For `HEATMAP`, a `HeatmapWidget` is created using a square shape derived
            from `dimension`.
        - If an unsupported type is provided, an error is printed and None is
            returned.
        """
        plot_widget = None

        if plot_type == PluginPlotType.LINE:
            plot_widget = PluginPlotWidget.LinesWidget(plot_name, dimension, unit)
        elif plot_type == PluginPlotType.LABEL:
            plot_widget = PluginPlotWidget.LabelWidget(plot_name, dimension, unit)
        elif plot_type == PluginPlotType.HEATMAP:
            heatmap_shape = (dimension, dimension)
            plot_widget = PluginPlotWidget.HeatmapWidget(plot_name, heatmap_shape, unit)
        else:
            print("Invalid plot parameters")

        return plot_widget
