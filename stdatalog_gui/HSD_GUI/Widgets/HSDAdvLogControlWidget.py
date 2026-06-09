# ******************************************************************************
#  * @file    HSDAdvLogControlWidget.py
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
Advanced log control widget enabling extended offline plotting options.

This module defines `HSDAdvLogControlWidget`, a thin specialization of
`HSDLogControlWidget` that enables additional UI controls for advanced
workflows. Compared to the base widget, it exposes SD card status and refresh
actions in the UI and turns on several plotting options (spectrum, debug,
tags, sub-plots, raw data) for offline analysis.

Highlights
----------
- Shows SD card status panel and refresh button for convenience.
- Enables spectrum and debug flags for richer offline plots.
- Exposes tag label selection and sub-plot grouping options.
- Allows toggling raw-data plotting where supported.
"""

from stdatalog_gui.HSD_GUI.Widgets.HSDLogControlWidget import HSDLogControlWidget
import stdatalog_core.HSD_utils.logger as logger
log = logger.get_logger(__name__)

class HSDAdvLogControlWidget(HSDLogControlWidget):
    """Advanced log controller with extended plotting toggles.

    Parameters
    ----------
    controller : object
        Application controller used by the base class to orchestrate logging,
        plotting, and configuration operations.
    comp_contents : list
        Component content descriptors forwarded to the base widget.
    comp_name : str, optional
        Component identifier, by default "log_controller".
    comp_display_name : str, optional
        Display name used in the UI header, by default "Log Controller".
    comp_sem_type : str, optional
        Semantic type forwarded to the base `ComponentWidget`, by default "other".
    c_id : int, optional
        Component id for the base widget, by default 0.
    parent : QWidget | None, optional
        Parent widget.
    """
    def __init__(
        self,
        controller,
        comp_contents,
        comp_name="log_controller",
        comp_display_name="Log Controller",
        comp_sem_type="other",
        c_id=0,
        parent=None,
    ):
        super().__init__(
            controller,
            comp_contents,
            comp_name,
            comp_display_name,
            comp_sem_type,
            c_id,
            parent,
        )

        self.frame_sub_log_info.setEnabled(True)
        self.frame_sub_log_info.setVisible(True)

        self.update_sd_status_label()

        self.refresh_sd_button.setEnabled(True)
        self.refresh_sd_button.setVisible(True)

        self.spectrum_radio.setEnabled(True)
        self.spectrum_radio.setVisible(True)

        self.debug_radio.setEnabled(True)
        self.debug_radio.setVisible(True)

        self.tags_label_combo.setEnabled(True)
        self.tags_label_combo.setVisible(True)

        self.sub_plots_radio.setEnabled(True)
        self.sub_plots_radio.setVisible(True)

        self.raw_data_radio.setEnabled(True)
        self.raw_data_radio.setVisible(True)
