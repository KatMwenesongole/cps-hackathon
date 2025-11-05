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
FORECAST_WINDOW = 64           # how many last points to use for model
FUTURE_POINTS = 40             # forecast samples across the 10 min horizon

auto_center = True  # will be turned off once user pans/zooms


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


# ---------------- GUI setup ---------------- #
pg.setConfigOptions(antialias=True)

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="Temperature Live Graph")

axis = NowDateAxis(orientation="bottom")
plot = win.addPlot(title="Device Temperatures", axisItems={"bottom": axis})
plot.setLabel("left", "Temperature (°C)")
plot.setLabel("bottom", "Time")
plot.addLegend()

view = plot.getViewBox()


def on_range_changed(*_):
    global auto_center
    auto_center = False  # stop auto-centering once user interacts


view.sigXRangeChanged.connect(on_range_changed)


# ---------------- Curve styles ---------------- #
real_style_device1 = dict(pen=pg.mkPen("r", width=2))
real_style_device2 = dict(pen=pg.mkPen("y", width=2))
forecast_style = dict(pen=pg.mkPen("m", width=2, style=QtCore.Qt.PenStyle.DashLine))

curve1 = plot.plot(name="device01", **real_style_device1)
curve2 = plot.plot(name="device02", **real_style_device2)
forecast_curve1 = plot.plot(name="device01 forecast", **forecast_style)
forecast_curve2 = plot.plot(name="device02 forecast", **forecast_style)


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
    We generate (n_future+1) points, starting by repeating the last real point,
    and map them evenly over [0, horizon_sec] in time.
    """
    if len(times) < 3 or not temps:
        return None, None

    # Use only the last `window` samples
    temps_arr = np.array(temps[-window:], dtype=float)
    times_window = np.array(times[-window:], dtype=float)
    n = len(temps_arr)
    if n < 3:
        return None, None

    # Build design matrix for AR(2):
    # y[k] ≈ c + a1*y[k-1] + a2*y[k-2]
    Y = temps_arr[2:]  # targets
    X = np.vstack([
        np.ones(n - 2),
        temps_arr[1:-1],
        temps_arr[0:-2],
    ]).T  # shape (n-2, 3)

    # Solve least squares for [c, a1, a2]
    try:
        beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    except np.linalg.LinAlgError:
        return None, None

    c, a1, a2 = beta

    # Start recursion from last two real points
    y_tm2 = temps_arr[-2]
    y_tm1 = temps_arr[-1]

    # We'll include the last real value as the first point to keep continuity
    forecast_values = [y_tm1]

    for _ in range(n_future):
        y_next = c + a1 * y_tm1 + a2 * y_tm2
        forecast_values.append(y_next)
        y_tm2, y_tm1 = y_tm1, y_next

    forecast_values = np.array(forecast_values, dtype=float)

    # Map these (discrete) AR steps evenly over the time horizon
    t_last = times_window[-1]
    future_offsets = np.linspace(0.0, horizon_sec, n_future + 1)  # +1 for the NOW point
    future_times = t_last + future_offsets

    return future_times, forecast_values


# ---------------- Update function ---------------- #
def update():
    # Load as much past data as we want to keep in memory/plot.
    # Here: last 1 day of history; change days= to go further back.
    start_utc = datetime.now(timezone.utc) - timedelta(days=1)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    times1, temps1 = get_temperature_data_in_range("device03", start_str, "")
    times2, temps2 = get_temperature_data_in_range("device02", start_str, "")

    times1 = np.array(times1 or [], dtype=float)
    times2 = np.array(times2 or [], dtype=float)

    # No data at all
    if not len(times1) and not len(times2):
        axis.set_latest(None)
        for c in (curve1, curve2, forecast_curve1, forecast_curve2):
            c.clear()
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

    # --- Latest timestamp (NOW) ---
    t_latest = max(
        [t for t in [
            times1[-1] if len(times1) else None,
            times2[-1] if len(times2) else None,
        ] if t is not None],
        default=None,
    )

    if t_latest is None:
        axis.set_latest(None)
        forecast_curve1.clear()
        forecast_curve2.clear()
        return

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

    # --- Keep NOW centered unless the user moved the view ---
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