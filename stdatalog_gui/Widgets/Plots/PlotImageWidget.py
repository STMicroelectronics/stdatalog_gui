 
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

import time
import numpy as np
from functools import partial

from stdatalog_gui.Utils.PlotParams import SensorCameraPlotParams

from PySide6.QtCore import Slot, Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QIcon, QIntValidator, QPainter, QPen, QBrush, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QFrame, QPushButton, QLineEdit, QButtonGroup, QLabel, QGridLayout

import pyqtgraph as pg
from stdatalog_gui.UI.styles import STDTDL_Chip, STDTDL_LineEdit, STDTDL_PushButton
from stdatalog_gui.Utils import UIUtils
from stdatalog_gui.Widgets.Plots.PlotWidget import CustomPGPlotWidget, PlotWidget
from PIL import Image

from PySide6.QtCore import Signal

from pkg_resources import resource_filename
import struct
import io
import math

start_image = resource_filename('stdatalog_gui.UI.images', 'st_logo.png')

# Provided register values
reg_values = {
    0x5381: 0x1e,  # CMX1
    0x5382: 0x5b,  # CMX2
    0x5383: 0x08,  # CMX3
    0x5384: 0x0a,  # CMX4
    0x5385: 0x7e,  # CMX5
    0x5386: 0x88,  # CMX6
    0x5387: 0x7c,  # CMX7
    0x5388: 0x6c,  # CMX8
    0x5389: 0x10,  # CMX9
    0x538A: 0x01,  # CMXSIGN_HIGH (sign for CMX9 in Bit[0])
    0x538B: 0x98,  # CMXSIGN_LOW (signs for CMX1-CMX8)
    0x5380: 0x00   # Assuming CMX_CTRL is 0x00 for 1.7 mode (normalization_factor = 128.0)
}


def yuv_to_rgb(y, u, v):
    # Converti YUV a RGB usando le formule di conversione
    c = y - 16
    d = u - 128
    e = v - 128

    r = (298 * c + 409 * e + 128) >> 8
    g = (298 * c - 100 * d - 208 * e + 128) >> 8
    b = (298 * c + 516 * d + 128) >> 8

    # Clampa i valori RGB tra 0 e 255
    r = np.clip(r, 0, 255)
    g = np.clip(g, 0, 255)
    b = np.clip(b, 0, 255)

    return np.array([r, g, b], dtype=np.uint8)

def yuv_to_rgb_vectorized(y, u, v):
    # Converti YUV a RGB usando le formule di conversione
    # Queste operazioni funzionano direttamente su array NumPy
    c = y - 16
    d = u - 128
    e = v - 128

    r = (298 * c + 409 * e + 128) >> 8
    g = (298 * c - 100 * d - 208 * e + 128) >> 8
    b = (298 * c + 516 * d + 128) >> 8

    # Clampa i valori RGB tra 0 e 255
    # np.clip funziona anche su array
    r = np.clip(r, 0, 255)
    g = np.clip(g, 0, 255)
    b = np.clip(b, 0, 255)

    # Impila i canali RGB lungo un nuovo asse per ottenere (altezza, larghezza, 3)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def yuv_to_rgb_vectorized_width_cmx(y, u, v, cmx_matrix, normalization_factor):
    # Converti YUV a RGB usando le formule di conversione
    # Queste operazioni funzionano direttamente su array NumPy
    c = y - 16
    d = u - 128
    e = v - 128

    # Calcola i valori RGB iniziali come float per mantenere la precisione
    r_linear = (298 * c + 409 * e + 128).astype(np.float32)
    g_linear = (298 * c - 100 * d - 208 * e + 128).astype(np.float32)
    b_linear = (298 * c + 516 * d + 128).astype(np.float32)

    # Applica la normalizzazione dello shift (divisione per 2^8 = 256)
    r_linear /= 256.0
    g_linear /= 256.0
    b_linear /= 256.0

    # 2. Prepara i canali RGB per la moltiplicazione della matrice
    # Impila per ottenere un array di forma (altezza, larghezza, 3)
    rgb_stacked = np.stack([r_linear, g_linear, b_linear], axis=-1)

    # 3. Applica la CMX e la normalizzazione finale
    # Assicurati che cmx_matrix sia un array NumPy 3x3 di float
    # Utilizza .T (trasposta) se la matrice è definita per una post-moltiplicazione (vettore riga)
    # o senza .T se è per pre-moltiplicazione (vettore colonna)
    rgb_corrected = np.dot(rgb_stacked, cmx_matrix.T)
    
    # Applica la normalizzazione finale specificata dal sensore
    rgb_corrected /= normalization_factor

    # 4. Clamping dei valori tra 0 e 255 e conversione a np.uint8
    r = np.clip(rgb_corrected[:, :, 0], 0, 255)
    g = np.clip(rgb_corrected[:, :, 1], 0, 255)
    b = np.clip(rgb_corrected[:, :, 2], 0, 255)

    # Impila i canali RGB lungo un nuovo asse per ottenere (altezza, larghezza, 3)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


class FPSCounter:
    def __init__(self):
        self.start_time = time.time()
        self.frame_count = 0

    def update(self):
        self.frame_count += 1
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0:
            fps = self.frame_count / elapsed_time
            return fps
        else:
            return 0.0


class CustomImagePlotWidget(CustomPGPlotWidget):
    def __init__(self, parent=None, background='default', plotItem=None, **kargs):
        super().__init__(parent, background, plotItem, **kargs)

    def mouseMoveEvent(self, ev):
        pass

class PlotImageWidget(PlotWidget):

    def __init__(self, controller, comp_name, comp_display_name, width, height, plot_label= "", p_id = 0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, plot_label)

        self.plot_label = plot_label
        self.pixel_format = 0
        # Clear PlotWidget inherited graphic elements (mantaining all attributes, functions and signals)
        while self.layout().count():
            item = self.layout().takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        main_layout = QHBoxLayout()

        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_frame = QFrame()
        main_frame.setStyleSheet("QFrame { border-radius: 5px; border: 2px solid rgb(255, 0, 0);}")
        main_frame.setLayout(main_layout)
        
        self.graph_widget = CustomImagePlotWidget(parent = self)

        self.image_height = height
        self.image_width  = width
        self.path_image_start =  start_image

        image = np.array(Image.open(start_image).rotate(-90, expand = True))
                 
        self.img = pg.ImageItem(image)

        self.graph_widget.getPlotItem().clear()
        old_plot_item = self.graph_widget.getPlotItem()
        self.graph_widget.removeItem(old_plot_item)
        self.graph_widget.setAspectLocked(True)
        self.graph_widget.getPlotItem().addItem(self.img)
        self.graph_widget.getPlotItem().showAxes(False)

        self.plot_layout = QHBoxLayout()
        self.plot_frame = QFrame()
        self.plot_frame.setStyleSheet("QFrame { border: transparent;}")
        self.plot_frame.setContentsMargins(0,0,0,0)
        self.plot_frame.setLayout(self.plot_layout)
        self.plot_layout.addWidget(self.graph_widget)

        main_layout.addWidget(self.plot_frame)
        self.adjustSize()
        self.layout().addWidget(main_frame)
        self.data = []
        self.data_end = 0
        self.first_data = 0
        self.resolution_with = 0
        self.resolution_height = 0
        self.bytes_per_pixel = 2
        self.total_bytes = self.image_width * self.image_height * self.bytes_per_pixel
        self.count = 0
        self.count_show = 0
        self.image_start_view =0
        self.image_stop_view  =0

        # Determine normalization factor
        self.cmx_ctrl_val = reg_values[0x5380]
        self.cmx_precision_bit = (self.cmx_ctrl_val >> 1) & 0x01
        self.normalization_factor = 128.0 if self.cmx_precision_bit == 0 else 64.0

        # Extract raw CMX values
        self.cmx_vals_raw = [
            reg_values[0x5381], reg_values[0x5382], reg_values[0x5383],
            reg_values[0x5384], reg_values[0x5385], reg_values[0x5386],
            reg_values[0x5387], reg_values[0x5388], reg_values[0x5389]
        ]

        # Extract sign bits
        self.cmx_sign_low_val = reg_values[0x538B]
        self.cmx_sign_high_val = reg_values[0x538A]
        self.cmx_coeffs_with_signs = []

        # Apply signs for CMX1-CMX8 (assuming bit i of CMXSIGN_LOW is for CMXi+1)
        for i in range(8):
            sign_bit = (self.cmx_sign_low_val >> i) & 0x01
            value = self.cmx_vals_raw[i]
            self.cmx_coeffs_with_signs.append(-value if sign_bit == 1 else value)

        # Apply sign for CMX9 (assuming Bit[0] of CMXSIGN_HIGH is for CMX9)
        self.cmx9_sign_bit = (self.cmx_sign_high_val >> 0) & 0x01
        self.value_cmx9 = self.cmx_vals_raw[8] # CMX9 is the last in the raw list
        self.cmx_coeffs_with_signs.append(-self.value_cmx9 if self.cmx9_sign_bit == 1 else self.value_cmx9)

        # Reshape into a 3x3 NumPy matrix
        self.cmx_matrix = np.array(self.cmx_coeffs_with_signs, dtype=np.float32).reshape((3, 3))
        self.called_update = 0
        self.called_update_and_visualize = 0



    @Slot(bool, int)
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1 or interface == 3:
            if_str = "USB" if interface == 1 else "Serial"
            print(f"Sensor {self.comp_name} is logging via {if_str}: {status}")
            if status:
                self.buffering_timer_counter = 0
                self.timer.start(self.timer_interval_ms)
            else:
                self.data = []
                self.data_end = 0
                self.first_data = 0
                self.timer.stop()
        else: # interface == 0
            print("Component {} is logging on SD Card: {}".format(self.comp_name,status))

    
    def find_jpeg_end_marker(self, buffer):
        #marker = b'\xff\xd9'
        marker = ['0xff', '0xd9']

        hex_array = [hex(x) for x in np.array(buffer).astype(np.uint8)]

        # Iterate through the byte array to find the marker
        for i in range(len(hex_array) - 1):
            if hex_array[i:i+2] == marker:
                return i+2  # Return the first index after the marker
    
        return -1  # Return -1 if the marker is not found
    
    def update_plot(self):

        self.called_update +=1;
        if self.pixel_format == 8:
            self.total_bytes_to_show = len(self.data)
            self.data_end = self.find_jpeg_end_marker(self.data)
            if (self.data_end < 0):
                return
            self.total_bytes = self.data_end

        else:  
            self.total_bytes_to_show = len(self.data)
            self.data_end = self.total_bytes
            
            if (self.total_bytes_to_show < self.total_bytes):
                # print("not enough data to plot {0} < {1}".format(self.total_bytes_to_show, self.total_bytes))
                return
        
        self.called_update_and_visualize +=1;

        #print("Plot called {0} times, visualize called {1} times".format(self.called_update, self.called_update_and_visualize))
            
        # Extract the image data            
        image_data = self.data[0: self.data_end]
        slice_floats = self.data[self.data_end : self.data_end + 8]
        # print("Slice floats:", slice_floats)
        #slice_uint8 = [int(f) for f in slice_floats]
        slice_uint8 = np.array(slice_floats, dtype=np.uint8)  # converte float in uint8 troncando
        data_bytes = bytes(slice_uint8)
        try:
            timestamp_seconds = struct.unpack('<d', data_bytes)[0]
            # print(f"Timestamp decodificato: {timestamp_seconds}")
        except struct.error as e:
            print(f"Errore di struct: {e}")
            # Questo non dovrebbe più accadere, poiché data_bytes è lungo 8.

        #timestamp_seconds = struct.unpack('<d', data_bytes)[0]
        #timestamp_seconds = slice_floats.view(dtype='<d')[0]

        # print(timestamp_seconds) # Debug: stampa il timestamp in secondi

        hours = int(timestamp_seconds // 3600)
        minutes = int((timestamp_seconds % 3600) // 60)
        seconds = int(timestamp_seconds % 60)
        milliseconds = int((timestamp_seconds - int(timestamp_seconds)) * 1000)
        name_file = f"{hours:02d}_{minutes:02d}_{seconds:02d}.{milliseconds:03d}"
        print(name_file) # Debug: stampa il nome del file basato sul timestamp
        
        # Converti i valori in interi
        # Assicurati che i valori siano nel range 0-255
        image_data_int = np.clip(image_data, 0, 255).astype(np.uint8)

        # Converti la lista in un oggetto bytes
        image_bytes = bytes(image_data_int)

        folder = self.controller.get_acquisition_folder()
        # print("folder = {0}".format(folder))
        # Crea il nome del file con il percorso completo
        self.namefile_saved = '{0}/{1}__{2}.raw'.format(folder, self.count_show,name_file)
        # Salva i dati dell'immagine in un file .raw
        
        #with open(self.namefile_saved, 'wb') as file:
        #    # Scrivi i dati nel file
        #    file.write(image_bytes)
        
        # print(f"Saved raw image data to {self.namefile_saved}")

        # print("extract {0} bytes of {1} bytes".format(self.data_end, self.total_bytes_to_show)) # Debug: stampa il numero di byte estratti
        
        # Delete the extracted image data plus the timestamp bytes from the buffer
        del  self.data[0: self.data_end+8]
        #print("remain {0} bytes".format(len(self.data))) # Debug: stampa il numero di byte rimanenti nel buffer
        
        if self.data_end > 0:
            self.data_end = 0
            # fps = self.fps_counter.update()
            # print(f"FPS: {fps:.2f}")
            self.count_show +=1 
            debug_pixel_format = self.pixel_format

            match debug_pixel_format:
                case 0:
                    self.bytes_per_pixel = 2 #RGB565                    
                    uint16_buffer = np.array(image_data, dtype=np.uint8).view(dtype=np.uint16)
                    uint16_buffer = np.reshape(uint16_buffer, ((self.image_height, self.image_width)))
                    
                    # Convert RGB565 to RGB888
                    r = (uint16_buffer >> 11) & 0x1F
                    g = (uint16_buffer >> 5) & 0x3F
                    b = uint16_buffer & 0x1F

                    # Scala i canali a 8 bit
                    r = (r << 3) | (r >> 2)
                    g = (g << 2) | (g >> 4)
                    b = (b << 3) | (b >> 2)

                    # Combina i canali in un array RGB888
                    rgb888_array = np.stack((r, g, b), axis=-1).astype(np.uint8)

                    # Create an image from the numpy array
                    image = Image.fromarray(rgb888_array, 'RGB').rotate(-90, expand=True)
                    # Display the image
                    self.img.setImage(np.array(image))
                    # Save the image
                    self.img.save("{0}/img_565_{1}.bmp".format(folder, self.count_show))
                case 1:
                    self.bytes_per_pixel = 3 #RGB888
                    uint8_buffer = np.array(image_data, dtype=np.uint8).view(dtype=np.uint8)
                    
                    rgb888_array = np.reshape(uint8_buffer, ((self.image_height, self.image_width, 3)))

                    # Create an image from the numpy array
                    image = Image.fromarray(rgb888_array, 'RGB').rotate(-90, expand=True)
                    # Display the image
                    self.img.setImage(np.array(image))
                    # Save the image
                    image.save("{0}/img_888_{1}.bmp".format(folder, self.count_show))
                case 2:
                    self.bytes_per_pixel = 2 #YUV422 

                    yuv422_image = np.array(image_data, dtype=np.uint8).reshape((self.image_height, self.image_width,2))

                    # Estrai i componenti Y
                    Y_all = yuv422_image[:, :, 0] # Tutti i valori Y (sia Y1 che Y2)
                    # Estrai i componenti U e V e li "espandi" per matchare ogni pixel Y
                    # Gli U sono nelle colonne pari del secondo canale (indice 1)
                    U_shared = yuv422_image[:, ::2, 1]
                    # I V sono nelle colonne dispari del secondo canale (indice 1)
                    V_shared = yuv422_image[:, 1::2, 1]

                    # Espandi U e V in modo che ci sia un valore U e V per ogni pixel Y
                    # np.repeat replica ogni elemento lungo un asse specificato
                    U_expanded = np.repeat(U_shared, 2, axis=1)
                    V_expanded = np.repeat(V_shared, 2, axis=1)

                    # Ora puoi passare gli array completi alla funzione di conversione vettorizzata
                    rgb = yuv_to_rgb_vectorized(Y_all, U_expanded, V_expanded)

                    #rgb = yuv_to_rgb_vectorized_width_cmx(Y_all, U_expanded, V_expanded, self.cmx_matrix, self.normalization_factor)


                    # rgb = np.zeros((self.image_height, self.image_width, 3), dtype=np.uint8)

                    # for i in range(self.image_height):
                    #     for j in range(0, self.image_width, 2):
                    #         # Estrai i valori YUV
                    #         y1 = yuv422_image[i, j, 0]
                    #         u = yuv422_image[i, j, 1]
                    #         y2 = yuv422_image[i, j + 1, 0]
                    #         v = yuv422_image[i, j + 1, 1]

                    #         # Converti YUV a RGB
                    #         rgb[i, j] = yuv_to_rgb(y1, u, v)
                    #         rgb[i, j + 1] = yuv_to_rgb(y2, u, v)


                    #uint16_buffer = np.array(image_data, dtype=np.uint8).view(dtype=np.uint16)
                    #yuv422_image = np.reshape(uint16_buffer, ((self.image_height, self.image_width // 2, 2))) #the last param is 2 or 4
            
                    # Convert YUV422 to RGB888
                    #y0 = yuv422_image[:, :, 0]
                    #u = yuv422_image[:, :, 1]
                    #y1 = yuv422_image[:, :, 2]
                    #v = yuv422_image[:, :, 3]

                    # Convert YUV to RGB
                    #u = u - 128
                    #v = v - 128

                    #r0 = y0 + 1.402 * v
                    #g0 = y0 - 0.344136 * u - 0.714136 * v
                    #b0 = y0 + 1.772 * u

                    #r1 = y1 + 1.402 * v
                    #g1 = y1 - 0.344136 * u - 0.714136 * v
                    #b1 = y1 + 1.772 * u

                    #r = np.empty((self.image_height, self.image_width), dtype=np.uint8)
                    #g = np.empty((self.image_height, self.image_width), dtype=np.uint8)
                    #b = np.empty((self.image_height, self.image_width), dtype=np.uint8)

                    #r[:, 0::2] = r0
                    #r[:, 1::2] = r1
                    #g[:, 0::2] = g0
                    #g[:, 1::2] = g1
                    #b[:, 0::2] = b0
                    #b[:, 1::2] = b1
            
                    # Combine the channels into an RGB888 array
                    #rgb888_array = np.stack((r, g, b), axis=-1).astype(np.uint8)
                    #rgb_image = np.stack((r, g, b), axis=-1).astype(np.uint8)

                    # Create an image from the numpy array
                    #image = Image.fromarray(rgb888_array, 'RGB').rotate(-90, expand=True)
                    #image = Image.fromarray(rgb_image, 'RGB').rotate(-90, expand=True)
                    image = Image.fromarray(rgb, 'RGB').rotate(-90, expand=True)
                    # Display the image
                    self.img.setImage(np.array(image))
                    # Save the image
                    image.save("{0}/img_yuv422_{1}.bmp".format(folder, self.count_show))
                case 7:
                    # Extract the image data
                    self.bytes_per_pixel = 1 #Y8
                    y8_buffer = np.array(image_data, dtype=np.uint8)
                    y8_image = np.reshape(y8_buffer, (self.image_height, self.image_width))
                    
                    # Convert Y8 to RGB888 (grayscale to RGB)
                    rgb888_array = np.stack((y8_image, y8_image, y8_image), axis=-1).astype(np.uint8)
                    
                    # Create an image from the numpy array
                    image = Image.fromarray(rgb888_array, 'RGB').rotate(-90, expand=True)
                    # Display the image
                    self.img.setImage(np.array(image))
                    # Save the image
                    image.save("{0}/img_y8_{1}.bmp".format(folder, self.count_show))
                case 8:
                    self.bytes_per_pixel = 1 #JPG
                    uint_buffer = np.array(image_data, dtype=np.float32).astype(np.uint8)
                    byte_array = bytearray(uint_buffer.tobytes())
                    
                    try:
                        image = Image.open(io.BytesIO(byte_array)).rotate(-90, expand = True)
                    except:
                        image = Image.open(start_image).rotate(-90, expand = True)
                        print("An exception occurred")
                    
                    self.img.setImage(np.array(image))
                    # Save the image
                    image.save("{0}}/img_jpg_{1}.bmp".format(folder, self.count_show))
                case _:
                    self.bytes_per_pixel = 0
            #print("remain data len = {0} after plot".format(len(self.data)))
        else:
            print("remain data len = {0} not full to plot".format(len(self.data)))
        
    def update_plot_characteristics(self, plot_params:SensorCameraPlotParams):
        self.pixel_format= plot_params.pixel_format
        self.resolution = plot_params.resolution
        match self.pixel_format:
            case 0:
                self.bytes_per_pixel = 2 #RBG565
            case 1:
                self.bytes_per_pixel = 3 #RGB888
            case 2:
                self.bytes_per_pixel = 2 #YUV422           
            case 7:
                self.bytes_per_pixel = 1 #Y8
            case 8:
                self.bytes_per_pixel = 0 #JPEG
            case _:
                self.bytes_per_pixel = 0
        
        match self.resolution:
            case 0:
                self.image_width = 160
                self.image_height = 120
            case 1:
                self.image_width = 320
                self.image_height = 240
            case 2:
                self.image_width = 480
                self.image_height = 272
            case 3:
                self.image_width = 640
                self.image_height = 480
            case 4:
                self.image_width = 800
                self.image_height = 480
            case _:
                self.image_width = 0
                self.image_height = 0

        self.total_bytes = self.image_width * self.image_height * self.bytes_per_pixel
        # self.packets = math.floor(self.total_bytes / 8112) #TODO 8112 sostituire con pacchetto di send # non piu usato
        print("Update Plot Image Widget")
        #self.app_qt.processEvents()

        
    def add_data(self, data):
        if (self.first_data==0):
            self.first_data+=1
            self.count = 0
            self.fps_counter = FPSCounter()

        # check if the pixel format is not jpeg
        if self.pixel_format != 8:
            lenght=len(data[0])

            # test new protocol for image data with packet number, total packets and length of data in the packet witout timestamp
            # packet format:
            #  Byte  0: Packet number (n)
            #  Byte  1: Total number of packets (tot)
            #  Bytes 2-4: Length of data in the packet (little-endian)
            #  Bytes 6-(6+length-1): Image data
            n = data[0][0]
            tot = data[0][1]
            byte_len_pkg = np.array(data[0][2:4], dtype=np.uint8)
            # Little-endian
            number_le = struct.unpack('<H', byte_len_pkg)[0]  # little-endian unsigned short
            
            #print("pacchetto = {0} of {1} pixel data len {2}".format(n, tot, number_le)) # Debug: stampa il numero di pacchetto, totale pacchetti e lunghezza dati
            
            if number_le > 0:
                # if the packet is not the last one extend data with number_le bytes without the protocol header and timestamp
                # else if is the last packet extend data data with number_le bytes without the protocol header but including the final 8 bytes for the timestamp
                if (n < tot ):
                    self.data.extend(data[0][4:4+number_le])
                else:
                    self.data.extend(data[0][4:4+number_le+8])
                    # if is the last packet update fps
                    fps = self.fps_counter.update()
                    #print(f"FPS: {fps:.2f}")
            else:
                print("dati non arrivati")

            #old code without image protocol and packet number with length of data 8112 for each packet

            # self.packets = math.floor(self.total_bytes / 8112) #TODO 8112 sostituire con pacchetto di send

            # if lenght > 0:
            #     if (self.count < self.packets ): #28):
            #         self.data.extend(data[0][0:lenght])
            #         # debug
            #         print("{1} extend data len = {0}".format(lenght, self.count))
            #         self.count +=1
            #     else:
            #         lenght= (self.total_bytes - (self.count* 8112)) #TODO 8112 sostituire con pacchetto di send
            #         self.data.extend(data[0][0:lenght])
            #         # debug
            #         print("{1} extend data len = {0}".format(lenght, self.count))
            #         self.count = 0
            #         fps = self.fps_counter.update()
            #         print(f"FPS: {fps:.2f}")
            # else:
            #     print("dati non arrivati")
            #     #self.data.clear()          
        else:
            # its necessary update the jpeg with the same protocol shown before, this part is the older one
            lenght=len(data[0])
            print("numero di dati {0}".format(lenght))
            if lenght > 0:
                self.data_end_marker = self.find_jpeg_end_marker(data[0])
                lenght = self.data_end_marker if self.data_end_marker > 0 else lenght
                self.data.extend(data[0][0:lenght])
            else:
                print("dati non arrivati")
                #self.data.clear()
