import pyqtgraph as pg
from pyqtgraph import DateAxisItem
from pyqtgraph.Qt import QtCore
import numpy as np

def create_plot_widget():
    tz = QtCore.QTimeZone(3600)  # UTC+1
    win = pg.GraphicsLayoutWidget(show=True, title="Temperature Graph")
    plot = win.addPlot(title="Temperature (°C)", axisItems={'bottom': DateAxisItem(timezone=tz)})
    plot.setLabel('left', 'Temperature', units='°C')
    plot.setLabel('bottom', 'Time (Local)')
    curve = plot.plot(pen='y')
    line_curve = plot.plot(pen=pg.mkPen('r', dash=[4, 2]))  # Dashed line
    return win, plot, curve, line_curve

def update_plot(curve, line_curve, times: list[float], temperatures: list[float]):
    if times and temperatures:
        time_array = np.array(times)
        temp_array = np.array(temperatures)
        curve.setData(time_array, temp_array)
    else:
        curve.setData([], [])
        line_curve.setData([], [])