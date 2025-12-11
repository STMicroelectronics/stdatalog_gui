
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

import setuptools
import os

with open("LICENSE.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="stdatalog_gui",
    version="1.3.0",
    author="SRA-ASP",
    author_email="matteo.ronchi@st.com",
    description="STMicroelectronics UI Toolkit based on DTDL and PySide6.",
    long_description=long_description,
    long_description_content_type="text\\markdown",
    include_package_data=True,    
    url="https://github.com/STMicroelectronics/stdatalog_gui",
    packages=setuptools.find_packages(),
    package_dir={'stdatalog_gui': 'stdatalog_gui'},
    license='BSD 3-clause',
    classifiers=[
        "License :: BSD License (BSD-3-Clause)",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Embedded Systems"
    ],
    install_requires=[
        "stdatalog_pnpl==1.3.0",
        "stdatalog_core==1.3.0",
        "stdatalog_dtk==1.3.0",
        "numpy==2.3.4",
        "pyqtgraph==0.13.7",
        "setuptools<81",
        "pyaudio==0.2.14",
        "PySide6==6.10.0; platform_system == 'Windows'",
        "PySide6==6.10.0; platform_system == 'Linux' and platform_machine != 'aarch64'",
        "PySide6==6.8.0.2; platform_system == 'Linux' and platform_machine == 'aarch64'",
        "PySide6==6.9.0; platform_system == 'Darwin' and platform_machine == 'arm64'",
        "PySide6==6.7.3; platform_system == 'Darwin' and platform_machine == 'x86_64'"
    ]
)