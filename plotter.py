import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import numpy as np
from pyqtgraph.Qt import QtCore

def create_plot_widget():
    tz = QtCore.QTimeZone(7200)  # UTC+1
    win = pg.GraphicsLayoutWidget(show=True, title="Temperature Graph")
    plot = win.addPlot(title="Temperature (°C)", axisItems={'bottom': DateAxisItem(timezone=tz)})
    plot.setLabel('left', 'Temperature', units='°C')
    plot.setLabel('bottom', 'Time (Local)')
    curve = plot.plot(pen='y')
    return win, plot, curve

def update_plot(curve, times: list[float], temperatures: list[float]):
    if times and temperatures:
        time_array = np.array(times)
        temp_array = np.array(temperatures)
        curve.setData(time_array, temp_array)
    else:
        curve.setData([], [])  # Clear plot if no data