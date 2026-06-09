#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    HSD_MC_LogControlWidget.py
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
Motor Control specific log control widget.

This module defines `HSD_MC_LogControlWidget`, a specialization of
`HSDLogControlWidget` that integrates Motor Control (MC) state with logging controls.
It ensures the Start Log button is disabled while the motor is running and exposes a
tags combo box for labeling.
"""

from PySide6.QtCore import Slot
from stdatalog_gui.HSD_GUI.Widgets.HSDLogControlWidget import HSDLogControlWidget

import stdatalog_core.HSD_utils.logger as logger
log = logger.setup_applevel_logger(is_debug = False, file_name= "app_debug.log")

class HSD_MC_LogControlWidget(HSDLogControlWidget):
    """Log control widget tailored for Motor Control use-cases.

    Parameters
    ----------
    controller : STDTDL_Controller
        Application controller providing logging state and MC signals.
    comp_contents : Any
        DTDL contents for the log controller component.
    comp_name : str, optional
        Component name, by default ``"log_controller"``.
    comp_display_name : str, optional
        Human-friendly name for UI, by default ``"Log Controller"``.
    comp_sem_type : str, optional
        Semantic type, by default ``"other"``.
    c_id : int, optional
        Component identifier used by the base class.
    parent : QWidget, optional
        Optional Qt parent.
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
            controller, comp_contents, comp_name, comp_display_name, comp_sem_type, c_id, parent
        )

        self.controller.sig_is_motor_started.connect(self.s_is_motor_started)
        self.tags_label_combo.setEnabled(True)
        self.tags_label_combo.setVisible(True)

    @Slot(bool, int)
    def s_is_motor_started(self, status:bool, motor_id:int):
        """Enable/disable Start Log button when motor starts/stops.

        Parameters
        ----------
        status : bool
            True when the motor starts, False when it stops.
        motor_id : int
            Motor identifier (reserved for future multi-motor handling).
        """
        # NOTE next dev: motor_id check vs self.motor_id
        _ = motor_id  # currently unused
        if status == True and self.controller.is_logging:
            self.log_start_button.setEnabled(False)
        elif status == False and self.controller.is_logging:
            self.log_start_button.setEnabled(True)

    @Slot(bool)
    def s_is_logging(self, status:bool, interface:int):
        """Override logging handler to honor motor running state.

        Delegates to base class for common behavior, then disables Start Log while the
        motor is already running.
        """
        super().s_is_logging(status, interface)

        if status:
            if self.controller.is_motor_started:
                self.log_start_button.setEnabled(False)
