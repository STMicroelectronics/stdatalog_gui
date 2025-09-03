---
pagetitle: Release Notes for stdatalog_gui 
lang: en
header-includes: <link rel="icon" type="image/x-icon" href="_htmresc/favicon.png" />
---

::: {.row}
::: {.col-sm-12 .col-lg-4}

<center> 
# Release Notes for <mark>stdatalog_gui</mark> 
Copyright &copy; 2025 STMicroelectronics
    
[![ST logo](_htmresc/st_logo_2020.png)](https://www.st.com){.logo}
</center>


# Purpose

The **[stdatalog_gui](https://github.com/STMicroelectronics/stdatalog_gui)** package is a UI toolkit developed by STMicroelectronics, based on **[DTDLv2](https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v2/DTDL.v2.md)** (**D**igital **T**win **D**efinition **L**anguage) and **[PySide6](https://pypi.org/project/PySide6/)**. It provides a graphical user interface for high-speed data logging and communication with STMicroelectronics hardware devices. The package provides a set of graphical widgets useful to display live data streams, configure, and show connected device parameters and manage data collection. These widgets are the basic building blocks for creating interactive graphical user interfaces (GUIs) to manage datalogging applications and devices configuration.

The package is part of the **[STDATALOG-PYSDK](https://github.com/STMicroelectronics/stdatalog-pysdk)**, which is a set of libraries and tools that enable the development of applications for data logging and data monitoring.

:::

::: {.col-sm-12 .col-lg-8}
# Update History

::: {.collapse}
<input type="checkbox" id="collapse-section4" checked aria-hidden="true">
<label for="collapse-section4" aria-hidden="true">v1.2.1 / 29-Aug-25</label>
<div>


## Main Changes

### Patch Release

- Solved issue #1 - pull request #2: accepted proposal from @YumTaha
- Fixed custom Device Model save and update


</div>
:::

::: {.collapse}
<input type="checkbox" id="collapse-section3" checked aria-hidden="true">
<label for="collapse-section3" aria-hidden="true">v1.2.0 / 20-Jun-25</label>
<div>


## Main Changes

### Maintenance Release

- Added support to Python 3.13
- Removed dependency from matplotlib in HSD_GUI
- Updated ACTUATOR components and properties management, aligned to new fast and slow telemetry DTDL components
- New USB catalog management: sync/update with the online catalog
- Added new dialog to show received PnPL_Error
- Moved query_dtdl_model from DeviceTemplateManager to DeviceCatalogManager class
- Aligned to staiotcraft python latest library version
- Fixed plot threads creation and shutdown + join stopped sensors acquisition threads


</div>
:::

::: {.collapse}
<input type="checkbox" id="collapse-section2" aria-hidden="true">
<label for="collapse-section2" aria-hidden="true">v1.1.0 / 9-Apr-25</label>
<div>


## Main Changes

### Maintenance Release

- **Added macos support.**
- Optimized TagsInfoWidget creation function.
- Fixed SpinBoxes arrows icons + QFrame unwanted borders + CommandWidget button name
- Added support for Vanilla and serial datalogger.


</div>
:::

::: {.collapse}
<input type="checkbox" id="collapse-section1" aria-hidden="true">
<label for="collapse-section1" aria-hidden="true">v1.0.0 / 17-Jan-25</label>
<div>


## Main Changes

### First official release


</div>
:::

:::
:::

<footer class="sticky">
::: {.columns}
::: {.column width="95%"}
For complete documentation,
visit: [www.st.com](https://github.com/STMicroelectronics/stdatalog-pysdk)
:::
::: {.column width="5%"}
<abbr title="Based on template cx566953 version 2.0">Info</abbr>
:::
:::
</footer>
