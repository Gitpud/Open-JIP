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
        raise EnvironmentError('Unsupported platform')

    result = [port for port in ports if not any(x in port for x in ['Bluetooth'])]

    if not result:
        raise IndexError("No USB devices found. Ensure Open-JIP is plugged in.")
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

    openJIP = serial.Serial(portAddress[portID], usb_baudrate) # Connect to Teensy
    print("Connected to Open-JIP fluorometer." if openJIP.is_open else "Open-JIP USB device not found.")

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
    print("Measuring fluorescence, please wait...")
    openJIP.flush() # Clear serial buffer
    time.sleep(1) # Wait for Teensy to reset
    openJIP.write(b'MF') # Send command to Teensy to start measuring fluorescence
    timeStamps, fluorescenceValues = zip(*[tuple(map(float, openJIP.readline().decode("utf-8").strip().split("\t"))) for _ in range(readLength)]) # Read fluorescence values from Teensy
    print("Transient captured.")
    return timeStamps, fluorescenceValues # Return two arrays to be passed into csv upload function

def calculate_parameters(fluorescenceValues, timeStamps):
    # Calculate fluorescence parameters
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

def upload(timeStamps, fluorescenceValues):
    # Upload fluorescence data to .csv file
    print(f"Uploading to {fileName}, please wait...")
    currentTime = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S") # Get current time
    
    with open(fileName, 'a') as f:
        writer = csv.writer(f)
        writer.writerow([currentTime, ", ".join(map(str, timeStamps)), ", ".join(map(str, fluorescenceValues))]) # Write data to .csv file
        print(f"Data written to {fileName}.")

def query_user_plot():
    # Ask user if they want to plot data
    plotData = input(f"Would you like to plot data from {fileName}? (y/n)")

    if plotData.lower() == "y":
        readTimes, timeStamps, fluorescenceValues = get_data_from_csv(fileName)
        plot_transients(readTimes, timeStamps, fluorescenceValues)
    else:
        print("Exiting.")

def get_data_from_csv(fileName):
    # Get data from .csv file
    readTimes, timeStamps, fluorescenceValues = [], [], []

    with open(fileName, 'r') as f:
        for row in csv.reader(f):
            if row:
                readTimes.append(row[0][11:])
                timeStamps.append([float(s) for s in row[1].split(',')])
                fluorescenceValues.append([float(s) for s in row[2].split(',')])
            else:
                raise IndexError(f"No data found in {fileName}.")
    return readTimes, timeStamps, fluorescenceValues

def plot_transients(readTimes, timeStamps, fluorescenceValues):
    # Plot fluorescence transients
    print(f"Plotting data from {fileName}, please wait...")

    updatemenus = [{
        'active': 1,
        'buttons': [{
            'label': 'Logarithmic Scale',
            'method': 'update',
            'args': [{'visible': [True, True]}, {'xaxis': {'type': 'log'}}]
        }, {
            'label': 'Linear Scale',
            'method': 'update',
            'args': [{'visible': [True, True]}, {'xaxis': {'type': 'linear'}}]
        }]
    }]

    data = [go.Scatter(x=times, y=values, mode='markers', name=f"Transient{index+1} at {readTime}") for index, (readTime, times, values) in enumerate(zip(readTimes, timeStamps, fluorescenceValues))]
    
    layout = {'updatemenus': updatemenus, 'title': 'Open-JIP Transients'}
    fig = go.Figure(data=data, layout=layout)
    fig.update_xaxes(title_text="Time (ms)")
    fig.update_yaxes(title_text="Fluorescence (V)")
    fig.layout.template = "seaborn"
    fig.show()

def close():
    if openJIP.is_open:
        openJIP.close()
        print("Exited cleanly.")

atexit.register(close)

if __name__ == "__main__":
    port = serial_ports()
    connect(port)
    measure = input("Do you want to measure an OJIP curve now? (y/n)")
    if measure.lower() == "y":
        adjust = input("Set gain and actinic intensity? (y/n)")
    if adjust.lower() == "y":
            set_intensity()
            set_gain()
    timeStamps, fluorescenceValues = measure_fluorescence(2000)
    calculate_parameters(fluorescenceValues, timeStamps)
    upload(timeStamps, fluorescenceValues)
    query_user_plot()
else:
    print("Exiting...")
