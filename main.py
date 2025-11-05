from utils import get_latest_temperature_data
device02_latest_value = get_latest_temperature_data('device02')
device01_latest_value = get_latest_temperature_data('device01')
print(device01_latest_value)
print(device02_latest_value)

import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import numpy as np
import sys

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="Temperature Live Graph")

plot = win.addPlot(title="Temperature")
curve = plot.plot(pen='y')

data = np.linspace(0, 2*np.pi, 1000)
phase = 0

def update():
    global phase
    #y = device02_latest_value;
    y = np.sin(data + phase)
    curve.setData(y)
    phase += 0.1

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(50)  # update every 50 ms (20 Hz)

sys.exit(app.exec())