# stdatalog_gui

![latest tag](https://img.shields.io/github/v/tag/STMicroelectronics/stdatalog_gui.svg?color=brightgreen)

The **[stdatalog_gui](https://github.com/STMicroelectronics/stdatalog_gui)** package is a UI toolkit developed by STMicroelectronics, based on **[DTDLv2](https://github.com/Azure/opendigitaltwins-dtdl/blob/master/DTDL/v2/DTDL.v2.md)** (**D**igital **T**win **D**efinition **L**anguage) and **[PySide6](https://pypi.org/project/PySide6/)**. It provides a graphical user interface for high-speed data logging and communication with STMicroelectronics hardware devices. The package provides a set of graphical widgets useful to display live data streams, configure, and show connected device parameters and manage data collection. These widgets are the basic building blocks for creating interactive graphical user interfaces (GUIs) to manage datalogging applications and devices configuration.

The package is part of the **[STDATALOG-PYSDK](https://github.com/STMicroelectronics/stdatalog-pysdk)**, which is a set of libraries and tools that enable the development of applications for data logging and data monitoring.

The package offers a set of base classes and utilities to create custom GUI applications for data logging and device configuration and two packeges that specialize the base classes for specific use cases:
- **HSD_GUI:** a package that provides a set of widgets to create GUI applications for high-speed data logging. It includes widgets to display live data streams, configure and show connected device parameters, and manage data collection.
- **HSD_MC_GUI:** a package that provides a set of widgets to create GUI applications for high-speed data logging in the context of motor control applications. It includes widgets to display motor control telemetries, and to configure and control connected motors parameters.

## Features

- Creation of data logging GUI applications
- Customizable GUI widgets
- Live data streams display
- Device discovery and connection
- Device configuration and control
- Application logging and error management display
- Support for multiple platforms (Windows, Linux)
- Compatible with Python 3.10 to 3.12
- Communication with various hardware devices

## Installation

To install the `stdatalog_gui` package, use the following command:

```sh
pip install stdatalog_gui
```

The package could also be installed as part of the **STDATALOG-PYSDK** by launching the SDK installation script from the SDK root folder:

On Windows:
```sh
.\STDATALOG-PYSDK_install.bat
```

On Linux:
```sh
./STDATALOG-PYSDK_install.sh
```

## Requirements
The package requires the following dependencies:

- **[stdatalog_pnpl](https://github.com/STMicroelectronics/stdatalog_pnpl)**
- **[stdatalog_core](https://github.com/STMicroelectronics/stdatalog_core)**
- **[stdatalog_dtk](https://github.com/STMicroelectronics/stdatalog_dtk)**
- numpy==1.26.4
- pyqtgraph
- setuptools
- PySide6==6.6.1
- pyaudio

## Usage
Here is a basic example of how to use the `stdatalog_gui` package to create a simple GUI application (HSD_GUI) for high-speed data logging:
> NOTE: Please, connect a compatible device (board flashed with FP-SNS-DATALOG2 or FP-IND-DATALOGMC) to your PC before running the example 

```python
from PySide6.QtWidgets import QApplication
from stdatalog_gui.HSD_GUI.HSD_MainWindow import HSD_MainWindow

# Create the Qt application
app = QApplication([])

# Create the main window
main_window = HSD_MainWindow(app)
# show the main window
main_window.show()
# set application properties
main_window.setAppTitle("Your Application Title")
main_window.setAppCredits("Your Application Credits")
main_window.setWindowTitle("Your Application Window Title")
main_window.setAppVersion("Your Application Version")
main_window.setLogMsg("A message to display when the logging process starts")
main_window.showMaximized()

# execute the Qt application
app.exec()
```
For more complete examples, please refer to the following STDATALOG-PYSDK examples:
- **[stdatalog_gui.py](https://github.com/STMicroelectronics/stdatalog_examples/blob/main/gui_applications/stdatalog/GUI/stdatalog_gui.py)**
- **[stdatalog_mc_gui.py](https://github.com/STMicroelectronics/stdatalog_examples/blob/main/gui_applications/stdatalog_mc/Datalog/stdatalog_MC_GUI.py)**
- **[stdatalog_MC_AI_GUI.py](https://github.com/STMicroelectronics/stdatalog_examples/blob/main/gui_applications/stdatalog_mc/AI/stdatalog_MC_AI_GUI.py)**
- **[ultrasound_fft_app.py](https://github.com/STMicroelectronics/stdatalog_examples/blob/main/gui_applications/stdatalog_ultrasound_fft/ultrasound_fft_app.py)**

## License
This project is licensed under the BSD 3-Clause License - see the LICENSE.md file for details.
