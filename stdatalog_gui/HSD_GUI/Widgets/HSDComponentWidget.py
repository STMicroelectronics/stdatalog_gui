# ******************************************************************************
#  * @file    HSDComponentWidget.py
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
Component-level widgets for HSD GUI components, including ALS-specific validation.

This module provides small wrapper widgets that extend the base `ComponentWidget` to
handle component-specific UI behavior and validation.

Highlights
----------
- `HSDComponentWidget`: Thin wrapper around the base widget for generic HSD
    components.
- `HSDDeviceInfoComponentWidget`: Specialization for the DeviceInformation
    component. It adjusts selected property labels so storage and memory values are
    shown with clear units in the UI.
- `HSDALSComponentWidget`: Specialization for an ALS (ambient light sensor)
    component. It coordinates two time-related properties — exposure time and
    intermeasurement time — and validates their relationship to provide immediate
    user feedback via styles and tooltips.

Notes
-----
- Icons are loaded from package resources using `pkg_resources.resource_filename`.
    Do not remove the `stdatalog_gui.UI.icons` import: it is required to make the
    icons available as packaged resources.
"""

from PySide6.QtGui import QPixmap

from stdatalog_gui.UI.styles import STDTDL_LineEdit
from stdatalog_gui.Widgets.ComponentWidget import ComponentWidget
from stdatalog_gui.Widgets.PropertyWidget import PropertyWidget
# NOTE: don't delete this import! It is required so that icons are packaged and
# accessible via `pkg_resources.resource_filename` used below.
import stdatalog_gui.UI.icons
from pkg_resources import resource_filename

info_img_path_valid = resource_filename(
    "stdatalog_gui.UI.icons",
    "outline_info_white_18dp.png",
)
info_img_path_invalid = resource_filename(
    "stdatalog_gui.UI.icons",
    "info_18dp_FF0000.svg",
)

DEVICE_INFORMATION_UNIT_MAP = {
    "Bytes": "B",
    "Kilobytes": "KB",
    "Kibibytes": "KiB",
    "Megabytes": "MB",
    "Mebibytes": "MiB",
    "Gigabytes": "GB",
    "Gibibytes": "GiB",
    "Terabytes": "TB",
    "Tebibytes": "TiB",
}


class HSDComponentWidget(ComponentWidget):
    """Base component widget for HSD GUI components.

    This widget subclasses `ComponentWidget` without adding component-specific
    behavior. Dedicated subclasses are used when a component needs custom UI logic.

    Parameters
    ----------
    controller : object
        Application controller exposing property read/write operations and
        device communication.
    comp_name : str
        Component identifier (e.g., "DeviceInformation").
    comp_display_name : str
        Human-friendly component name used in the UI.
    comp_sem_type : str
        Semantic type for the component (e.g., "sensor", "algorithm", "other").
    comp_contents : list
        List of property descriptors provided by the backend/schema.
    c_id : int, optional
        Component identifier used by the base class, by default 0.
    parent : QWidget | None, optional
        Parent widget.
    """
    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        comp_sem_type,
        comp_contents,
        c_id=0,
        parent=None,
    ):
        """Initialize the generic component widget."""
        super().__init__(
            controller,
            comp_name,
            comp_display_name,
            comp_sem_type,
            comp_contents,
            c_id,
            parent,
        )


class HSDDeviceInfoComponentWidget(HSDComponentWidget):
    """Device information widget with custom display labels for memory fields."""

    def __init__(
        self,
        controller,
        comp_name,
        comp_display_name,
        comp_sem_type,
        comp_contents,
        c_id=0,
        parent=None,
    ):
        self._update_display_names(comp_contents)
        super().__init__(
            controller,
            comp_name,
            comp_display_name,
            comp_sem_type,
            comp_contents,
            c_id,
            parent,
        )

    @staticmethod
    def _update_display_names(comp_contents):
        total_storage = next(
            (content for content in comp_contents if content.name == "totalStorage"),
            None,
        )
        total_memory = next(
            (content for content in comp_contents if content.name == "totalMemory"),
            None,
        )

        if total_storage is not None:
            total_storage.display_name = HSDDeviceInfoComponentWidget._format_label(
                "Total Storage",
                total_storage,
                default_unit="GB",
            )
        if total_memory is not None:
            total_memory.display_name = HSDDeviceInfoComponentWidget._format_label(
                "Total Memory",
                total_memory,
                default_unit="KB",
            )

    @staticmethod
    def _extract_display_unit(prop_content):
        """Return the user-facing display unit string, if defined."""
        display_unit = getattr(prop_content, "display_unit", None)
        if isinstance(display_unit, str):
            return display_unit
        return getattr(display_unit, "en", None)

    @staticmethod
    def _resolve_device_information_unit(prop_content, default_unit):
        """Resolve display suffix for DeviceInformation properties.

        Resolution order:
        1. `display_unit` as-is, because it is already intended for user display.
        2. `unit` mapped through the DeviceInformation byte-unit map.
        3. Fallback default supplied by the caller.
        """
        display_unit = HSDDeviceInfoComponentWidget._extract_display_unit(prop_content)
        if display_unit:
            return display_unit

        unit = getattr(prop_content, "unit", None)
        if isinstance(unit, str):
            unit = unit.strip()
            for unit_name, unit_symbol in DEVICE_INFORMATION_UNIT_MAP.items():
                if unit_name.casefold() == unit.casefold():
                    return unit_symbol
            return unit

        if unit:
            return DEVICE_INFORMATION_UNIT_MAP.get(unit, unit)

        return default_unit

    @staticmethod
    def _format_label(base_label, prop_content, default_unit):
        """Compose the final DeviceInformation display label with unit suffix."""
        unit = HSDDeviceInfoComponentWidget._resolve_device_information_unit(
            prop_content,
            default_unit,
        )
        return f"{base_label} [{unit}]"


class HSDALSComponentWidget(HSDComponentWidget):
    """ALS component widget with timing validation and user feedback.

    This specialization wires up the ALS properties controlling exposure time and
    intermeasurement time and enforces a simple constraint to help users avoid a
    configuration that would be ignored by the firmware:

    - If `IM <= Texp + 6 ms`, the intermeasurement time is effectively ignored.

    The widget provides immediate visual feedback by updating the line edit's
    style and tooltip, as well as switching the info icon to a red variant when
    the constraint is violated.

    Parameters
    ----------
    controller : object
        Application controller exposing property operations.
    comp_name : str
        Component name (e.g., "ALS").
    comp_display_name : str
        Human-friendly component name.
    comp_sem_type : str
        Semantic type (e.g., "sensor").
    comp_contents : list
        Property descriptors for the ALS component.
    c_id : int, optional
        Component identifier, by default 0.
    parent : QWidget | None, optional
        Parent widget.
    """
    def __init__(
            self,
            controller,
            comp_name,
            comp_display_name,
            comp_sem_type,
            comp_contents,
            c_id=0,
            parent=None
        ):
        """Connect ALS-specific properties and prepare validation state."""
        super().__init__(
            controller,
            comp_name,
            comp_display_name,
            comp_sem_type,
            comp_contents,
            c_id,
            parent,
        )

        self.exposure_time_widget:PropertyWidget = None
        self.intermeasurement_time_widget:PropertyWidget = None
        self.default_tooltip_text = ""

        self.initialize_widgets()

    def initialize_widgets(self):
        """Locate and connect ALS timing widgets from the base property set.

        This method scans `self.property_widgets` (created by the base
        `ComponentWidget`) to find the `exposure_time` and
        `intermeasurement_time` widgets, stores references to them, and wires
        their `textChanged` signals to the validation handler.
        """
        for w_key, widget in self.property_widgets.items():
            if w_key == "exposure_time":
                self.exposure_time_widget = widget
                self.exposure_time_widget.value.textChanged.connect(self.times_value_changed)
            elif w_key == "intermeasurement_time":
                self.default_tooltip_text = widget.icon.toolTip()
                self.intermeasurement_time_widget = widget
                self.intermeasurement_time_widget.value.textChanged.connect(
                    self.times_value_changed
                )

    def times_value_changed(self, value):
        """Validate ALS timing fields and update the UI accordingly.

        Parameters
        ----------
        value : str
            New text from the sender line edit (unused; the method reads both
            fields directly).
            kept for signature compatibility with `textChanged` signal.

        Behavior
        ---------
        - Reads `exposure_time` and `intermeasurement_time` as floats.
        - If either field is empty, no validation is performed.
        - If `IM <= (Texp / 1000) + 6`, the intermeasurement time field is
            marked invalid and the info icon shows a red tooltip explaining that
            the value would be ignored by the firmware.
        - Otherwise, the field is marked valid and the normal tooltip/icon are
            restored.
        """
        _ = value  # Unused parameter kept for signal compatibility
        exposure_time_str = self.exposure_time_widget.value.text()
        intermeasurement_time_str = self.intermeasurement_time_widget.value.text()
        if exposure_time_str == "" or intermeasurement_time_str == "":
            return
        exposure_time = float(exposure_time_str)
        intermeasurement_time = float(intermeasurement_time_str)
        if intermeasurement_time <= (exposure_time / 1000) + 6:
            self.intermeasurement_time_widget.value.setStyleSheet(STDTDL_LineEdit.invalid)
            self.intermeasurement_time_widget.icon.setToolTip(
                "<span style='color:red;'>If IM &le; Texp + 6ms, then it is ignored." \
                "</span>"
            )
            pixmap = QPixmap(info_img_path_invalid)
        else:
            self.intermeasurement_time_widget.value.setStyleSheet(STDTDL_LineEdit.valid)
            self.intermeasurement_time_widget.icon.setToolTip(self.default_tooltip_text)
            pixmap = QPixmap(info_img_path_valid)
        self.intermeasurement_time_widget.icon.setPixmap(pixmap)
