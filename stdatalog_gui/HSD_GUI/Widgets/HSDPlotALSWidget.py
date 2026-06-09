# ******************************************************************************
#  * @file    HSDPlotALSWidget.py
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
Ambient light sensor (ALS) multi-channel line plotting widget.

This module defines `HSDPlotALSWidget`, a thin specialization of
`HSDPlotLinesWidget` that visualizes ALS channels (Red, Visible, Blue,
Green, IR, Clear) with fixed colors and labeled legend entries.

Highlights
----------
- Clears the inherited legend and re-adds items with ALS-specific labels.
- Applies a semi-transparent legend background for readability.
- Uses deterministic per-channel colors for visual consistency.
"""
from PySide6.QtGui import QColor, QBrush
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotLinesWidget import HSDPlotLinesWidget
class HSDPlotALSWidget(HSDPlotLinesWidget):
    """
    ALS plot widget that renders six spectral channels with labels and colors.

    Parameters
    ----------
    controller : object
        Application controller used by the base plot widget.
    comp_name : str
        Component name (unique identifier for the plot source).
    comp_display_name : str
        Human-friendly display name for the plot container.
    plot_params : object
        Plot parameters passed to the base `HSDPlotLinesWidget`.
    p_id : int, optional
        Plot identifier used by the base class, by default 0.
    parent : QWidget | None, optional
        Parent widget, by default `None`.
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

        self.legend.clear()

        self.lines_params = {
            0: {"color": "#FF0000", "label": "Red"},
            1: {"color": "#666666", "label": "Visible"},
            2: {"color": "#0000FF", "label": "Blue"},
            3: {"color": "#00FF00", "label": "Green"},
            4: {"color": "#FF00FF", "label": "IR"},
            5: {"color": "#FFFFFF", "label": "Clear"},
        }

        self.legend = self.graph_widget.addLegend()
        brush = QBrush(QColor(255, 255, 255, 15))
        self.legend.setBrush(brush)

        for gc_id in self.graph_curves:
            self.graph_curves[gc_id].setPen(
                {
                    'color': self.lines_params[gc_id]["color"],
                    'width': 1,
                }
            )
            self.legend.addItem(
                self.graph_curves[gc_id], self.lines_params[gc_id]["label"]
            )

        self.graph_widget.setMinimumHeight(180)
