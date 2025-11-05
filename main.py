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
FUTURE_POINTS = 15             # number of forecast points per device
FORECAST_WINDOW = 64           # how many last measurements to use for trend


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


# -------- Helper: compute forecast line using linear trend -------- #
def compute_forecast_line(times: np.ndarray,
                          temps: list[float],
                          window: int,
                          n_future: int,
                          dt: float):
    """
    Fit a linear trend to the last `window` points and extrapolate
    `n_future` points ahead by step `dt`.

    Returns (future_times, future_values) or (None, None) if not enough data.
    """
    if times.size < 2 or not temps:
        return None, None

    # Take last `window` samples
    temps_arr = np.array(temps, dtype=float)
    if temps_arr.size > window:
        temps_arr = temps_arr[-window:]
        times_window = times[-window:]
    else:
        times_window = times

    # Shift time so last point is at x = 0
    t_last = times_window[-1]
    x = times_window - t_last         # <= 0
    y = temps_arr

    # Need at least 2 distinct x values for a slope
    if np.allclose(x, x[0]):
        return None, None

    # Linear regression: y ≈ a*x + b
    a, b = np.polyfit(x, y, 1)

    # Adjust intercept so line passes exactly through last real point (x=0)
    y_last = y[-1]
    # at x=0, current line predicts b; we want y_last instead
    delta = y_last - b
    b_adj = b + delta

    # Future x values: dt, 2*dt, ..., n_future*dt
    future_x = dt * np.arange(1, n_future + 1, dtype=float)
    future_y = a * future_x + b_adj

    # Convert back to absolute timestamps (undo the shift)
    future_times = t_last + future_x

    return future_times, future_y


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

    # ---- Forecast for each device using trend ----
    # device01
    if len(times1) and temps1:
        f_times1, f_vals1 = compute_forecast_line(times1, temps1,
                                                  FORECAST_WINDOW,
                                                  FUTURE_POINTS,
                                                  dt)
        if f_times1 is not None:
            forecast_curve1.setData(f_times1, f_vals1)
        else:
            forecast_curve1.clear()
    else:
        forecast_curve1.clear()

    # device02
    if len(times2) and temps2:
        f_times2, f_vals2 = compute_forecast_line(times2, temps2,
                                                  FORECAST_WINDOW,
                                                  FUTURE_POINTS,
                                                  dt)
        if f_times2 is not None:
            forecast_curve2.setData(f_times2, f_vals2)
        else:
            forecast_curve2.clear()
    else:
        forecast_curve2.clear()

    # ---- X-range: from past window up to end of forecast ----
    rightmost_future = []
    if t_max1 is not None and forecast_curve1.getData()[0] is not None:
        rightmost_future.append(forecast_curve1.getData()[0][-1])
    if t_max2 is not None and forecast_curve2.getData()[0] is not None:
        rightmost_future.append(forecast_curve2.getData()[0][-1])

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