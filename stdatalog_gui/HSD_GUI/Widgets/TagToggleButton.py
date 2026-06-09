# ******************************************************************************
#  * @file    TagToggleButton.py
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
Tag toggle widget used in the HSD GUI.

This module exposes the class `TagToggleButton`, a small convenience subclass of
`ToggleButton` tailored for software/hardware tag controls in the UI. It only presets
reasonable defaults for size, colors, and animation curve to achieve a consistent look
and feel across the application, while delegating all toggle behavior to the base
`ToggleButton` implementation.

Highlights
----------
- Thin wrapper around `ToggleButton` with opinionated defaults.
- Keeps behavior identical to the base widget; no extra logic is introduced.
- Intended for use wherever tag enable/disable switches appear in the GUI.
"""
from PySide6.QtCore import QEasingCurve
from stdatalog_gui.Widgets.ToggleButton import ToggleButton

class TagToggleButton(ToggleButton):
    """
    Toggle button preset for tag controls.

    This widget inherits from `ToggleButton` and provides preselected visual defaults that
    suit tag toggling. It does not change the toggle logic or event handling of the base
    class.

    Parameters
    ----------
    width : int, optional
        Control width in pixels. Defaults to 60.
    bg_color : str, optional
        Background color (OFF state), as a hex string. Defaults to "#777".
    circle_color : str, optional
        Knob/circle color, as a hex string. Defaults to "#DDD".
    active_color : str, optional
        Accent color (ON state), as a hex string. Defaults to "#000ccf".
    animation_curve : QEasingCurve.Type, optional
        Easing curve used for the toggle animation. Defaults to
        `QEasingCurve.Type.OutBounce`.

    Notes
    -----
    - Styling values are defaults only; callers may override any parameter.
    - All behavior (signals, state changes, painting) is implemented by the base
        `ToggleButton` class.
    """

    def __init__(
        self,
        width=60,
        bg_color="#777",
        circle_color="#DDD",
        active_color="#000ccf",
        animation_curve=QEasingCurve.Type.OutBounce,
    ):
        """
        Initialize the tag toggle with optional visual overrides.

        See the class docstring for parameter details and defaults.
        """
        super().__init__(width, bg_color, circle_color, active_color, animation_curve)
