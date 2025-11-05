import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from pyqtgraph.graphicsItems.DateAxisItem import DateAxisItem

from utils import get_temperature_data_in_range

# -------- Configuration -------- #
WINDOW_PAST_SEC = 600          # 10 min of history to the left
WINDOW_FUTURE_SEC = 600        # 10 min of forecast to the right
UPDATE_INTERVAL_MS = 5000      # refresh every 5s
FORECAST_WINDOW = 64           # last N points used for trend
FUTURE_POINTS = 40             # forecast points across the horizon


# -------- Custom Axis: DateAxis + "NOW" label -------- #
class NowDateAxis(DateAxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.latest_ts = None

    def set_latest(self, ts):
        self.latest_ts = ts

    def tickStrings(self, values, scale, spacing):
        labels = super().tickStrings(values, scale, spacing)
        if self.latest_ts is None:
            return labels
        for i, v in enumerate(values):
            if abs(v - self.latest_ts) <= spacing / 2:
                labels[i] = "NOW"
        return labels


# -------- PyQtGraph setup -------- #
pg.setConfigOptions(antialias=True)

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="Temperature Live Graph")

axis = NowDateAxis(orientation='bottom')
plot = win.addPlot(title="Device Temperatures", axisItems={'bottom': axis})
plot.setLabel('left', 'Temperature (°C)')
plot.setLabel('bottom', 'Time')
plot.addLegend()

# -------- Curve Styles -------- #
# Real data with solid line + circular markers
real_style_device1 = dict(pen=pg.mkPen('r', width=2),
                          symbol='o',
                          symbolSize=3,
                          symbolBrush=(255, 100, 100, 180))

real_style_device2 = dict(pen=pg.mkPen('y', width=2),
                          symbol='o',
                          symbolSize=3,
                          symbolBrush=(255, 255, 150, 180))

# Forecast data with dashed line + hollow points
forecast_style = dict(pen=pg.mkPen('m', width=2, style=QtCore.Qt.PenStyle.DashLine),
                      symbol='o',
                      symbolSize=3,
                      symbolBrush=(255, 200, 255, 80),
                      symbolPen=pg.mkPen('m', width=1))

# Curves
curve1 = plot.plot(name='device01', **real_style_device1)
curve2 = plot.plot(name='device02', **real_style_device2)
forecast_curve1 = plot.plot(name='device01 forecast', **forecast_style)
forecast_curve2 = plot.plot(name='device02 forecast', **forecast_style)


# -------- Forecast helper (linear trend) -------- #
def compute_forecast_line(times: np.ndarray,
                          temps: list[float],
                          window: int,
                          horizon_sec: float,
                          n_future: int):
    if times.size < 2 or not temps:
        return None, None

    temps_arr = np.array(temps, dtype=float)
    if temps_arr.size > window:
        temps_arr = temps_arr[-window:]
        times_window = times[-window:]
    else:
        times_window = times

    t_last = times_window[-1]
    x = times_window - t_last
    y = temps_arr

    if np.allclose(x, x[0]):
        return None, None

    # Linear regression: y ≈ a*x + b
    a, b = np.polyfit(x, y, 1)
    y_last = y[-1]
    delta = y_last - b
    b_adj = b + delta

    # Generate 10 minutes of forecast
    future_x = np.linspace(horizon_sec / n_future, horizon_sec, n_future)
    future_y = a * future_x + b_adj
    future_times = t_last + future_x
    return future_times, future_y


# -------- Update function -------- #
def update():
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(seconds=WINDOW_PAST_SEC)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = ""

    times1, temps1 = get_temperature_data_in_range("device01", start_str, end_str)
    times2, temps2 = get_temperature_data_in_range("device02", start_str, end_str)

    times1 = np.array(times1 or [], dtype=float)
    times2 = np.array(times2 or [], dtype=float)

    if not len(times1) and not len(times2):
        axis.set_latest(None)
        for c in (curve1, curve2, forecast_curve1, forecast_curve2):
            c.clear()
        return

    # --- Real data ---
    if len(times1) and temps1:
        curve1.setData(times1, temps1)
    else:
        curve1.clear()

    if len(times2) and temps2:
        curve2.setData(times2, temps2)
    else:
        curve2.clear()

    # --- Latest timestamp (NOW) ---
    t_max1 = times1[-1] if len(times1) else None
    t_max2 = times2[-1] if len(times2) else None
    latest_candidates = [t for t in (t_max1, t_max2) if t is not None]
    if not latest_candidates:
        axis.set_latest(None)
        forecast_curve1.clear()
        forecast_curve2.clear()
        return

    t_latest = max(latest_candidates)
    axis.set_latest(t_latest)

    # --- Forecasts for each device (10-min horizon) ---
    if len(times1) and temps1:
        f_times1, f_vals1 = compute_forecast_line(times1, temps1,
                                                  FORECAST_WINDOW,
                                                  WINDOW_FUTURE_SEC,
                                                  FUTURE_POINTS)
        forecast_curve1.setData(f_times1, f_vals1 if f_vals1 is not None else [])
    else:
        forecast_curve1.clear()

    if len(times2) and temps2:
        f_times2, f_vals2 = compute_forecast_line(times2, temps2,
                                                  FORECAST_WINDOW,
                                                  WINDOW_FUTURE_SEC,
                                                  FUTURE_POINTS)
        forecast_curve2.setData(f_times2, f_vals2 if f_vals2 is not None else [])
    else:
        forecast_curve2.clear()

    # --- Center NOW in view ---
    left = t_latest - WINDOW_PAST_SEC
    right = t_latest + WINDOW_FUTURE_SEC
    plot.setXRange(left, right)


# -------- Timer -------- #
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(UPDATE_INTERVAL_MS)

update()
sys.exit(app.exec())