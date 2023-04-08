# <Open-JIPtoCSV Operates "Open-JIP" which is an Open-source Chlorophyll fluorometer>
# Copyright (C) <2020>  <Harvey Bates>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

# For more information contact: harvey_bates@hotmail.com

import sys
import csv
import glob
import serial
import time
import datetime
from time import strftime
import plotly.graph_objects as go
import atexit

# Custom exception classes
class UnsupportedPlatformError(Exception):
    pass
class NoUSBDevicesFoundError(Exception):
    pass
class NoDataInCSVError(Exception):
    pass
class MeasurementError(Exception):
    pass
class ParameterError(Exception):
    pass
class CSVError(Exception):
    pass


usb_baudrate = 115200  # Baudrate to match Teensy
fileName = "Open-JIP_Data.csv"  # Filename of output .csv file
fo_pos = 3

def serial_ports():
    # List serial ports available on each OS
    # For windows OS
    if sys.platform.startswith('win'):
        ports = [f'COM{i + 1}' for i in range(256)]
    # For linux OS
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        ports = glob.glob('/dev/tty[A-Za-z]*')
    # For Mac OS
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise UnsupportedPlatformError('Unsupported platform')

    result = [port for port in ports if not any(x in port for x in ['Bluetooth'])]

    if not result:
        raise NoUSBDevicesFoundError("No USB devices found. Ensure Open-JIP is plugged in.")
    return result

def connect(portAddress):
    # Connect to the Open-JIP fluorometer (Teensy Microcontroller)
    global openJIP
    if len(portAddress) > 1 and not isinstance(portAddress, str):
        print("Which port do you want to connect to:")
        for i, port in enumerate(portAddress):
            print(f"\t{i}. {port}")
        portID = int(input("Port number: "))
        print(f"Port {portAddress[portID]} selected.")
    else:
        portID = 0

    try:
        openJIP = serial.Serial(portAddress[portID], usb_baudrate) # Connect to Teensy
        print("Connected to Open-JIP fluorometer." if openJIP.is_open else "Open-JIP USB device not found.")
    except serial.SerialException as e:
        raise serial.SerialException(f"Failed to connect to Open-JIP fluorometer: {e}")

def set_gain():
    gain = input("Set the detection gain: (1 (Lowest) - 4 (Highest))")
    if 1 <= int(gain) <= 4:
        openJIP.flush()
        time.sleep(0.2)
        openJIP.write(f'F{gain}\n'.encode('utf-8'))
        print(f"Gain set to: {gain}")
    else:
        print("Invalid detection gain. Default settings will be used.")

def set_intensity():
    intensity = input("Set the actinic LED intensity: (1 (Lowest) - 4 (Highest))")
    if 1 <= int(intensity) <= 4:
        openJIP.flush()
        time.sleep(0.2)
        openJIP.write(f'A{intensity}\n'.encode('utf-8'))
        print(f"Actinic intensity set to: {intensity}")
    else:
        print("Invalid actinic intensity. Default settings will be used.")

def measure_fluorescence(readLength):
    # Read fluorescence and create two arrays of corresponding values
    try:
        print("Measuring fluorescence, please wait...")
        openJIP.flush()  # Clear serial buffer
        time.sleep(1)  # Wait for Teensy to reset
        openJIP.write(b'MF')  # Send command to Teensy to start measuring fluorescence
        
        timeStamps, fluorescenceValues = zip(
            *[
                tuple(map(float, openJIP.readline().decode("utf-8").strip().split("\t")))
                for _ in range(readLength)
            ]
        )  # Read fluorescence values from Teensy
        
        if len(timeStamps) != readLength or len(fluorescenceValues) != readLength:
            raise MeasurementError("Incomplete measurement data received.")
        
        print("Transient captured.")
        return timeStamps, fluorescenceValues  # Return two arrays to be passed into csv upload function
    except MeasurementError as e:
        print(f"Error: {e}")
        return [], []
    
def calculate_parameters(fluorescenceValues, timeStamps):
    # Calculate fluorescence parameters
    try:
        if not fluorescenceValues or not timeStamps:
            raise ParameterError("Empty data received. Cannot calculate parameters.")
        
        fo = fluorescenceValues[fo_pos]
        fm = max(fluorescenceValues[2:])
        fj_found = False
        fi_found = False

        for i, t in enumerate(timeStamps):
            if not fj_found and int(t) == 2:
                fj, fj_time = fluorescenceValues[i], t
                fj_found = True
            elif not fi_found and int(t) == 30:
                fi, fi_time = fluorescenceValues[i], t
                fi_found = True

        fv = fm - fo
        quantumYield = fv / fm

        print(f"Fo: {fo}\nFj: {fj} at {fj_time}\nFi: {fi} at {fi_time}\nFm: {fm}\nFv: {fv}\nQuantum yield: {round(quantumYield, 3)}")
    except ParameterError as e:
        print(f"Error: {e}")

def get_data_from_csv(fileName):
    # Get data from .csv file
    try:
        readTimes, timeStamps, fluorescenceValues = [], [], []

        with open(fileName, 'r') as f:
            rows = list(csv.reader(f))
            
            if not rows:
                raise CSVError(f"No data found in {fileName}.")
            
            for row in rows:
                readTimes.append(row[0][11:])
                timeStamps.append([float(s) for s in row[1].split(',')])
                fluorescenceValues.append([float(s) for s in row[2].split(',')])
        return readTimes, timeStamps, fluorescenceValues
    except CSVError as e:
        print(f"Error: {e}")
        return [], [], []

def measure_fluorescence(readLength):
    # Read fluorescence and create two arrays of corresponding values
    try:
        print("Measuring fluorescence, please wait...")
        openJIP.flush()  # Clear serial buffer
        time.sleep(1)  # Wait for Teensy to reset
        openJIP.write(b'MF')  # Send command to Teensy to start measuring fluorescence
        
        timeStamps, fluorescenceValues = zip(
            *[
                tuple(map(float, openJIP.readline().decode("utf-8").strip().split("\t")))
                for _ in range(readLength)
            ]
        )  # Read fluorescence values from Teensy
        
        if len(timeStamps) != readLength or len(fluorescenceValues) != readLength:
            raise MeasurementError("Incomplete measurement data received.")
        
        print("Transient captured.")
        return timeStamps, fluorescenceValues  # Return two arrays to be passed into csv upload function
    except MeasurementError as e:
        print(f"Error: {e}")
        return [], []
