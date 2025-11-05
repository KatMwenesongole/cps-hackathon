import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from pyqtgraph.graphicsItems.DateAxisItem import DateAxisItem

from utils import get_temperature_data_in_range

# -------- Configuration -------- #
WINDOW_PAST_SEC = 600          # show 10 min of history to the left of latest
UPDATE_INTERVAL_MS = 5000      # refresh every 5s
FUTURE_POINTS = 15             # number of forecast points
FORECAST_WINDOW = 64           # how many last measurements to average per device


# -------- Custom Axis: DateAxis + "NOW" label -------- #
class NowDateAxis(DateAxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.latest_ts = None  # epoch seconds of the latest measurement

    def set_latest(self, ts: float | None):
        self.latest_ts = ts

    def tickStrings(self, values, scale, spacing):
        # normal date/time labels first
        labels = super().tickStrings(values, scale, spacing)
        if self.latest_ts is None:
            return labels

        # Replace the label closest to latest_ts with "NOW"
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

# Real data curves
curve1 = plot.plot(pen='r', name='device01')
curve2 = plot.plot(pen='y', name='device02')

# Forecast curves (same colour, dashed)
forecast_curve1 = plot.plot(
    pen=pg.mkPen('m', width=2, style=QtCore.Qt.PenStyle.DashLine),
    name='device01 forecast'
)
forecast_curve2 = plot.plot(
    pen=pg.mkPen('m', width=2, style=QtCore.Qt.PenStyle.DashLine),
    name='device02 forecast'
)


# -------- Helper: compute constant forecast from last N measurements -------- #
def compute_forecast_value(temps: list[float], window: int) -> float | None:
    """Return mean of last `window` measurements (or None if not enough data)."""
    if not temps:
        return None
    # take up to last `window` values
    window_vals = temps[-window:] if len(temps) > window else temps
    # guard in case of weird non-numeric entries
    arr = np.array(window_vals, dtype=float)
    if arr.size == 0:
        return None
    return float(arr.mean())


# -------- Update function -------- #
def update():
    # Time window for query (absolute UTC)
    now_utc = datetime.now(timezone.utc)
    start_utc = now_utc - timedelta(seconds=WINDOW_PAST_SEC)

    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = ""  # your API uses "" for "until now"

    # Fetch data for both devices
    times1, temps1 = get_temperature_data_in_range("device01", start_str, end_str)
    times2, temps2 = get_temperature_data_in_range("device02", start_str, end_str)

    times1 = np.array(times1 or [], dtype=float)
    times2 = np.array(times2 or [], dtype=float)

    if not len(times1) and not len(times2):
        print("No data in range yet...")
        axis.set_latest(None)
        curve1.clear()
        curve2.clear()
        forecast_curve1.clear()
        forecast_curve2.clear()
        return

    # ---- Real data curves ----
    if len(times1) and temps1:
        curve1.setData(times1, temps1)
    else:
        curve1.clear()

    if len(times2) and temps2:
        curve2.setData(times2, temps2)
    else:
        curve2.clear()

    # Latest real timestamp for each device
    t_max1 = times1[-1] if len(times1) else None
    t_max2 = times2[-1] if len(times2) else None

    # Latest across both -> label as NOW
    latest_ts_candidates = [t for t in (t_max1, t_max2) if t is not None]
    if not latest_ts_candidates:
        axis.set_latest(None)
        forecast_curve1.clear()
        forecast_curve2.clear()
        return

    t_latest = max(latest_ts_candidates)
    axis.set_latest(t_latest)

    # ---- Determine approximate sampling interval dt ----
    combined_times = (
        np.concatenate([times1, times2])
        if len(times1) and len(times2)
        else (times1 if len(times1) else times2)
    )
    if len(combined_times) > 1:
        sorted_t = np.sort(combined_times)
        diffs = np.diff(sorted_t)
        dt = np.median(diffs[diffs > 0]) if np.any(diffs > 0) else 10.0
    else:
        dt = 10.0

    # ---- Forecast values based on last measurements ----
    forecast_val1 = compute_forecast_value(temps1, FORECAST_WINDOW) if temps1 else None
    forecast_val2 = compute_forecast_value(temps2, FORECAST_WINDOW) if temps2 else None

    # device01 forecast
    if t_max1 is not None and forecast_val1 is not None:
        future_times1 = t_max1 + dt * np.arange(1, FUTURE_POINTS + 1, dtype=float)
        future_vals1 = np.full_like(future_times1, forecast_val1, dtype=float)
        forecast_curve1.setData(future_times1, future_vals1)
    else:
        forecast_curve1.clear()

    # device02 forecast
    if t_max2 is not None and forecast_val2 is not None:
        future_times2 = t_max2 + dt * np.arange(1, FUTURE_POINTS + 1, dtype=float)
        future_vals2 = np.full_like(future_times2, forecast_val2, dtype=float)
        forecast_curve2.setData(future_times2, future_vals2)
    else:
        forecast_curve2.clear()

    # ---- X-range: from past window up to end of forecast ----
    rightmost_future = []
    if t_max1 is not None:
        rightmost_future.append(t_max1 + FUTURE_POINTS * dt)
    if t_max2 is not None:
        rightmost_future.append(t_max2 + FUTURE_POINTS * dt)

    rightmost = max(rightmost_future) if rightmost_future else t_latest
    left_bound = t_latest - WINDOW_PAST_SEC

    plot.setXRange(left_bound, rightmost)


# -------- Timer -------- #
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(UPDATE_INTERVAL_MS)

# Initial draw
update()

sys.exit(app.exec())