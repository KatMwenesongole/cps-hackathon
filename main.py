import sys
from datetime import datetime, timedelta, timezone
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

from utils import get_temperature_data_in_range

# -------- Configuration -------- #
WINDOW_PAST_SEC = 600          # show 10 min of history
UPDATE_INTERVAL_MS = 5000      # refresh every 5s
FUTURE_POINTS = 15             # number of forecast points
FORECAST_VALUES = {            # target temperature per device
    "device01": 28.7,
    "device02": 28.4
}

# -------- PyQtGraph setup -------- #
pg.setConfigOptions(antialias=True)

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="Temperature Live Graph")

axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation='bottom')
plot = win.addPlot(title="Device Temperatures", axisItems={'bottom': axis})
plot.setLabel('left', 'Temperature (°C)')
plot.setLabel('bottom', 'Time (UTC)')
plot.addLegend()

# Real data curves
curve1 = plot.plot(pen='r', name='device01')
curve2 = plot.plot(pen='y', name='device02')

# Forecast curves (same color for both)
forecast_curve1 = plot.plot(pen=pg.mkPen('m', width=2, style=QtCore.Qt.PenStyle.DashLine), name='device01 forecast')
forecast_curve2 = plot.plot(pen=pg.mkPen('m', width=2, style=QtCore.Qt.PenStyle.DashLine), name='device02 forecast')


# -------- Update function -------- #
def update():
    # Compute query window
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(seconds=WINDOW_PAST_SEC)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = ""  # until now

    # Get data
    times1, temps1 = get_temperature_data_in_range("device01", start_str, end_str)
    times2, temps2 = get_temperature_data_in_range("device02", start_str, end_str)

    times1 = np.array(times1 or [], dtype=float)
    times2 = np.array(times2 or [], dtype=float)

    if not len(times1) and not len(times2):
        print("No data in range yet...")
        return

    # --- Real data plotting ---
    if len(times1) and len(temps1):
        curve1.setData(times1, temps1)
    else:
        curve1.clear()

    if len(times2) and len(temps2):
        curve2.setData(times2, temps2)
    else:
        curve2.clear()

    # Determine latest timestamps for each
    t_max1 = times1[-1] if len(times1) else None
    t_max2 = times2[-1] if len(times2) else None

    # Determine common dt (sampling interval)
    combined_times = np.concatenate([times1, times2]) if len(times1) and len(times2) else (times1 if len(times1) else times2)
    if len(combined_times) > 1:
        sorted_t = np.sort(combined_times)
        diffs = np.diff(sorted_t)
        dt = np.median(diffs[diffs > 0]) if np.any(diffs > 0) else 10.0
    else:
        dt = 10.0

    # --- Forecast for device01 ---
    if t_max1 is not None:
        forecast_times1 = t_max1 + dt * np.arange(1, FUTURE_POINTS + 1, dtype=float)
        forecast_vals1 = np.full_like(forecast_times1, FORECAST_VALUES["device01"], dtype=float)
        forecast_curve1.setData(forecast_times1, forecast_vals1)
    else:
        forecast_curve1.clear()

    # --- Forecast for device02 ---
    if t_max2 is not None:
        forecast_times2 = t_max2 + dt * np.arange(1, FUTURE_POINTS + 1, dtype=float)
        forecast_vals2 = np.full_like(forecast_times2, FORECAST_VALUES["device02"], dtype=float)
        forecast_curve2.setData(forecast_times2, forecast_vals2)
    else:
        forecast_curve2.clear()

    # --- X range ---
    latest_real = max([t for t in [t_max1, t_max2] if t is not None])
    rightmost = latest_real + FUTURE_POINTS * dt
    plot.setXRange(latest_real - WINDOW_PAST_SEC, rightmost)


# -------- Timer -------- #
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(UPDATE_INTERVAL_MS)

# Initial draw
update()

sys.exit(app.exec())