import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
from pyqtgraph.graphicsItems.DateAxisItem import DateAxisItem

from utils import get_temperature_data_in_range


# ---------------- Configuration ---------------- #
WINDOW_PAST_SEC = 600          # visible history to the left (10 min)
WINDOW_FUTURE_SEC = 600        # visible forecast to the right (10 min)
UPDATE_INTERVAL_MS = 1000      # refresh every 1 s
FORECAST_WINDOW = 64           # last N points used for AR(2) fit
FUTURE_POINTS = 40             # forecast samples across the 10 min horizon
HISTORY_DAYS = 1               # how much past data to load for plotting + normal range

auto_center = True  # disables itself once user pans/zooms


# ---------------- Axis with "NOW" label ---------------- #
class NowDateAxis(DateAxisItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.latest_ts = None  # epoch seconds

    def set_latest(self, ts: float | None):
        self.latest_ts = ts

    def tickStrings(self, values, scale, spacing):
        labels = super().tickStrings(values, scale, spacing)
        if self.latest_ts is None:
            return labels
        # Replace tick nearest to latest_ts with "NOW"
        for i, v in enumerate(values):
            if abs(v - self.latest_ts) <= spacing / 2:
                labels[i] = "NOW"
        return labels


# ---------------- Normal-range helper ---------------- #
def compute_normal_band(temps):
    """
    Compute a 'normal operating range' from past data.
    Here: 5th–95th percentile over all historical values.
    """
    if temps is None:
        return None, None
    arr = np.array(temps, dtype=float)
    if arr.size < 20:  # need a bit of history
        return None, None
    low = np.percentile(arr, 5)
    high = np.percentile(arr, 95)
    return float(low), float(high)


# ---------------- AR(2) forecast helper ---------------- #
def compute_forecast_line_ar2(
    times: np.ndarray,
    temps: list[float],
    window: int,
    horizon_sec: float,
    n_future: int,
):
    """
    Simple AR(2) model:

        y_t ≈ c + a1*y_{t-1} + a2*y_{t-2}

    Fit on the last `window` points, then simulate `n_future` steps ahead.
    We generate (n_future+1) points, starting at the last real value
    to keep the line continuous at NOW.
    """
    if len(times) < 3 or not temps:
        return None, None

    temps_arr = np.array(temps[-window:], dtype=float)
    times_window = np.array(times[-window:], dtype=float)
    n = len(temps_arr)
    if n < 3:
        return None, None

    # Build AR(2) design matrix: y[k] ≈ c + a1*y[k-1] + a2*y[k-2]
    Y = temps_arr[2:]  # targets
    X = np.vstack([
        np.ones(n - 2),
        temps_arr[1:-1],
        temps_arr[0:-2],
    ]).T  # shape (n-2, 3)

    try:
        beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    except np.linalg.LinAlgError:
        return None, None

    c, a1, a2 = beta

    # Start recursion from last two real points
    y_tm2 = temps_arr[-2]
    y_tm1 = temps_arr[-1]

    # Include last real value as first point for continuity
    forecast_values = [y_tm1]

    for _ in range(n_future):
        y_next = c + a1 * y_tm1 + a2 * y_tm2
        forecast_values.append(y_next)
        y_tm2, y_tm1 = y_tm1, y_next

    forecast_values = np.array(forecast_values, dtype=float)

    # Map forecast steps evenly over [0, horizon_sec]
    t_last = times_window[-1]
    future_offsets = np.linspace(0.0, horizon_sec, n_future + 1)  # +1 includes NOW
    future_times = t_last + future_offsets

    return future_times, forecast_values


# ---------------- GUI setup ---------------- #
pg.setConfigOptions(antialias=True)

app = QtWidgets.QApplication(sys.argv)

# Main window: graph on top, status label below
main = QtWidgets.QWidget()
main.setWindowTitle("Temperature Live Graph")
layout = QtWidgets.QVBoxLayout(main)

plot_widget = pg.GraphicsLayoutWidget()
layout.addWidget(plot_widget)

axis = NowDateAxis(orientation="bottom")
plot = plot_widget.addPlot(title="Device Temperatures", axisItems={"bottom": axis})
plot.setLabel("left", "Temperature (°C)")
plot.setLabel("bottom", "Time")
plot.addLegend()

status_label = QtWidgets.QLabel("Status: waiting for data...")
layout.addWidget(status_label)

main.resize(1100, 650)
main.show()

view = plot.getViewBox()


def on_range_changed(*_):
    global auto_center
    auto_center = False  # stop auto-centering once user interacts


view.sigXRangeChanged.connect(on_range_changed)


# ---------------- Curves ---------------- #
real_style_device1 = dict(pen=pg.mkPen("r", width=2))
real_style_device2 = dict(pen=pg.mkPen("y", width=2))
real_style_device3 = dict(pen=pg.mkPen("g", width=2))

forecast_style1 = dict(pen=pg.mkPen("m", width=2, style=QtCore.Qt.PenStyle.DashLine))
forecast_style2 = dict(pen=pg.mkPen("c", width=2, style=QtCore.Qt.PenStyle.DashLine))
forecast_style3 = dict(pen=pg.mkPen("w", width=2, style=QtCore.Qt.PenStyle.DashLine))

curve1 = plot.plot(name="device01", **real_style_device1)
curve2 = plot.plot(name="device02", **real_style_device2)
curve3 = plot.plot(name="device03", **real_style_device3)

forecast_curve1 = plot.plot(name="device01 forecast", **forecast_style1)
forecast_curve2 = plot.plot(name="device02 forecast", **forecast_style2)
forecast_curve3 = plot.plot(name="device03 forecast", **forecast_style3)


# ---------------- Update function ---------------- #
def update():
    now_utc = datetime.now(timezone.utc)

    # Load HISTORY_DAYS days of past data
    start_utc = now_utc - timedelta(days=HISTORY_DAYS)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Fetch data for all 3 devices
    times1, temps1 = get_temperature_data_in_range("device01", start_str, "")
    times2, temps2 = get_temperature_data_in_range("device02", start_str, "")
    times3, temps3 = get_temperature_data_in_range("device03", start_str, "")

    times1 = np.array(times1 or [], dtype=float)
    times2 = np.array(times2 or [], dtype=float)
    times3 = np.array(times3 or [], dtype=float)

    # No data at all
    if not len(times1) and not len(times2) and not len(times3):
        axis.set_latest(None)
        for c in (curve1, curve2, curve3, forecast_curve1, forecast_curve2, forecast_curve3):
            c.clear()
        status_label.setText("Status: no data available.")
        return

    # --- Real data plotting (all historical points) ---
    if len(times1):
        curve1.setData(times1, temps1)
    else:
        curve1.clear()

    if len(times2):
        curve2.setData(times2, temps2)
    else:
        curve2.clear()

    if len(times3):
        curve3.setData(times3, temps3)
    else:
        curve3.clear()

    # --- Latest timestamps & values ---
    latest_info = []  # (device_name, latest_time, latest_value)

    if len(times1):
        latest_info.append(("device01", times1[-1], temps1[-1]))
    if len(times2):
        latest_info.append(("device02", times2[-1], temps2[-1]))
    if len(times3):
        latest_info.append(("device03", times3[-1], temps3[-1]))

    if not latest_info:
        axis.set_latest(None)
        forecast_curve1.clear()
        forecast_curve2.clear()
        forecast_curve3.clear()
        status_label.setText("Status: no latest measurements.")
        return

    # Latest time across all three (NOW)
    t_latest = max(info[1] for info in latest_info)
    axis.set_latest(t_latest)

    # --- Forecast with AR(2) for each device ---
    if len(times1):
        f_t1, f_y1 = compute_forecast_line_ar2(
            times1, temps1,
            FORECAST_WINDOW,
            WINDOW_FUTURE_SEC,
            FUTURE_POINTS,
        )
        if f_t1 is not None:
            forecast_curve1.setData(f_t1, f_y1)
        else:
            forecast_curve1.clear()
    else:
        forecast_curve1.clear()

    if len(times2):
        f_t2, f_y2 = compute_forecast_line_ar2(
            times2, temps2,
            FORECAST_WINDOW,
            WINDOW_FUTURE_SEC,
            FUTURE_POINTS,
        )
        if f_t2 is not None:
            forecast_curve2.setData(f_t2, f_y2)
        else:
            forecast_curve2.clear()
    else:
        forecast_curve2.clear()

    if len(times3):
        f_t3, f_y3 = compute_forecast_line_ar2(
            times3, temps3,
            FORECAST_WINDOW,
            WINDOW_FUTURE_SEC,
            FUTURE_POINTS,
        )
        if f_t3 is not None:
            forecast_curve3.setData(f_t3, f_y3)
        else:
            forecast_curve3.clear()
    else:
        forecast_curve3.clear()

    # --- Normal range based on DEVICE2 + DEVICE3 combined ---
    combined_ref_temps = []
    if temps2:
        combined_ref_temps.extend(temps2)
    if temps3:
        combined_ref_temps.extend(temps3)

    normal_low, normal_high = compute_normal_band(combined_ref_temps)

    messages = []
    if normal_low is None or normal_high is None:
        status_label.setText(
            "Status: not enough device02+device03 history to define normal range."
        )
    else:
        for dev_name, t_last, v_last in latest_info:
            # Distance outside normal band
            if normal_low <= v_last <= normal_high:
                # Inside range
                messages.append(
                    f"✓ {dev_name}: {v_last:.2f}°C OK "
                    f"(ref: devices 02+03 {normal_low:.2f}–{normal_high:.2f}°C)"
                )
            else:
                # How far out of range?
                if v_last < normal_low:
                    diff = normal_low - v_last
                else:
                    diff = v_last - normal_high

                # Danger levels (tweak thresholds if you want)
                if diff <= 0.5:
                    symbol = "⚠"   # slight deviation
                    level = "slightly out of range"
                elif diff <= 2.0:
                    symbol = "❗"   # moderate
                    level = "out of range"
                else:
                    symbol = "🚨"   # severe
                    level = "far out of range"

                messages.append(
                    f"{symbol} {dev_name}: {v_last:.2f}°C ({level}, "
                    f"ref: 02+03 {normal_low:.2f}–{normal_high:.2f}°C, "
                    f"Δ={diff:.2f}°C)"
                )

        status_label.setText("Status: " + " | ".join(messages))

    # --- Keep NOW centered unless user moved the view ---
    if auto_center:
        plot.setXRange(t_latest - WINDOW_PAST_SEC, t_latest + WINDOW_FUTURE_SEC)


# ---------------- Timer ---------------- #
timer = QtCore.QTimer()
try:
    timer.setTimerType(QtCore.Qt.PreciseTimer)
except AttributeError:
    try:
        timer.setTimerType(QtCore.QTimerType.PreciseTimer)
    except Exception:
        pass

timer.timeout.connect(update)
timer.start(UPDATE_INTERVAL_MS)

update()
sys.exit(app.exec())

