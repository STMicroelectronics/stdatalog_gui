#!/usr/bin/env python
# coding: utf-8
# *****************************************************************************
#  * @file    ToggleButton.py
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
Animated toggle button used throughout the ST DTDL GUI.

This module provides a custom Qt toggle control derived from `QCheckBox` that looks and
feels like a modern on/off switch. It supports hover highlighting, a smooth animated
transition of the circle knob when toggled, and disabled styling. The widget is purely
presentational; external code is expected to connect to the regular `toggled`/`stateChanged`
signals for behavior.

Responsibilities:
- Render a rounded track with a circular knob that slides when toggled.
- Animate knob position via `QPropertyAnimation` bound to a custom property.
- React to hover events to show a subtle outline.
- Reflect the disabled state by changing the knob color and removing interactivity.
"""
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import (
    Qt,
    QEvent,
    QRect,
    QPoint,
    QEasingCurve,
    QPropertyAnimation,
    Property,
)
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent

class ToggleButton(QCheckBox):
    """A rounded, animated on/off toggle based on `QCheckBox`.

    Parameters
    ----------
    width : int, optional
        Total widget width. Height is fixed at 28px. Default is 60.
    bg_color : str, optional
        Background color for the track when unchecked. Default is "#1b1d23".
    circle_color : str, optional
        Color of the knob when enabled and unchecked. Default is "#343b48".
    active_color : str, optional
        Track/knob color when checked. Default is "#20b2aa".
    animation_curve : QEasingCurve.Type, optional
        Easing curve for the knob transition. Default is `OutBounce`.
    """

    def __init__(
        self,
        width=60,
        bg_color="#1b1d23",
        circle_color="#343b48",
        active_color="#20b2aa",
        animation_curve=QEasingCurve.Type.OutBounce,
    ):
        QCheckBox.__init__(self)
        self.setAttribute(Qt.WA_Hover)

        self.setFixedSize(width, 28)
        self.setCursor(Qt.PointingHandCursor)

        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color
        self._circle_disabled_color = "#1b1d23"

        self._circle_position = 3
        # Property animation to smoothly move the knob across the track
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(animation_curve)
        self.animation.setDuration(500)  # ms

        self.stateChanged.connect(self.start_transition)

        self.hovered = False

    def event(self, event):
        """Track hover enter/leave to adjust the outline styling.

        Parameters
        ----------
        event : QEvent
            Incoming event to inspect and optionally handle.

        Returns
        -------
        bool
            Result of base-class event processing.
        """
        if event.type() == QEvent.HoverEnter:
            self.hovered = True
        elif event.type() == QEvent.HoverLeave:
            self.hovered = False
        return super().event(event)

    @Property(float)
    def circle_position(self):
        """Current x-position (in px) of the knob's top-left corner."""
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        """Setter used by the animation to update the knob position and repaint."""
        self._circle_position = pos
        self.update()

    def start_transition(self, value):
        """Animate the circle to the new position when the state changes.

        Parameters
        ----------
        value : int
            Checkbox state value (0/2). Any non-zero value is considered checked.
        """
        self.animation.stop()
        if value:
            self.animation.setEndValue(self.width() - 26)
        else:
            self.animation.setEndValue(3)
        self.animation.start()

    def hitButton(self, pos: QPoint):
        """Return whether a click position falls within the interactive area."""
        return self.contentsRect().contains(pos)

    def paintEvent(self, e):
        """Custom paint routine drawing the track, outline, and moving knob.

        The drawing sequence is:
        1. Clear pen and compute the target rectangle.
        2. Paint the rounded track background according to state.
        3. Select outline if hovered; otherwise, remove it when checkable.
        4. Draw the circular knob at the current animated position.

        Note: 'e' is unused but required by the Qt signature. 
        """
        _ = e  # Unused parameter
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHints.Antialiasing)

        p.setPen(Qt.PenStyle.NoPen)
        r = QRect(0, 0, self.width(), self.height())

        p.setBrush(QColor(self._bg_color))
        p.drawRoundedRect(
            0,
            0,
            r.width(),
            self.height(),
            self.height() / 2,
            self.height() / 2,
        )

        if not self.isChecked():
            if self.isCheckable():
                p.setBrush(QColor(self._circle_color))
            else:
                p.setBrush(QColor(self._circle_disabled_color))
                p.setPen(QPen(QColor("#3d4656"), 3))
        else:
            p.setBrush(QColor(self._active_color))

        if self.hovered:
            p.setPen(QPen(QColor("#3d4656"), 3))
        else:
            if self.isCheckable():
                p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(self._circle_position, 3, 22, 22)

        p.end()

    def setEnabled(self, enabled: bool):
        """Mirror enabled state into checkable and request a repaint."""
        super().setEnabled(enabled)
        self.setCheckable(enabled)
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        """Ignore presses when disabled; otherwise, defer to base implementation."""
        if not self.isEnabled():
            event.ignore()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Ignore releases when disabled; otherwise, defer to base implementation."""
        if not self.isEnabled():
            event.ignore()
        else:
            super().mouseReleaseEvent(event)
