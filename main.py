from utils import get_temperature_data_in_range
from stats import calculate_stats, calculate_trend_slope
from plotter import create_plot_widget, update_plot
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore
import sys
import numpy as np
from datetime import datetime, timedelta

class TemperatureApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Temperature Data Viewer")
        self.setGeometry(100, 100, 1200, 800)

        # Main layout
        main_layout = QtWidgets.QHBoxLayout()

        # Left panel for controls
        control_panel = QtWidgets.QVBoxLayout()

        # Device selection
        device_layout = QtWidgets.QHBoxLayout()
        device_layout.addWidget(QtWidgets.QLabel("Device:"))
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItems(['device01', 'device02', 'device03', 'device04'])
        device_layout.addWidget(self.device_combo)
        control_panel.addLayout(device_layout)

        # Start time
        start_layout = QtWidgets.QHBoxLayout()
        start_layout.addWidget(QtWidgets.QLabel("Start:"))
        self.start_edit = QtWidgets.QDateTimeEdit()
        self.start_edit.setDateTime(QtCore.QDateTime.currentDateTime().addSecs(-3600))  # 1 hour ago
        start_layout.addWidget(self.start_edit)
        control_panel.addLayout(start_layout)

        # End time removed, always to now

        # Query button
        self.query_button = QtWidgets.QPushButton("Query Data")
        self.query_button.clicked.connect(self.query_data)
        control_panel.addWidget(self.query_button)

        # Stats display
        stats_group = QtWidgets.QGroupBox("Statistics")
        stats_layout = QtWidgets.QVBoxLayout()
        self.stats_labels = {}
        for stat in ['mean', 'min', 'max', 'std', 'count']:
            label = QtWidgets.QLabel(f"{stat.capitalize()}: --")
            self.stats_labels[stat] = label
            stats_layout.addWidget(label)
        stats_group.setLayout(stats_layout)
        control_panel.addWidget(stats_group)

        # Hover info label
        self.hover_label = QtWidgets.QLabel("Hover over the graph for data point info")
        control_panel.addWidget(self.hover_label)

        # Trend analysis
        trend_layout = QtWidgets.QHBoxLayout()
        trend_layout.addWidget(QtWidgets.QLabel("Last N values:"))
        self.n_spin = QtWidgets.QSpinBox()
        self.n_spin.setRange(2, 1000)
        self.n_spin.setValue(10)
        trend_layout.addWidget(self.n_spin)
        self.trend_button = QtWidgets.QPushButton("Compute Trend")
        self.trend_button.clicked.connect(self.compute_trend)
        trend_layout.addWidget(self.trend_button)
        control_panel.addLayout(trend_layout)

        self.trend_label = QtWidgets.QLabel("Trend slope: --")
        control_panel.addWidget(self.trend_label)

        control_panel.addStretch()

        # Right panel for plot
        self.win, self.plot, self.curve, self.line_curve = create_plot_widget()
        self.win.setFixedWidth(800)

        # Connect mouse moved signal for hover info
        self.proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=60, slot=self.mouse_moved)

        # Add panels to main layout
        main_layout.addLayout(control_panel)
        main_layout.addWidget(self.win)

        self.setLayout(main_layout)

    def do_query_and_plot(self):
        device = self.device_combo.currentText()
        start_dt = self.start_edit.dateTime()
        
        # Convert local time to UTC by subtracting 1 hour
        start_dt_utc = start_dt.addSecs(-3600)
        start_str = start_dt_utc.toString("yyyy-MM-ddTHH:mm:ssZ")
        
        try:
            times, temperatures = get_temperature_data_in_range(device, start_str, "")  # end ignored
            self.current_times = times
            self.current_temps = temperatures
            update_plot(self.curve, self.line_curve, times, temperatures)
            # Center view on latest value
            if times:
                latest_x = times[-1]
                latest_y = temperatures[-1]
                x_width = 3600  # 1 hour width
                y_height = 10  # temperature range
                self.plot.setXRange(latest_x - x_width/2, latest_x + x_width/2)
                self.plot.setYRange(latest_y - y_height/2, latest_y + y_height/2)
                # Draw trend line from latest to right
                right_x = latest_x + x_width/2
                n = self.n_spin.value()
                slope = calculate_trend_slope(times, temperatures, n)
                self.current_slope = slope
                line_temps = [float(latest_y), float(latest_y) + slope * (right_x - latest_x)]
                self.line_curve.setData([latest_x, right_x], line_temps)
                self.trend_label.setText(f"Trend slope: {slope:.4f} °C/s")
            stats = calculate_stats(temperatures)
            self.update_stats(stats)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to fetch data: {str(e)}")

    def query_data(self):
        self.do_query_and_plot()
        # Start live updates
        if hasattr(self, 'live_timer'):
            self.live_timer.stop()
        self.live_timer = QtCore.QTimer()
        self.live_timer.timeout.connect(self.update_live)
        self.live_timer.start(10000)  # Update every 10 seconds

    def update_stats(self, stats):
        for stat, value in stats.items():
            if isinstance(value, float):
                self.stats_labels[stat].setText(f"{stat.capitalize()}: {value:.2f}")
            else:
                self.stats_labels[stat].setText(f"{stat.capitalize()}: {value}")

    def mouse_moved(self, evt):
        pos = evt[0]
        if self.plot.sceneBoundingRect().contains(pos):
            mouse_point = self.plot.vb.mapSceneToView(pos)
            x = mouse_point.x()
            if hasattr(self, 'current_times') and self.current_times:
                times_arr = np.array(self.current_times)
                idx = np.argmin(np.abs(times_arr - x))
                timestamp = self.current_times[idx]
                temp = self.current_temps[idx]
                count = idx + 1
                dt = datetime.fromtimestamp(timestamp) + timedelta(hours=1)
                self.hover_label.setText(f"Count: {count}, Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}, Temp: {temp:.2f}°C")
        else:
            self.hover_label.setText("Hover over the graph for data point info")

    def update_live(self):
        self.do_query_and_plot()

    def compute_trend(self):
        if hasattr(self, 'current_times') and self.current_times:
            n = self.n_spin.value()
            slope = calculate_trend_slope(self.current_times, self.current_temps, n)
            self.current_slope = slope
            self.trend_label.setText(f"Trend slope: {slope:.4f} °C/s")
            # Update the trend line
            if self.current_times:
                latest_x = self.current_times[-1]
                latest_y = self.current_temps[-1]
                x_width = 3600
                right_x = latest_x + x_width/2
                line_temps = [float(latest_y), float(latest_y) + slope * (right_x - latest_x)]
                self.line_curve.setData([latest_x, right_x], line_temps)
        else:
            self.trend_label.setText("Trend slope: No data")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = TemperatureApp()
    window.show()
    sys.exit(app.exec())