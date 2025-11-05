from utils import get_latest_temperature_data, get_temperature_data_in_range
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import numpy as np
import sys
from collections import deque
import datetime

# Initialize data structures for live plotting
max_points = 100  # Keep last 100 points
times = deque(maxlen=max_points)
temperatures = deque(maxlen=max_points)

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="Temperature Live Graph")

plot = win.addPlot(title="Temperature (°C)")
plot.setLabel('left', 'Temperature', units='°C')
plot.setLabel('bottom', 'Time', units='s')
curve = plot.plot(pen='y')

def fetch_data():
    global times, temperatures
    try:
        latest_temp = get_latest_temperature_data('device02')
        if latest_temp is not None:
            current_time = datetime.datetime.now().timestamp()
            times.append(current_time)
            temperatures.append(latest_temp)
    except Exception as e:
        print(f"Error fetching data: {e}")

def update_plot():
    if times and temperatures:
        # Convert to numpy arrays for plotting
        time_array = np.array(list(times))
        temp_array = np.array(list(temperatures))
        # Make times relative to the first point for better visualization
        if len(time_array) > 1:
            time_array -= time_array[0]
        curve.setData(time_array, temp_array)

# Timer for fetching data every 5 seconds
data_timer = QtCore.QTimer()
data_timer.timeout.connect(fetch_data)
data_timer.start(5000)  # 5000 ms = 5 seconds

# Timer for updating plot every 50 ms
plot_timer = QtCore.QTimer()
plot_timer.timeout.connect(update_plot)
plot_timer.start(50)

# Fetch initial data
fetch_data()

sys.exit(app.exec())