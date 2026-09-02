from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QComboBox, QPushButton
from PySide6.QtCore import Qt, QTimer, QDateTime, Signal, QPoint, QPointF, QRect, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygon, QLinearGradient, QRadialGradient, QPainterPath
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
import math

class TelemetryCard(QFrame):
    """
    A custom card widget to display telemetry metrics with a modern ocean layout.
    """
    def __init__(self, title, initial_value, unit, theme="ocean", parent=None):
        super().__init__(parent)
        self.setObjectName("TelemetryCard")
        self.setProperty("theme", theme)
        self.setFrameShape(QFrame.StyledPanel)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(6)
        
        # Title Label (Small, uppercase, secondary text)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        
        # Value & Unit layout
        value_layout = QHBoxLayout()
        value_layout.setContentsMargins(0, 0, 0, 0)
        value_layout.setSpacing(4)
        
        # Value Label (Large bold number)
        self.value_label = QLabel(initial_value)
        self.value_label.setObjectName("CardValue")
        self.value_label.setAlignment(Qt.AlignBottom | Qt.AlignLeft)
        
        # Unit Label (Accent colored, subscript style)
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("CardUnit")
        self.unit_label.setAlignment(Qt.AlignBottom | Qt.AlignLeft)
        # Give unit label some padding so it aligns nicely with base of value
        self.unit_label.setStyleSheet("margin-bottom: 4px;")
        
        value_layout.addWidget(self.value_label)
        value_layout.addWidget(self.unit_label)
        value_layout.addStretch()
        
        layout.addWidget(self.title_label)
        layout.addLayout(value_layout)

    def set_value(self, value_text):
        self.value_label.setText(str(value_text))

    def set_status(self, status):
        self.setProperty("status", status)
        self.style().unpolish(self)
        self.style().polish(self)


class MarineCompass(QWidget):
    """
    Custom-drawn widget displaying a Marine Compass/Rose indicating vehicle heading.
    """
    def __init__(self, parent=None, theme="ocean"):
        super().__init__(parent)
        self.theme = theme
        self.setMinimumSize(100, 100)
        self.yaw = 0.0
        self.wp_bearing = None

    def set_yaw(self, yaw):
        self.yaw = float(yaw) % 360.0
        self.update() # Triggers repaint

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        size = min(width, height) - 10
        center_x = width / 2
        center_y = height / 2
        radius = size / 2

        # Draw outer glowing ring
        if self.theme == "cockpit":
            glow_pen = QPen(QColor(60, 60, 60), 2)
        else:
            glow_pen = QPen(QColor(0, 229, 255, 60), 4)
        painter.setPen(glow_pen)
        painter.drawEllipse(center_x - radius, center_y - radius, size, size)

        # Draw compass dial base
        if self.theme == "cockpit":
            painter.setPen(QPen(QColor(40, 40, 40), 2))
            painter.setBrush(QBrush(QColor(15, 15, 15)))
        else:
            painter.setPen(QPen(QColor(28, 59, 101), 2))
            painter.setBrush(QBrush(QColor(10, 22, 37)))
        painter.drawEllipse(center_x - radius + 2, center_y - radius + 2, size - 4, size - 4)

        # Draw compass graduations and text (rotated relative to heading)
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(-self.yaw) # Counter-rotate so heading is at top

        # Draw degree tick marks
        if self.theme == "cockpit":
            tick_pen = QPen(QColor(200, 200, 200), 1)
            long_tick_pen = QPen(QColor(255, 145, 0), 1.5) # Amber/orange major ticks
        else:
            tick_pen = QPen(QColor(142, 183, 230), 1)
            long_tick_pen = QPen(QColor(0, 229, 255), 1.5)
        
        for deg in range(0, 360, 15):
            painter.save()
            painter.rotate(deg)
            if deg % 90 == 0:
                painter.setPen(long_tick_pen)
                painter.drawLine(0, -radius + 4, 0, -radius + 14)
            else:
                painter.setPen(tick_pen)
                painter.drawLine(0, -radius + 4, 0, -radius + 9)
            painter.restore()

        # Draw cardinal points
        painter.setFont(QFont("Google Sans", 9, QFont.Bold))
        
        if self.theme == "cockpit":
            painter.setPen(QPen(QColor(255, 23, 73))) # Red North
            painter.drawText(-10, -int(radius - 28), 20, 15, Qt.AlignCenter, "N")
            painter.setPen(QPen(QColor(245, 245, 245)))
            painter.drawText(-10, int(radius - 38), 20, 15, Qt.AlignCenter, "S")
            painter.drawText(int(radius - 38), -7, 20, 15, Qt.AlignCenter, "E")
            painter.drawText(-int(radius - 18), -7, 20, 15, Qt.AlignCenter, "W")
        else:
            painter.setPen(QPen(QColor(255, 23, 73))) # Red North
            painter.drawText(-10, -int(radius - 28), 20, 15, Qt.AlignCenter, "N")
            painter.setPen(QPen(QColor(142, 183, 230)))
            painter.drawText(-10, int(radius - 38), 20, 15, Qt.AlignCenter, "S")
            painter.drawText(int(radius - 38), -7, 20, 15, Qt.AlignCenter, "E")
            painter.drawText(-int(radius - 18), -7, 20, 15, Qt.AlignCenter, "W")

        # Draw Waypoint target indicator arrow on dial ring
        if self.wp_bearing is not None:
            painter.save()
            painter.rotate(self.wp_bearing)
            painter.setPen(QPen(QColor(255, 109, 0), 1.5))
            painter.setBrush(QBrush(QColor(255, 109, 0, 200)))
            wp_poly = QPolygon([
                QPoint(0, -int(radius - 6)),
                QPoint(-5, -int(radius - 16)),
                QPoint(5, -int(radius - 16))
            ])
            painter.drawPolygon(wp_poly)
            painter.restore()

        painter.restore()

        # Draw center vessel pointer indicator (always pointing up)
        painter.save()
        painter.translate(center_x, center_y)
        
        # Draw ship hull polygon outline
        if self.theme == "cockpit":
            ship_brush = QBrush(QColor(255, 214, 0, 45))
            ship_pen = QPen(QColor(255, 214, 0), 2)
            painter.setPen(ship_pen)
            painter.setBrush(ship_brush)
            
            # Sleek cockpit-style marine vessel outline (pointed bow, transom cutout)
            ship_poly = QPolygon([
                QPoint(0, -28),    # Bow
                QPoint(8, -12),    # Foredeck Starboard
                QPoint(10, 10),    # Starboard midship
                QPoint(10, 22),    # Starboard transom corner
                QPoint(6, 22),     # Transom cutout
                QPoint(4, 18),     # Recessed center
                QPoint(-4, 18),
                QPoint(-6, 22),
                QPoint(-10, 22),   # Port transom corner
                QPoint(-10, 10),   # Port midship
                QPoint(-8, -12)    # Foredeck Port
            ])
            painter.drawPolygon(ship_poly)
            
            # Draw radar arch crossbar
            painter.setPen(QPen(QColor(255, 214, 0), 1.5))
            painter.drawLine(-7, 2, 7, 2)
            
            # Draw center indicator dot
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(255, 214, 0)))
            painter.drawEllipse(-2, -2, 4, 4)
        else:
            ship_brush = QBrush(QColor(0, 229, 255, 40))
            ship_pen = QPen(QColor(0, 229, 255), 2)
            painter.setPen(ship_pen)
            painter.setBrush(ship_brush)
            
            ship_poly = QPolygon([
                QPoint(0, -30),    # Bow
                QPoint(10, -10),   # Starboard shoulder
                QPoint(10, 20),    # Starboard stern
                QPoint(-10, 20),   # Port stern
                QPoint(-10, -10)   # Port shoulder
            ])
            painter.drawPolygon(ship_poly)
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(0, 229, 255)))
            painter.drawEllipse(-3, -3, 6, 6)
            
        painter.restore()

        # Draw outer reading index pointer (pointing to current yaw value)
        if self.theme == "cockpit":
            pointer_color = QColor(255, 145, 0)
        else:
            pointer_color = QColor(0, 229, 255)
            
        painter.setPen(QPen(pointer_color, 2))
        painter.setBrush(QBrush(pointer_color))
        index_poly = QPolygon([
            QPoint(int(center_x), int(center_y - radius + 2)),
            QPoint(int(center_x - 6), int(center_y - radius - 6)),
            QPoint(int(center_x + 6), int(center_y - radius - 6))
        ])
        painter.drawPolygon(index_poly)


class MarineHorizon(QWidget):
    """
    Custom-drawn widget displaying an Artificial Horizon/Gyroscopic Indicator for Roll & Pitch.
    """
    def __init__(self, parent=None, theme="ocean"):
        super().__init__(parent)
        self.theme = theme
        self.setMinimumSize(100, 100)
        self.roll = 0.0
        self.pitch = 0.0

    def set_attitude(self, roll, pitch):
        self.roll = float(roll)
        self.pitch = float(pitch)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        size = min(width, height) - 10
        center_x = width / 2
        center_y = height / 2
        radius = size / 2

        # Set clipping path to a circle so drawing sky/sea stays inside the dial
        painter.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(center_x - radius, center_y - radius, size, size)
        painter.setClipPath(clip_path)

        # Draw Sky
        if self.theme == "cockpit":
            # Classic aviation sky blue
            sky_brush = QBrush(QColor(42, 129, 198))
            painter.fillRect(self.rect(), sky_brush)
        else:
            sky_gradient = QLinearGradient(0, center_y - radius, 0, center_y + radius)
            sky_gradient.setColorAt(0.0, QColor(10, 28, 52))
            sky_gradient.setColorAt(1.0, QColor(21, 48, 80))
            painter.fillRect(self.rect(), QBrush(sky_gradient))

        # Rotate and translate for pitch/roll sea representation
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(-self.roll)
        
        # 1 degree of pitch = 2.4 pixels shift
        pitch_offset = self.pitch * 2.4
        # Cap pitch offset to fit in radius
        pitch_offset = max(-radius, min(radius, pitch_offset))
        
        # Draw Sea/Ground
        if self.theme == "cockpit":
            # Classic aviation cockpit ground brown
            ground_brush = QBrush(QColor(139, 90, 43))
        else:
            ground_brush = QBrush(QColor(10, 74, 98))
            
        painter.setPen(Qt.NoPen)
        painter.setBrush(ground_brush)
        painter.drawRect(-int(size), int(pitch_offset), int(size * 2), int(size * 2))

        # Draw Horizon Line
        if self.theme == "cockpit":
            horizon_pen = QPen(QColor(255, 255, 255), 2)
        else:
            horizon_pen = QPen(QColor(0, 229, 255), 2)
            
        painter.setPen(horizon_pen)
        painter.drawLine(-int(radius), int(pitch_offset), int(radius), int(pitch_offset))
        
        # Draw Pitch scale lines
        if self.theme == "cockpit":
            scale_pen = QPen(QColor(255, 255, 255, 180), 1)
        else:
            scale_pen = QPen(QColor(226, 241, 255, 120), 1)
            
        painter.setPen(scale_pen)
        painter.setFont(QFont("Google Sans", 7))
        for p in [-20, -10, 10, 20]:
            p_y = pitch_offset - (p * 2.4)
            if -radius < p_y < radius:
                line_w = 20 if p % 10 == 0 else 10
                painter.drawLine(-line_w, int(p_y), line_w, int(p_y))
                if p % 10 == 0:
                    painter.drawText(line_w + 4, int(p_y - 6), f"{p}°")
                    painter.drawText(-line_w - 24, int(p_y - 6), f"{p}°")

        painter.restore() # Restore from Pitch/Roll transform

        # Draw center reference indicator (ship profile overlay, stationary)
        if self.theme == "cockpit":
            ref_pen = QPen(QColor(255, 214, 0), 3) # Cockpit yellow
            painter.setPen(ref_pen)
            
            # Left wing bar
            painter.drawLine(center_x - 26, center_y, center_x - 10, center_y)
            painter.drawLine(center_x - 10, center_y, center_x - 10, center_y + 6)
            # Right wing bar
            painter.drawLine(center_x + 10, center_y, center_x + 26, center_y)
            painter.drawLine(center_x + 10, center_y, center_x + 10, center_y + 6)
            # Center pointer dot
            painter.setBrush(QBrush(QColor(255, 214, 0)))
            painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)
        else:
            ref_pen = QPen(QColor(255, 23, 73), 3.5) # Glowing red marker
            painter.setPen(ref_pen)
            painter.drawLine(center_x - 30, center_y, center_x - 10, center_y)
            painter.drawLine(center_x + 10, center_y, center_x + 30, center_y)
            painter.drawLine(center_x, center_y, center_x, center_y + 10)
            painter.drawEllipse(center_x - 4, center_y - 4, 8, 8)

        # Restore from clipping
        painter.restore()

        # Draw dial border frame
        if self.theme == "cockpit":
            border_pen = QPen(QColor(60, 60, 60), 2)
        else:
            border_pen = QPen(QColor(28, 59, 101), 2)
            
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center_x - radius, center_y - radius, size, size)


class TopBar(QFrame):
    """
    Top Bar of the Groundstation. Contains:
    - Time & Date (Left)
    - App Title (Center)
    - Connection controls: Port, Baud rate, and Connect button (Right)
    """
    # Signals for connection action
    # Emits (port_name, baudrate)
    connect_requested = Signal(str, str)
    disconnect_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBarFrame")
        self.status_state = "disconnected"
        
        self.init_ui()
        self.start_clock()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignVCenter)

        # Left Section: Date & Time
        self.clock_label = QLabel()
        self.clock_label.setObjectName("ClockLabel")
        layout.addWidget(self.clock_label)

        # Left Section: GPS Satellites Count
        self.gps_label = QLabel("GPS: --")
        self.gps_label.setObjectName("TopBarGpsLabel")
        layout.addWidget(self.gps_label)

        # Left Section: Battery Percentage
        self.battery_label = QLabel("BATT: --")
        self.battery_label.setObjectName("TopBarBatteryLabel")
        layout.addWidget(self.battery_label)
        
        # Left Section: Chamber Temperature
        self.temp_label = QLabel("TEMP: --")
        self.temp_label.setObjectName("TopBarTempLabel")
        layout.addWidget(self.temp_label)
        
        # New Warning Badge (Pulsing Pill)
        self.alert_badge = QPushButton("⚠️ NO ALERTS")
        self.alert_badge.setObjectName("TopBarAlertBadge")
        self.alert_badge.setVisible(False)
        self.alert_badge.setCursor(Qt.PointingHandCursor)
        self.alert_badge.setStyleSheet("""
            QPushButton#TopBarAlertBadge {
                background-color: #2A1800;
                border: 1px solid #FF9F43;
                border-radius: 10px;
                color: #FF9F43;
                font-family: 'Google Sans', sans-serif;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 10px;
            }
        """)
        layout.addWidget(self.alert_badge)
        
        layout.addStretch()

        # Center Section: Title
        title_label = QLabel("MARINE GS")
        title_label.setObjectName("LogoLabel")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addStretch()

        # Right Section: Control Layout
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        controls_layout.setAlignment(Qt.AlignVCenter)
        
        # Status Light and Label
        self.status_panel = QFrame()
        self.status_panel.setObjectName("StatusPanel")
        self.status_panel.setFixedHeight(22)
        
        status_layout = QHBoxLayout(self.status_panel)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.setSpacing(6)
        status_layout.setAlignment(Qt.AlignVCenter)
        
        self.status_led = QFrame()
        self.status_led.setObjectName("StatusLED")
        self.status_led.setProperty("connected", False)
        
        self.status_text = QLabel("STANDBY")
        self.status_text.setObjectName("StatusLabel")
        self.status_text.setProperty("connected", False)
        
        status_layout.addWidget(self.status_led)
        status_layout.addWidget(self.status_text)
        controls_layout.addWidget(self.status_panel)

        # Port Select
        port_lbl = QLabel("PORT")
        port_lbl.setProperty("class", "TopBarControlLabel")
        self.port_combo = QComboBox()
        
        controls_layout.addWidget(port_lbl)
        controls_layout.addWidget(self.port_combo)

        # IP/Port Input for Ethernet Connection (TCP / UDP)
        from PySide6.QtWidgets import QLineEdit
        self.ip_port_lbl = QLabel("IP:PORT")
        self.ip_port_lbl.setProperty("class", "TopBarControlLabel")
        self.ip_port_lbl.setVisible(False)
        self.ip_port_input = QLineEdit()
        self.ip_port_input.setPlaceholderText("192.168.1.10:8888")
        self.ip_port_input.setText("127.0.0.1:8888")
        self.ip_port_input.setStyleSheet("""
            QLineEdit {
                background-color: #0F2030;
                border: 1px solid #162F4A;
                border-radius: 3px;
                color: #00E5FF;
                font-family: 'Google Sans', monospace;
                font-size: 10px;
                padding: 2px 6px;
                width: 120px;
            }
            QLineEdit:focus {
                border-color: #00E5FF;
            }
        """)
        self.ip_port_input.setVisible(False)
        controls_layout.addWidget(self.ip_port_lbl)
        controls_layout.addWidget(self.ip_port_input)

        # Baud Rate Select
        self.baud_lbl = QLabel("BAUD")
        self.baud_lbl.setProperty("class", "TopBarControlLabel")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["4800", "9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("9600")
        
        controls_layout.addWidget(self.baud_lbl)
        controls_layout.addWidget(self.baud_combo)

        # Connect button
        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.setObjectName("ConnectButton")
        self.connect_btn.setProperty("connected", False)
        self.connect_btn.clicked.connect(self.on_connect_clicked)
        controls_layout.addWidget(self.connect_btn)



        # Dynamic layout toggle slot
        def on_port_changed(text):
            is_ethernet = text in ("TCP CLIENT", "UDP CLIENT")
            self.baud_lbl.setVisible(not is_ethernet)
            self.baud_combo.setVisible(not is_ethernet)
            self.ip_port_lbl.setVisible(is_ethernet)
            self.ip_port_input.setVisible(is_ethernet)
            if is_ethernet:
                current_val = self.ip_port_input.text().strip()
                if text == "UDP CLIENT":
                    self.ip_port_lbl.setText("LOCAL PORT")
                    self.ip_port_input.setPlaceholderText("8888")
                    if not current_val or ":" in current_val:
                        self.ip_port_input.setText("8888")
                else:
                    self.ip_port_lbl.setText("IP:PORT")
                    self.ip_port_input.setPlaceholderText("192.168.1.10:8888")
                    if not current_val or not ":" in current_val:
                        self.ip_port_input.setText("127.0.0.1:8888")
            
        self.port_combo.currentTextChanged.connect(on_port_changed)

        layout.addLayout(controls_layout)



    def start_clock(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

    def update_time(self):
        # Format current time to show e.g. "04 Jul 2026 11:27:01"
        current_dt = QDateTime.currentDateTime()
        self.clock_label.setText(current_dt.toString("dd MMM yyyy  hh:mm:ss"))

    def set_gps_count(self, count):
        if count is None or count == "--":
            self.gps_label.setText("GPS: --")
        else:
            self.gps_label.setText(f"GPS: {count}")

    def set_battery_percentage(self, percentage):
        if percentage is None or percentage == "--":
            self.battery_label.setText("BATT: --")
        else:
            self.battery_label.setText(f"BATT: {percentage}%")

    def set_chamber_temp(self, temp):
        if temp is None or temp == "--":
            self.temp_label.setText("TEMP: --")
        else:
            self.temp_label.setText(f"TEMP: {temp:.1f}°C")

    def populate_ports(self, ports):
        # Compare current list to avoid redundant updates that clear user text and reset focus
        current_ports = [self.port_combo.itemText(i) for i in range(self.port_combo.count())]
        if current_ports == ports:
            return
            
        current_sel = self.port_combo.currentText()
        
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current_sel in ports:
            self.port_combo.setCurrentText(current_sel)
        self.port_combo.blockSignals(False)

    def on_connect_clicked(self):
        if self.status_state == "disconnected":
            port = self.port_combo.currentText()
            if port in ("TCP CLIENT", "UDP CLIENT"):
                baud = self.ip_port_input.text().strip()
            else:
                baud = self.baud_combo.currentText()
            self.connect_requested.emit(port, baud)
        else:
            self.disconnect_requested.emit()

    def set_connection_status(self, status, status_msg=""):
        self.status_state = status
        
        if status == "disconnected":
            self.gps_label.setText("GPS: --")
            
        # Toggle widgets state property for QSS update
        self.connect_btn.setProperty("status", status)
        self.status_led.setProperty("status", status)
        self.status_text.setProperty("status", status)
        
        if status == "connected":
            self.connect_btn.setText("DISCONNECT")
            self.status_text.setText("CONNECTED" if not status_msg else status_msg.upper())
            # Disable port selections during active connection
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.ip_port_input.setEnabled(False)
        elif status == "connecting":
            self.connect_btn.setText("CANCEL")
            self.status_text.setText("WAITING DATA" if not status_msg else status_msg.upper())
            self.port_combo.setEnabled(False)
            self.baud_combo.setEnabled(False)
            self.ip_port_input.setEnabled(False)
        else:
            self.connect_btn.setText("CONNECT")
            self.status_text.setText("STANDBY" if not status_msg else status_msg.upper())
            self.port_combo.setEnabled(True)
            self.baud_combo.setEnabled(True)
            self.ip_port_input.setEnabled(True)
            
        # Re-apply styles
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        self.status_led.style().unpolish(self.status_led)
        self.status_led.style().polish(self.status_led)
        self.status_text.style().unpolish(self.status_text)
        self.status_text.style().polish(self.status_text)


class MagnetometerVectorWidget(QWidget):
    """
    Custom cockpit widget displaying a 2D vector plot of magnetometer X and Y values.
    """
    def __init__(self, theme="ocean", parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setMinimumSize(120, 120)
        self.mx = 0.0
        self.my = 0.0
        self.mz = 0.0
        
    def set_mag_values(self, mx, my, mz):
        self.mx = float(mx)
        self.my = float(my)
        self.mz = float(mz)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        size = min(w, h) - 10
        center_x = w / 2
        center_y = h / 2
        radius = size / 2
        
        # Theme colors
        if self.theme == "cockpit":
            bg_color = QColor(24, 24, 24)
            grid_color = QColor(51, 51, 51)
            grid_dash_color = QColor(51, 51, 51, 100)
            text_color = QColor(160, 160, 160)
            vector_color = QColor(255, 145, 0) # Warning amber/orange for cockpit vector sweep
        else:
            bg_color = QColor(10, 15, 25)
            grid_color = QColor(28, 59, 101)
            grid_dash_color = QColor(28, 59, 101, 100)
            text_color = QColor(142, 183, 230)
            vector_color = QColor(0, 230, 118) # Neon green for ocean
        
        # Draw background grid
        painter.fillRect(self.rect(), QBrush(bg_color))
        painter.setPen(QPen(grid_color, 1.5))
        painter.drawEllipse(center_x - radius, center_y - radius, size, size)
        painter.drawEllipse(center_x - radius/2, center_y - radius/2, radius, radius)
        
        # Crosshair lines
        painter.setPen(QPen(grid_dash_color, 1, Qt.DashLine))
        painter.drawLine(center_x - radius, center_y, center_x + radius, center_y)
        painter.drawLine(center_x, center_y - radius, center_x, center_y + radius)
        
        # Draw vector arrow representing (mx, my)
        magnitude = math.sqrt(self.mx**2 + self.my**2)
        max_scale = 50.0  # expected scale max magnitude
        scale = radius / max_scale if magnitude > 0 else 1.0
        
        vx = center_x + self.mx * scale
        vy = center_y - self.my * scale  # Inverted Y
        
        # Draw vector line
        vector_pen = QPen(vector_color, 2.5)
        painter.setPen(vector_pen)
        painter.drawLine(center_x, center_y, vx, vy)
        
        # Arrow tip
        painter.setBrush(QBrush(vector_color))
        painter.drawEllipse(int(vx - 3), int(vy - 3), 6, 6)
        
        # Draw text labels
        painter.setPen(QPen(text_color, 1))
        painter.setFont(QFont("Google Sans", 7))
        painter.drawText(10, h - 25, f"H-Mag: {magnitude:.1f} uT")
        painter.drawText(10, h - 12, f"Z-Axis: {self.mz:.1f} uT")


class RealTimeChart(QChartView):
    """
    High-performance real-time scrolling line chart.
    """
    def __init__(self, title, min_val, max_val, unit_str, theme="ocean", parent=None):
        chart = QChart()
        super().__init__(chart, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.theme = theme
        
        self.max_points = 100
        self.series_list = []
        
        # Theme configuration
        if theme == "cockpit":
            bg_hex = "#1A1A1A"
            title_color = "#E0E0E0"
            label_color = "#A0A0A0"
            grid_color = "#333333"
            border_color = "#333333"
        else:
            bg_hex = "#0A1625"
            title_color = "#8EB7E6"
            label_color = "#8EB7E6"
            grid_color = "#1C2A3A"
            border_color = "#1C3B65"
        
        # Chart styling
        chart.setTitle(title)
        chart.setTitleFont(QFont("Google Sans", 9, QFont.Bold))
        chart.setTitleBrush(QBrush(QColor(title_color)))
        chart.setBackgroundBrush(QBrush(QColor(bg_hex)))
        chart.setMargins(QMargins(8, 8, 8, 8))
        self.setStyleSheet(f"border: 1px solid {border_color}; border-radius: 8px; background-color: {bg_hex};")
        chart.legend().setVisible(True)
        chart.legend().setFont(QFont("Google Sans", 8))
        chart.legend().setLabelColor(QColor(title_color))
        
        # Axis setup
        self.axis_x = QValueAxis()
        self.axis_x.setRange(0, self.max_points)
        self.axis_x.setVisible(False)
        
        self.axis_y = QValueAxis()
        self.axis_y.setRange(min_val, max_val)
        self.axis_y.setLabelFormat(f"%.1f {unit_str}")
        self.axis_y.setLabelsFont(QFont("Google Sans", 8))
        self.axis_y.setLabelsColor(QColor(label_color))
        self.axis_y.setGridLinePen(QPen(QColor(grid_color), 1, Qt.DashLine))
        
        chart.addAxis(self.axis_x, Qt.AlignBottom)
        chart.addAxis(self.axis_y, Qt.AlignLeft)
        
    def add_series(self, name, color_str):
        series = QLineSeries()
        series.setName(name)
        series.setPen(QPen(QColor(color_str), 2))
        self.chart().addSeries(series)
        
        series.attachAxis(self.axis_x)
        series.attachAxis(self.axis_y)
        
        self.series_list.append({
            "series": series,
            "data": []
        })
        
    def append_data(self, values):
        for i, val in enumerate(values):
            if i >= len(self.series_list):
                break
                
            item = self.series_list[i]
            history = item["data"]
            series = item["series"]
            
            history.append(val)
            if len(history) > self.max_points:
                history.pop(0)
                
            points = [QPointF(x, y) for x, y in enumerate(history)]
            series.replace(points)


class SidebarButton(QPushButton):
    """
    Custom sidebar navigation button with programmatically drawn vector icons.
    """
    def __init__(self, icon_name, tooltip_text, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarButton")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip_text)
        self.icon_name = icon_name

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # Draw background based on state
        bg_color = QColor(0, 0, 0, 0)
        if self.isChecked():
            bg_color = QColor(28, 59, 101) # checked blue
        elif self.underMouse():
            bg_color = QColor(18, 40, 70) # hover blue
            
        if bg_color.alpha() > 0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(bg_color))
            painter.drawRoundedRect(4, 4, w - 8, h - 8, 6, 6)
            
        # Determine icon color based on state
        icon_color = QColor(106, 137, 176) # standby dim light blue
        if self.isChecked():
            icon_color = QColor(255, 255, 255) # active white
        elif self.underMouse():
            icon_color = QColor(0, 229, 255) # hover cyan
            
        painter.setPen(QPen(icon_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        
        cx, cy = w / 2.0, h / 2.0
        
        # Draw vector icon by name
        if self.icon_name == "earth":
            # Draw Globe (Circle with latitude/longitude lines)
            r = 9
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            painter.drawEllipse(cx - r/2, cy - r, r, r * 2)
            painter.drawLine(cx - r, cy, cx + r, cy)
            
        elif self.icon_name == "plan":
            # Draw Path/Route (Three connected dots with lines)
            painter.drawLine(cx - 8, cy + 8, cx + 2, cy - 8)
            painter.drawLine(cx + 2, cy - 8, cx + 8, cy + 4)
            
            painter.setBrush(QBrush(icon_color))
            painter.drawEllipse(cx - 10, cy + 6, 4, 4)
            painter.drawEllipse(cx, cy - 10, 4, 4)
            painter.drawEllipse(cx + 6, cy + 2, 4, 4)
            
        elif self.icon_name == "setup":
            # Draw Joystick (Crosshairs/Base with stick handle)
            painter.drawRect(cx - 8, cy + 4, 16, 4)
            painter.drawLine(cx, cy + 4, cx, cy - 4)
            painter.setBrush(QBrush(icon_color))
            painter.drawEllipse(cx - 4, cy - 8, 8, 8)
            
        elif self.icon_name == "dashboard":
            # Draw Grid Dashboard (4 tiny squares)
            painter.drawRect(cx - 8, cy - 8, 7, 7)
            painter.drawRect(cx + 1, cy - 8, 7, 7)
            painter.drawRect(cx - 8, cy + 1, 7, 7)
            painter.drawRect(cx + 1, cy + 1, 7, 7)
            
        elif self.icon_name == "navigation":
            # Draw Compass Needle (diamond shape rotated slightly)
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(45)
            
            poly = QPolygon([
                QPoint(0, -9),
                QPoint(3, 0),
                QPoint(0, 9),
                QPoint(-3, 0)
            ])
            painter.drawPolygon(poly)
            painter.drawLine(0, -9, 0, 9)
            painter.restore()
            
        elif self.icon_name == "docking":
            # Draw Ship Anchor
            painter.drawLine(cx, cy - 8, cx, cy + 6)
            painter.drawEllipse(cx - 3, cy - 11, 6, 6) # Ring
            painter.drawLine(cx - 6, cy - 4, cx + 6, cy - 4) # Crossbar
            
            # Curved anchor hooks
            path = QPainterPath()
            path.moveTo(cx - 8, cy)
            path.quadTo(cx, cy + 12, cx + 8, cy)
            painter.drawPath(path)
            painter.drawLine(cx - 8, cy, cx - 10, cy - 3)
            painter.drawLine(cx + 8, cy, cx + 10, cy - 3)
            
        elif self.icon_name == "communication":
            # Draw Antenna/Radio waves
            painter.drawLine(cx, cy - 2, cx, cy + 10)
            painter.setBrush(QBrush(icon_color))
            painter.drawEllipse(cx - 2, cy - 4, 4, 4)
            
            # Radio waves arcs
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(cx - 6, cy - 8, 12, 12, 45 * 16, 90 * 16)
            painter.drawArc(cx - 10, cy - 12, 20, 20, 45 * 16, 90 * 16)
            
        elif self.icon_name == "depth":
            # Draw vertical depth sonar lines
            painter.drawLine(cx - 8, cy - 8, cx + 8, cy - 8)
            painter.setPen(QPen(icon_color, 2, Qt.DashLine))
            painter.drawLine(cx - 8, cy - 1, cx + 8, cy - 1)
            painter.drawLine(cx - 8, cy + 6, cx + 8, cy + 6)
            
        elif self.icon_name == "settings":
            # Draw gear cog wheel
            r_out = 8
            r_in = 3
            painter.drawEllipse(cx - r_out, cy - r_out, r_out * 2, r_out * 2)
            painter.drawEllipse(cx - r_in, cy - r_in, r_in * 2, r_in * 2)
            # Cog teeth
            for step in range(8):
                painter.save()
                painter.translate(cx, cy)
                painter.rotate(step * 45)
                painter.drawLine(0, -r_out, 0, -r_out - 3)
                painter.restore()
                
        elif self.icon_name == "about":
            # Draw Info symbol (i inside a circle)
            painter.drawEllipse(cx - 8, cy - 8, 16, 16)
            painter.drawLine(cx, cy - 1, cx, cy + 4)
            # Dot on top of i
            painter.setBrush(QBrush(icon_color))
            painter.drawEllipse(cx - 1, cy - 5, 2, 2)


class Sidebar(QFrame):
    """
    Vertical sidebar containing icon-only navigation buttons.
    """
    # Signal emitted when a page selection is changed
    page_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SidebarFrame")
        self.setFixedWidth(50)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)
        
        self.buttons = []
        
        # Top Group: Main Navigation (Earth, Plan, Setup, Dashboard)
        top_group = [
            ("earth", "Earth Map Operations", 1),
            ("plan", "Waypoint Plan", 2),
            ("setup", "Hardware Setup", 3),
            ("dashboard", "Dashboard (Waves)", 0)
        ]
        for icon_name, tooltip, idx in top_group:
            btn = SidebarButton(icon_name, tooltip, self)
            btn.setProperty("page_index", idx)
            btn.clicked.connect(self.on_button_clicked)
            layout.addWidget(btn)
            self.buttons.append(btn)
            

            
        # Spacing stretch pushes settings and about to bottom
        layout.addStretch()
        
        # Bottom Group: Settings & About
        bottom_group = [
            ("settings", "Application Settings", 4),
            ("about", "About System", 5)
        ]
        for icon_name, tooltip, idx in bottom_group:
            btn = SidebarButton(icon_name, tooltip, self)
            btn.setProperty("page_index", idx)
            btn.clicked.connect(self.on_button_clicked)
            layout.addWidget(btn)
            self.buttons.append(btn)
            
        # Default select the Earth Map button (first in buttons)
        self.buttons[0].setChecked(True)

    def on_button_clicked(self):
        sender = self.sender()
        if sender:
            idx = sender.property("page_index")
            self.select_page(idx)
            self.page_changed.emit(idx)

    def select_page(self, index):
        for btn in self.buttons:
            if btn.property("page_index") == index:
                btn.setChecked(True)
            else:
                btn.setChecked(False)


class Ping360SonarWidget(QWidget):
    """
    Custom widget displaying a 360-degree scanning imaging sonar sweep.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.image = None
        self.max_range = 10.0
        self.current_angle = 0 # in degrees (0-360)
        self.scan_intensity = 0.0
        
    def update_scan_line(self, angle, max_range, data):
        self.current_angle = angle
        self.max_range = max_range
        
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
            
        # Initialize or resize persistent QImage
        from PySide6.QtGui import QImage, QColor
        if self.image is None or self.image.size() != self.size():
            self.image = QImage(self.size(), QImage.Format_ARGB32_Premultiplied)
            self.image.fill(QColor(10, 15, 25))
            
        # Draw new ray onto persistent QImage
        from PySide6.QtGui import QPainter, QLinearGradient, QPen
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Apply phosphor decay (fades out previous sweeps over time)
        painter.fillRect(self.image.rect(), QColor(10, 15, 25, 4))
        
        center_x = w / 2.0
        center_y = h / 2.0
        radius = min(center_x, center_y) - 15
        
        # 0 degrees is straight up. Angles rotate clockwise.
        theta = math.radians(angle) - math.pi / 2
        
        end_x = center_x + radius * math.cos(theta)
        end_y = center_y + radius * math.sin(theta)
        
        # Draw ray with color-coded downsampled data values
        grad = QLinearGradient(center_x, center_y, end_x, end_y)
        
        step = max(1, len(data) // 60)
        downsampled = data[::step]
        
        # Keep track of average peak intensity
        if downsampled:
            self.scan_intensity = sum(downsampled) / len(downsampled)
        
        for idx, val in enumerate(downsampled):
            pos = idx / max(1, len(downsampled) - 1)
            # Map intensity 0-255 to copper/orange/yellow/white scale (standard sonar theme)
            val = float(val)
            r = int(min(255, val * 1.5))
            g = int(min(255, val * 0.9))
            b = int(min(255, val * 0.3))
            grad.setColorAt(pos, QColor(r, g, b))
            
        # Draw ray segment (approx 2.5 degrees wide to avoid gaps between angles)
        pen = QPen(grad, int(radius * 0.035))
        painter.setPen(pen)
        painter.drawLine(center_x, center_y, end_x, end_y)
        
        painter.end()
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        center_x = w / 2.0
        center_y = h / 2.0
        radius = min(center_x, center_y) - 15
        
        # Draw persistent scan image
        if self.image is not None:
            painter.drawImage(0, 0, self.image)
        else:
            painter.fillRect(self.rect(), QColor(15, 15, 15))
            
        # Draw polar grid rings
        grid_pen = QPen(QColor(60, 60, 60, 150), 1, Qt.SolidLine)
        painter.setPen(grid_pen)
        for r_factor in [0.25, 0.5, 0.75, 1.0]:
            r = radius * r_factor
            painter.drawEllipse(center_x - r, center_y - r, r * 2, r * 2)
            
        # Draw radial dashed lines
        grid_dash_pen = QPen(QColor(60, 60, 60, 100), 1, Qt.DashLine)
        painter.setPen(grid_dash_pen)
        for deg in range(0, 360, 45):
            rad = math.radians(deg - 90)
            rx = center_x + radius * math.cos(rad)
            ry = center_y + radius * math.sin(rad)
            painter.drawLine(center_x, center_y, rx, ry)
            
        # Draw active sweep line indicating current scan angle
        sweep_theta = math.radians(self.current_angle) - math.pi / 2
        sx = center_x + radius * math.cos(sweep_theta)
        sy = center_y + radius * math.sin(sweep_theta)
        
        sweep_pen = QPen(QColor(255, 23, 73, 200), 2, Qt.SolidLine) # Bright red sweep pointer
        painter.setPen(sweep_pen)
        painter.drawLine(center_x, center_y, sx, sy)
        
        # Draw range overlay labels (Mission Planner style)
        painter.setPen(QColor(180, 180, 180))
        painter.setFont(QFont("Google Sans", 8))
        painter.drawText(int(center_x + radius * 0.5 + 5), int(center_y - 5), f"{self.max_range * 0.5:.1f}m")
        painter.drawText(int(center_x + radius - 35), int(center_y - 5), f"{self.max_range:.1f}m")
        
        # Cardinal point labels
        painter.drawText(int(center_x - 5), int(center_y - radius - 5), "N")
        painter.drawText(int(center_x - 5), int(center_y + radius + 12), "S")
        painter.drawText(int(center_x + radius + 5), int(center_y + 4), "E")
        painter.drawText(int(center_x - radius - 15), int(center_y + 4), "W")


class Marine3DHorizon(QWidget):
    """
    Premium 3D Spherical Gyroscopic Horizon displaying curved attitude scale markings,
    roll pointer indicators, and a radial 3D glass shading dome.
    """
    def __init__(self, parent=None, theme="cockpit"):
        super().__init__(parent)
        self.theme = theme
        self.setMinimumSize(100, 100)
        self.roll = 0.0
        self.pitch = 0.0

    def set_attitude(self, roll, pitch):
        self.roll = float(roll)
        self.pitch = float(pitch)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        size = min(width, height) - 10
        center_x = width / 2
        center_y = height / 2
        radius = size / 2

        # Outer clipping sphere
        painter.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(center_x - radius, center_y - radius, size, size)
        painter.setClipPath(clip_path)

        # 1. Paint Sky background (with vertical gradient for height feel)
        sky_gradient = QLinearGradient(0, center_y - radius, 0, center_y + radius)
        if self.theme == "cockpit":
            sky_gradient.setColorAt(0.0, QColor(25, 90, 150))
            sky_gradient.setColorAt(1.0, QColor(42, 129, 198))
        else:
            sky_gradient.setColorAt(0.0, QColor(5, 15, 30))
            sky_gradient.setColorAt(1.0, QColor(15, 35, 60))
        painter.fillRect(self.rect(), QBrush(sky_gradient))

        # Rotate and translate for Pitch and Roll
        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(-self.roll)
        
        # 1 degree of pitch = 2.4 pixels shift
        pitch_offset = self.pitch * 2.4
        pitch_offset = max(-radius, min(radius, pitch_offset))

        # 2. Paint Ground/Sea block below the pitch horizon
        if self.theme == "cockpit":
            ground_brush = QBrush(QColor(120, 75, 35))
        else:
            ground_brush = QBrush(QColor(10, 60, 80))
        
        # We want to fill the ground area below the horizon line.
        # To handle rotation and curves properly, we can draw a large rect below pitch_offset.
        painter.setPen(Qt.NoPen)
        painter.setBrush(ground_brush)
        painter.drawRect(-int(size * 2), int(pitch_offset), int(size * 4), int(size * 4))

        # 3. Paint Curved Latitude / Pitch Scale Lines (Orthographic Sphere projection)
        import math
        if self.theme == "cockpit":
            line_pen = QPen(QColor(255, 255, 255, 180), 1.5)
            text_color = QColor(255, 255, 255, 220)
        else:
            line_pen = QPen(QColor(0, 229, 255, 150), 1.5)
            text_color = QColor(226, 241, 255, 220)
            
        painter.setFont(QFont("Google Sans", 7, QFont.Bold))
        
        # Draw central horizon line
        painter.setPen(line_pen)
        painter.drawLine(-int(radius), int(pitch_offset), int(radius), int(pitch_offset))
        
        # Curved pitch lines
        for p in [-30, -20, -10, 10, 20, 30]:
            p_y = pitch_offset - (p * 2.4)
            # Check if this pitch line is visible inside the sphere
            if -radius < p_y < radius:
                # Math for curvature (orthographic sphere projection projection)
                # Curve offset bends lines back towards center to look 3D
                curve_bend = p_y * 0.12
                
                # Determine width of tick line at this height
                rem_r_sq = radius**2 - p_y**2
                line_w = 24 if p % 10 == 0 else 12
                if rem_r_sq > 0:
                    max_w = math.sqrt(rem_r_sq)
                    line_w = min(line_w, max_w)
                
                # Draw curved path
                curve_path = QPainterPath()
                curve_path.moveTo(-line_w, p_y)
                curve_path.quadTo(0, p_y + curve_bend, line_w, p_y)
                painter.drawPath(curve_path)
                
                # Draw vertical tick legs at the ends of each pitch line (military HUD style)
                leg_h = 4 if p > 0 else -4
                painter.drawLine(-line_w, int(p_y), -line_w, int(p_y + leg_h))
                painter.drawLine(line_w, int(p_y), line_w, int(p_y + leg_h))
                
                # Text labels on sides of major ticks
                if p % 10 == 0 and line_w > 15:
                    painter.setPen(QPen(text_color))
                    painter.drawText(int(line_w + 4), int(p_y - 5), f"{abs(p)}")
                    painter.drawText(int(-line_w - 18), int(p_y - 5), f"{abs(p)}")
                    painter.setPen(line_pen)

        painter.restore() # Restore pitch/roll transform
        
        # 4. Paint Roll Graduation Arc and Ticks at the top boundary
        painter.save()
        painter.translate(center_x, center_y)
        
        arc_pen = QPen(QColor(255, 255, 255, 100), 1, Qt.SolidLine)
        painter.setPen(arc_pen)
        # Draw top roll scale arc
        arc_r = radius - 10
        painter.drawArc(-int(arc_r), -int(arc_r), int(arc_r * 2), int(arc_r * 2), 30 * 16, 120 * 16)
        
        # Draw roll scale tick marks
        roll_ticks = [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60]
        for tick in roll_ticks:
            painter.save()
            painter.rotate(tick)
            tick_len = 8 if tick % 30 == 0 else 5
            painter.drawLine(0, -int(arc_r), 0, -int(arc_r) + tick_len)
            painter.restore()
            
        # Draw current roll pointer triangle (counter-rotated relative to vehicle roll)
        painter.save()
        painter.rotate(-self.roll)
        pointer_pen = QPen(QColor(255, 214, 0), 1.5)
        painter.setPen(pointer_pen)
        painter.setBrush(QBrush(QColor(255, 214, 0)))
        poly = QPolygon([
            QPoint(0, -int(arc_r) + 2),
            QPoint(-5, -int(arc_r) + 10),
            QPoint(5, -int(arc_r) + 10)
        ])
        painter.drawPolygon(poly)
        painter.restore()
        
        painter.restore()

        # 5. Shading: 3D Spherical Radial Gradient overlay (creates glass dome and depth)
        radial_grad = QRadialGradient(center_x - radius*0.2, center_y - radius*0.2, radius * 1.4)
        radial_grad.setColorAt(0.0, QColor(255, 255, 255, 35)) # Top-left light reflection shine
        radial_grad.setColorAt(0.4, QColor(0, 0, 0, 0))        # Clear viewport center
        radial_grad.setColorAt(0.85, QColor(0, 0, 0, 60))      # Spherical dimming
        radial_grad.setColorAt(1.0, QColor(0, 0, 0, 180))      # Dark sphere shadow edges
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(radial_grad))
        painter.drawEllipse(center_x - radius, center_y - radius, size, size)
        
        painter.restore() # Restore clipping

        # 6. Stationary Central Vessel Reference Symbol (drawn on top of dome)
        ref_pen = QPen(QColor(255, 214, 0), 2.5) # Cockpit yellow outline
        painter.setPen(ref_pen)
        painter.setBrush(Qt.NoBrush)
        
        # Left Wing
        painter.drawLine(center_x - 28, center_y, center_x - 12, center_y)
        painter.drawLine(center_x - 12, center_y, center_x - 12, center_y + 5)
        # Right Wing
        painter.drawLine(center_x + 12, center_y, center_x + 28, center_y)
        painter.drawLine(center_x + 12, center_y, center_x + 12, center_y + 5)
        # Center reference point dot
        painter.setBrush(QBrush(QColor(255, 214, 0)))
        painter.drawEllipse(center_x - 3, center_y - 3, 6, 6)

        # 7. Draw Dial Border Ring
        border_pen = QPen(QColor(28, 59, 101), 2)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center_x - radius, center_y - radius, size, size)


class VisionTargetWidget(QWidget):
    """
    Simulated computer vision target tracking viewport with crosshair, bounding box, and target metrics.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.distance = 4.2
        self.angle = 12.5
        self.target_locked = True
        self.sweep_step = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate_sweep)
        self.timer.start(100)

    def animate_sweep(self):
        self.sweep_step = (self.sweep_step + 1) % 40
        self.update()

    def set_target(self, dist, ang, locked):
        self.distance = float(dist)
        self.angle = float(ang)
        self.target_locked = bool(locked)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(10, 15, 25))
        
        # Draw camera viewfinder border corners
        pen_glow = QPen(QColor(0, 229, 255, 100), 2)
        painter.setPen(pen_glow)
        margin = 15
        line_len = 15
        
        # Top-left corner
        painter.drawLine(margin, margin, margin + line_len, margin)
        painter.drawLine(margin, margin, margin, margin + line_len)
        # Top-right corner
        painter.drawLine(w - margin, margin, w - margin - line_len, margin)
        painter.drawLine(w - margin, margin, w - margin, margin + line_len)
        # Bottom-left corner
        painter.drawLine(margin, h - margin, margin + line_len, h - margin)
        margin_x, margin_y = margin, h - margin
        painter.drawLine(margin_x, margin_y, margin_x, margin_y - line_len)
        # Bottom-right corner
        painter.drawLine(w - margin, h - margin, w - margin - line_len, h - margin)
        painter.drawLine(w - margin, h - margin, w - margin, h - margin - line_len)
        
        # Center crosshair
        cx, cy = w / 2.0, h / 2.0
        painter.setPen(QPen(QColor(0, 229, 255, 80), 1, Qt.DashLine))
        painter.drawLine(cx - 30, cy, cx + 30, cy)
        painter.drawLine(cx, cy - 30, cx, cy + 30)
        painter.drawEllipse(int(cx - 15), int(cy - 15), 30, 30)
        
        # Draw target bounding box (locked: green, search: red)
        if self.target_locked:
            box_color = QColor(0, 230, 118) # Neon green
            box_text = "LOCK"
        else:
            box_color = QColor(255, 23, 73) # Red search
            box_text = "SEARCHING"
            
        # Add slight animation bounce to target box
        bounce = math.sin(self.sweep_step * 0.3) * 2
        bw, bh = 70 + bounce, 70 + bounce
        bx = int(cx - bw/2 + math.sin(self.sweep_step * 0.15) * 5)
        by = int(cy - bh/2 + math.cos(self.sweep_step * 0.1) * 3)
        
        painter.setPen(QPen(box_color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(bx, by, int(bw), int(bh))
        
        # Draw corner marks inside bounding box
        painter.setBrush(QBrush(box_color))
        painter.drawRect(bx, by, 6, 6)
        painter.drawRect(bx + int(bw) - 6, by, 6, 6)
        painter.drawRect(bx, by + int(bh) - 6, 6, 6)
        painter.drawRect(bx + int(bw) - 6, by + int(bh) - 6, 6, 6)
        
        # Info overlays
        painter.setPen(QColor(226, 241, 255))
        painter.setFont(QFont("Google Sans", 7, QFont.Bold))
        painter.drawText(bx + 5, by + 15, box_text)
        
        # FLIR HUD overlays (horizontal and vertical ticks along borders)
        painter.setPen(QPen(QColor(0, 229, 255, 60), 1))
        painter.setFont(QFont("Google Sans", 6))
        for tick_x in range(int(cx - 50), int(cx + 51), 10):
            painter.drawLine(tick_x, margin, tick_x, margin + 4)
        for tick_y in range(int(cy - 50), int(cy + 51), 10):
            painter.drawLine(w - margin - 4, tick_y, w - margin, tick_y)
            
        # Target details floating next to bounding box
        if self.target_locked:
            painter.setPen(QColor(0, 230, 118))
            painter.setFont(QFont("Google Sans", 7, QFont.Bold))
            painter.drawText(bx + int(bw) + 6, by + 12, f"RNG: {self.distance:.1f}m")
            painter.drawText(bx + int(bw) + 6, by + 22, f"AZ : {self.angle:+.1f}°")
            painter.drawText(bx + int(bw) + 6, by + 32, "EL : -1.8°")
        
        painter.setFont(QFont("Google Sans", 7))
        painter.setPen(QColor(142, 183, 230))
        painter.drawText(15, h - 35, f"Dist: {self.distance:.2f} m")
        painter.drawText(15, h - 22, f"Angle: {self.angle:+.1f}°")


class ROVPositionWidget(QWidget):
    """
    Subsea Acoustic relative 3D tracking map (USBL relative grid).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self.x = 2.5
        self.y = -3.8
        self.z = 1.2
        self.quality = 98.0
        self.sweep_angle = 0
        self.history = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate_sweep)
        self.timer.start(50)

    def rotate_sweep(self):
        self.sweep_angle = (self.sweep_angle + 3) % 360
        self.update()

    def set_position(self, x, y, z, quality):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.quality = float(quality)
        self.history.append((self.x, self.y))
        if len(self.history) > 20:
            self.history.pop(0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        center_x, center_y = w / 2.0, h / 2.0
        radius = min(center_x, center_y) - 15
        
        # Dark ocean grid background
        painter.fillRect(self.rect(), QColor(5, 12, 22))
        
        # Draw concentric range rings
        painter.setPen(QPen(QColor(28, 59, 101, 150), 1))
        for r_factor in [0.33, 0.66, 1.0]:
            r = radius * r_factor
            painter.drawEllipse(center_x - r, center_y - r, r * 2, r * 2)
            
        # Draw crosshair grids
        painter.drawLine(center_x - radius, center_y, center_x + radius, center_y)
        painter.drawLine(center_x, center_y - radius, center_x, center_y + radius)
        
        # Draw rotating acoustic ping sweep line
        sweep_rad = math.radians(self.sweep_angle - 90)
        sx = center_x + radius * math.cos(sweep_rad)
        sy = center_y + radius * math.sin(sweep_rad)
        painter.setPen(QPen(QColor(0, 229, 255, 60), 2))
        painter.drawLine(center_x, center_y, sx, sy)
        
        # Plot target ROV (scale mapping: 10m range = radius)
        scale = radius / 10.0
        
        # Draw target history trail
        painter.setPen(Qt.NoPen)
        for idx, (hx, hy) in enumerate(self.history):
            alpha = int(120 * ((idx + 1) / (len(self.history) + 1)))
            htx = center_x + hx * scale
            hty = center_y - hy * scale
            painter.setBrush(QBrush(QColor(0, 230, 118, alpha)))
            painter.drawEllipse(htx - 2, hty - 2, 4, 4)
            
        tx = center_x + self.x * scale
        ty = center_y - self.y * scale  # Invert Y for cartesian grid
        
        # Target blip with glow ring
        painter.setPen(QPen(QColor(0, 230, 118, 120), 2))
        painter.setBrush(QBrush(QColor(0, 230, 118, 50)))
        painter.drawEllipse(tx - 10, ty - 10, 20, 20)
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(0, 230, 118)))
        painter.drawEllipse(tx - 4, ty - 4, 8, 8)
        
        # Label next to target
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Google Sans", 7, QFont.Bold))
        painter.drawText(int(tx + 12), int(ty + 4), "ROV")
        
        # Text details
        painter.setPen(QColor(142, 183, 230))
        painter.setFont(QFont("Google Sans", 7))
        painter.drawText(10, h - 35, f"Rel: ({self.x:+.1f}, {self.y:+.1f}, {self.z:+.1f}) m")
        painter.drawText(10, h - 22, f"USBL Quality: {self.quality:.0f}%")


class AcousticFFTWidget(QWidget):
    """
    Real-time scrolling audio frequency spectrum FFT analyzer visualizer.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 120)
        self.values = [0] * 20
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.simulate_noise)
        self.timer.start(80)

    def simulate_noise(self):
        import random
        for i in range(len(self.values)):
            # Random signal fluctuations with some harmonics
            base = 15 if i in [5, 12] else 3
            self.values[i] = max(0, min(100, base + random.randint(-15, 25)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(10, 15, 25))
        
        # Draw spectrum grid lines
        painter.setPen(QPen(QColor(28, 59, 101, 100), 1))
        for y_factor in [0.25, 0.5, 0.75]:
            painter.drawLine(0, int(h * y_factor), w, int(h * y_factor))
            
        bar_count = len(self.values)
        bar_width = max(2, int(w / bar_count) - 2)
        
        # Draw gradient colored FFT bars
        grad = QLinearGradient(0, h, 0, 0)
        grad.setColorAt(0.0, QColor(0, 229, 255))   # cyan base
        grad.setColorAt(0.7, QColor(0, 230, 118))   # green mid
        grad.setColorAt(1.0, QColor(255, 23, 73))   # red peak peaks
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        
        for idx, val in enumerate(self.values):
            bar_h = int((val / 100.0) * (h - 20))
            x = idx * (bar_width + 2) + 5
            y = h - bar_h - 10
            painter.drawRect(x, y, bar_width, bar_h)
            
        # Draw bottom frequency axis line
        painter.setPen(QPen(QColor(28, 59, 101), 2))
        painter.drawLine(0, h - 10, w, h - 10)


class RadialGaugeWidget(QWidget):
    """
    Premium circular radial analog needle dial gauge widget for sensors.
    """
    def __init__(self, title, min_val, max_val, unit_str, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)
        self.title = title
        self.min_val = min_val
        self.max_val = max_val
        self.unit_str = unit_str
        self.value = min_val

    def set_value(self, val):
        self.value = max(self.min_val, min(self.max_val, float(val)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        size = min(w, h) - 10
        center_x, center_y = w / 2.0, h / 2.0
        radius = size / 2.0
        
        # Dial backing
        painter.setPen(QPen(QColor(28, 59, 101), 2))
        painter.setBrush(QBrush(QColor(10, 18, 30)))
        painter.drawEllipse(center_x - radius, center_y - radius, size, size)
        
        # Draw dial gauge scale arc (-225 degrees to +45 degrees)
        painter.save()
        painter.translate(center_x, center_y)
        
        # Scale marks
        scale_pen = QPen(QColor(142, 183, 230), 1)
        painter.setPen(scale_pen)
        for i in range(11):
            angle = -225 + i * 27
            painter.save()
            painter.rotate(angle)
            painter.drawLine(0, -int(radius - 3), 0, -int(radius - 9))
            painter.restore()
            
        # Draw needle pointing to value
        val_pct = (self.value - self.min_val) / max(1.0, self.max_val - self.min_val)
        needle_angle = -225 + val_pct * 270
        
        painter.save()
        painter.rotate(needle_angle)
        needle_pen = QPen(QColor(255, 23, 73), 2.5) # Glowing red needle pointer
        painter.setPen(needle_pen)
        painter.drawLine(0, 0, 0, -int(radius - 12))
        painter.restore()
        
        # Needle cap
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 23, 73)))
        painter.drawEllipse(-5, -5, 10, 10)
        
        painter.restore()
        
        # Labels
        painter.setPen(QColor(226, 241, 255))
        painter.setFont(QFont("Google Sans", 7, QFont.Bold))
        painter.drawText(0, int(center_y + radius - 28), w, 15, Qt.AlignCenter, f"{self.value:.1f} {self.unit_str}")
        
        painter.setPen(QColor(142, 183, 230))
        painter.setFont(QFont("Google Sans", 7))
        painter.drawText(0, int(center_y - radius + 20), w, 15, Qt.AlignCenter, self.title)


class VerticalDepthGauge(QWidget):
    """
    Vertical depth bar-gauge showing depth and altimeter height above seabed.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(80, 180)
        self.depth = 12.4
        self.altitude = 4.2

    def set_values(self, depth, altitude):
        self.depth = float(depth)
        self.altitude = float(altitude)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        bar_w = 20
        bar_x = w / 2.0 - bar_w / 2.0
        bar_y = 15
        bar_h = h - 35
        
        painter.fillRect(self.rect(), QColor(10, 15, 25))
        
        # Track backing
        painter.setPen(QPen(QColor(28, 59, 101), 2))
        painter.setBrush(QBrush(QColor(5, 10, 18)))
        painter.drawRect(bar_x, bar_y, bar_w, bar_h)
        
        # Fill depth portion (e.g. max range 50m)
        max_range = 50.0
        pct = self.depth / max_range
        fill_h = int(bar_h * min(1.0, pct))
        
        depth_grad = QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_h)
        depth_grad.setColorAt(0.0, QColor(0, 229, 255, 100))
        depth_grad.setColorAt(1.0, QColor(0, 120, 255, 200))
        
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(depth_grad))
        painter.drawRect(bar_x + 1, bar_y + 1, bar_w - 2, fill_h - 1)
        
        # Draw ticks on sides
        painter.setPen(QPen(QColor(142, 183, 230), 1))
        painter.setFont(QFont("Google Sans", 7))
        for i in range(6):
            tick_y = bar_y + (i * 0.2) * bar_h
            painter.drawLine(int(bar_x - 6), int(tick_y), int(bar_x), int(tick_y))
            painter.drawText(int(bar_x - 32), int(tick_y + 4), f"{int(i * 0.2 * max_range)}m")
            
        # Draw Altitude seabed line reference
        seabed_y = bar_y + bar_h - 2
        painter.setPen(QPen(QColor(139, 90, 43), 3.5)) # Brown seabed line
        painter.drawLine(int(bar_x - 10), int(seabed_y), int(bar_x + bar_w + 10), int(seabed_y))
        
        # Overlay readings text
        painter.setPen(QColor(226, 241, 255))
        painter.drawText(0, h - 15, w, 15, Qt.AlignCenter, f"Alt: {self.altitude:.1f}m")
        painter.drawText(0, 2, w, 15, Qt.AlignCenter, f"Depth: {self.depth:.1f}m")


class DVLVelocityVectorWidget(QWidget):
    """
    Subsea DVL 2D Velocity Vector Crosshair target grid displaying drift velocity.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(120, 120)
        self.vx = 0.0
        self.vy = 0.0

    def set_velocities(self, vx, vy):
        self.vx = float(vx)
        self.vy = float(vy)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        center_x, center_y = w / 2.0, h / 2.0
        radius = min(center_x, center_y) - 10
        
        painter.fillRect(self.rect(), QColor(10, 15, 25))
        
        # Draw target circles
        painter.setPen(QPen(QColor(28, 59, 101, 150), 1))
        for r_factor in [0.33, 0.66, 1.0]:
            r = radius * r_factor
            painter.drawEllipse(center_x - r, center_y - r, r * 2, r * 2)
            
        # Draw crosshairs
        painter.drawLine(center_x - radius, center_y, center_x + radius, center_y)
        painter.drawLine(center_x, center_y - radius, center_x, center_y + radius)
        
        # Draw velocity vector line (scale: 1.0 m/s = radius)
        scale = radius / 1.0
        target_x = center_x + self.vx * scale
        target_y = center_y - self.vy * scale  # Invert Y for cartesian grid
        
        # Draw glowing vector line
        vector_pen = QPen(QColor(255, 145, 0), 2)
        painter.setPen(vector_pen)
        painter.drawLine(center_x, center_y, target_x, target_y)
        
        # Draw target dot
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 145, 0)))
        painter.drawEllipse(target_x - 3, target_y - 3, 6, 6)
        
        # Label velocities
        painter.setPen(QColor(142, 183, 230))
        painter.setFont(QFont("Google Sans", 7))
        painter.drawText(8, h - 18, f"V_vector: ({self.vx:+.2f}, {self.vy:+.2f}) m/s")


class PFDWidget(QWidget):
    """
    Subsea Primary Flight Display (PFD) HUD widget replicating the defense-grade cockpit overlay.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 240)
        self.roll = 1.5
        self.pitch = -0.8
        self.yaw = 142.0
        self.depth = 245.0
        self.speed = 1.8
        self.course = 135.0
        self.dtw = 412.0
        
    def set_telemetry(self, roll, pitch, yaw, depth, speed, course, dtw):
        self.roll = float(roll)
        self.pitch = float(pitch)
        self.yaw = float(yaw)
        self.depth = float(depth)
        self.speed = float(speed)
        self.course = float(course)
        self.dtw = float(dtw)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # Draw background canvas
        painter.fillRect(self.rect(), QColor(5, 12, 22))
        
        # =========================================================================
        # 1. FAR-LEFT DEPTH OVERVIEW TAPE (Static 0 - 500 meters)
        # =========================================================================
        left_tape_w = 45
        painter.setPen(QPen(QColor(28, 59, 101, 180), 1))
        painter.drawLine(left_tape_w, 0, left_tape_w, h)
        
        # PFD Header
        painter.setPen(QColor(0, 229, 255))
        painter.setFont(QFont("Google Sans", 7, QFont.Bold))
        painter.drawText(5, 12, "PFD")
        
        # 500 meters label at bottom
        painter.setFont(QFont("Google Sans", 6))
        painter.setPen(QColor(142, 183, 230))
        painter.drawText(5, h - 18, 38, 15, Qt.AlignCenter, "500\nmeters")
        
        # Draw vertical tape tick lines and numbers
        tape_y_start = 25
        tape_y_end = h - 30
        tape_h = tape_y_end - tape_y_start
        
        painter.setPen(QPen(QColor(142, 183, 230, 120), 1))
        for val in range(0, 501, 100):
            # Calculate Y coordinate
            val_pct = val / 500.0
            ty = tape_y_start + val_pct * tape_h
            painter.drawLine(left_tape_w - 8, int(ty), left_tape_w, int(ty))
            painter.drawText(5, int(ty - 5), 30, 10, Qt.AlignRight | Qt.AlignVCenter, str(val))
            
        # Draw green active range slider bar
        slider_x = left_tape_w - 4
        painter.setPen(QPen(QColor(0, 230, 118), 3))
        depth_pct = min(1.0, max(0.0, self.depth / 500.0))
        pointer_y = tape_y_start + depth_pct * tape_h
        painter.drawLine(slider_x, int(tape_y_start), slider_x, int(pointer_y))
        
        # Draw yellow pointer arrow pointing to the value
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 214, 0)))
        poly_pointer = QPolygon([
            QPoint(slider_x - 3, int(pointer_y)),
            QPoint(slider_x - 9, int(pointer_y - 4)),
            QPoint(slider_x - 9, int(pointer_y + 4))
        ])
        painter.drawPolygon(poly_pointer)
        
        # =========================================================================
        # 2. MAIN PFD SKY/SEA ATTITUDE VIEWPORT (CX, CY based clipping)
        # =========================================================================
        pfd_x = left_tape_w + 1
        pfd_w = w - pfd_x
        pfd_rect = QRect(pfd_x, 0, pfd_w, h)
        
        painter.save()
        painter.setClipRect(pfd_rect)
        
        CX = pfd_x + pfd_w / 2.0
        CY = h / 2.0
        
        # DYNAMIC SCALE FACTOR (Adjusts HUD elements size dynamically)
        scale_f = min(pfd_w, h) / 250.0
        scale_f = max(0.9, min(2.8, scale_f))
        
        # Draw Sky & Sea background rotated for roll/pitch
        painter.save()
        painter.translate(CX, CY)
        painter.rotate(-self.roll)
        
        # Pitch offset: 1 degree = 2.5 * scale_f pixels
        pitch_offset = self.pitch * 2.5 * scale_f
        
        # Sky fill (gradient blue)
        sky_gradient = QLinearGradient(0, -h, 0, pitch_offset)
        sky_gradient.setColorAt(0.0, QColor(21, 101, 192))
        sky_gradient.setColorAt(1.0, QColor(66, 165, 245))
        painter.fillRect(QRect(-int(w * 1.5), -int(h * 1.5), int(w * 3), int(h * 1.5 + pitch_offset)), QBrush(sky_gradient))
        
        # Sea fill (gradient dark gray/blue)
        sea_gradient = QLinearGradient(0, pitch_offset, 0, h)
        sea_gradient.setColorAt(0.0, QColor(44, 62, 80))
        sea_gradient.setColorAt(1.0, QColor(33, 47, 61))
        painter.fillRect(QRect(-int(w * 1.5), int(pitch_offset), int(w * 3), int(h * 1.5 - pitch_offset)), QBrush(sea_gradient))
        
        # White Horizon line
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.drawLine(-int(w * 1.5), int(pitch_offset), int(w * 1.5), int(pitch_offset))
        
        # --- Pitch Ladder Lines ---
        font_sz_ticks = max(6, int(6.5 * scale_f))
        painter.setFont(QFont("Google Sans", font_sz_ticks, QFont.Bold))
        for p in [-30, -20, -10, 10, 20, 30]:
            p_y = pitch_offset - (p * 2.5 * scale_f)
            line_w = int(24 * scale_f)
            # Draw rung
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
            painter.drawLine(-line_w, int(p_y), line_w, int(p_y))
            # Draw vertical tick legs
            leg_h = int(4 * scale_f) if p > 0 else -int(4 * scale_f)
            painter.drawLine(-line_w, int(p_y), -line_w, int(p_y + leg_h))
            painter.drawLine(line_w, int(p_y), line_w, int(p_y + leg_h))
            
            # Numeric labels
            painter.setPen(QColor(255, 255, 255, 220))
            painter.drawText(line_w + 4, int(p_y - 4), f"{abs(p)}")
            painter.drawText(-line_w - 15, int(p_y - 4), f"{abs(p)}")
            
        painter.restore() # Restore roll/pitch translation
        
        # =========================================================================
        # 3. HUD OVERLAYS (Fixed on screen coordinate system)
        # =========================================================================
        
        # --- Fixed Aircraft Reference Symbol (Orange Chevron) ---
        painter.setPen(QPen(QColor(255, 179, 0), 2.5))
        chev_w = int(28 * scale_f)
        chev_gap = int(9 * scale_f)
        # Left Wing
        painter.drawLine(int(CX - chev_w), int(CY + chev_gap), int(CX - chev_gap), int(CY + chev_gap))
        painter.drawLine(int(CX - chev_gap), int(CY + chev_gap), int(CX), int(CY))
        # Right Wing
        painter.drawLine(int(CX), int(CY), int(CX + chev_gap), int(CY + chev_gap))
        painter.drawLine(int(CX + chev_gap), int(CY + chev_gap), int(CX + chev_w), int(CY + chev_gap))
        
        # --- Roll Scale Arc at the Top ---
        arc_r = int(85 * scale_f)
        arc_rect = QRect(int(CX - arc_r), int(CY - arc_r), int(arc_r * 2), int(arc_r * 2))
        painter.setPen(QPen(QColor(255, 255, 255, 100), 1, Qt.SolidLine))
        painter.drawArc(arc_rect, 35 * 16, 110 * 16)
        # Ticks on roll scale
        for tick in [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60]:
            painter.save()
            painter.translate(CX, CY)
            painter.rotate(tick)
            tick_len = int(6 * scale_f) if tick % 30 == 0 else int(4 * scale_f)
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
            painter.drawLine(0, -arc_r, 0, -arc_r + tick_len)
            painter.restore()
            
        # Draw roll pointer white triangle indicator
        painter.save()
        painter.translate(CX, CY)
        painter.rotate(-self.roll)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        poly_roll = QPolygon([
            QPoint(0, -arc_r + 2),
            QPoint(-4, -arc_r + 8),
            QPoint(4, -arc_r + 8)
        ])
        painter.drawPolygon(poly_roll)
        painter.restore()
        
        # --- Left Vertical Altitude/Depth Tape (`units`) ---
        tape_x_left = CX - int(75 * scale_f)
        tape_y_range = int(90 * scale_f)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
        # Main vertical line
        painter.drawLine(int(tape_x_left), int(CY - tape_y_range), int(tape_x_left), int(CY + tape_y_range))
        
        font_sz_labels = max(7, int(7.5 * scale_f))
        painter.setFont(QFont("Google Sans", font_sz_labels))
        
        unit_scale_pixels = 0.5 * scale_f
        range_val_span = int(tape_y_range / unit_scale_pixels)
        start_val = int((self.depth - range_val_span) // 50 * 50)
        end_val = int((self.depth + range_val_span) // 50 * 50)
        
        for val in range(start_val, end_val + 1, 50):
            if val < 0:
                continue
            y_pos = CY - (val - self.depth) * unit_scale_pixels
            if CY - tape_y_range <= y_pos <= CY + tape_y_range:
                painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
                painter.drawLine(int(tape_x_left - 6), int(y_pos), int(tape_x_left), int(y_pos))
                painter.drawText(int(tape_x_left - 35), int(y_pos - 5), 26, 10, Qt.AlignRight | Qt.AlignVCenter, str(val))
                
        # Draw green active vertical band indicator along the ruler
        painter.setPen(QPen(QColor(0, 230, 118), 3))
        painter.drawLine(int(tape_x_left + 2), int(CY - tape_y_range / 2), int(tape_x_left + 2), int(CY + tape_y_range / 2))
        
        # units labels at top/bottom of tape
        painter.setPen(QColor(180, 220, 255))
        painter.setFont(QFont("Google Sans", font_sz_ticks))
        painter.drawText(int(tape_x_left - 25), int(CY - tape_y_range - 10), "units")
        painter.drawText(int(tape_x_left - 25), int(CY + tape_y_range + 2), "units")
        
        # Current Value black box pointer at CY
        box_w = int(45 * scale_f)
        box_h = int(16 * scale_f)
        box_rect_alt = QRect(int(tape_x_left - box_w - 2), int(CY - box_h/2), box_w, box_h)
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.drawRect(box_rect_alt)
        painter.setFont(QFont("Google Sans", max(8, int(9 * scale_f)), QFont.Bold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(box_rect_alt, Qt.AlignCenter, f"{int(self.depth)}m")
        
        # --- Right Vertical Speed Tape (`knots`) ---
        tape_x_right = CX + int(75 * scale_f)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
        # Main vertical line
        painter.drawLine(int(tape_x_right), int(CY - tape_y_range), int(tape_x_right), int(CY + tape_y_range))
        
        unit_scale_speed = 80.0 * scale_f
        range_spd_span = tape_y_range / unit_scale_speed
        
        start_spd = max(0.0, round((self.speed - range_spd_span) / 0.2) * 0.2)
        end_spd = round((self.speed + range_spd_span) / 0.2) * 0.2
        for spd in [x * 0.1 for x in range(int(start_spd * 10), int(end_spd * 10) + 1, 2)]:
            y_pos = CY - (spd - self.speed) * unit_scale_speed
            if CY - tape_y_range <= y_pos <= CY + tape_y_range:
                painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
                painter.drawLine(int(tape_x_right), int(y_pos), int(tape_x_right + 6), int(y_pos))
                painter.setFont(QFont("Google Sans", font_sz_labels))
                painter.drawText(int(tape_x_right + 10), int(y_pos - 5), 25, 10, Qt.AlignLeft | Qt.AlignVCenter, f"{spd:.1f}")
                
        # Draw speed arrow pointer
        painter.setPen(QPen(QColor(0, 230, 118), 2))
        painter.setBrush(QBrush(QColor(0, 230, 118)))
        arrow_poly = QPolygon([
            QPoint(int(tape_x_right - 1), int(CY)),
            QPoint(int(tape_x_right - 6), int(CY - 4)),
            QPoint(int(tape_x_right - 6), int(CY + 4))
        ])
        painter.drawPolygon(arrow_poly)
        
        # knots labels at top/bottom of tape
        painter.setPen(QColor(180, 220, 255))
        painter.setFont(QFont("Google Sans", font_sz_ticks))
        painter.drawText(int(tape_x_right + 5), int(CY - tape_y_range - 10), "knots")
        painter.drawText(int(tape_x_right + 5), int(CY + tape_y_range + 2), "knots")
        
        # Current Speed Value box pointer
        box_w_spd = int(35 * scale_f)
        box_rect_spd = QRect(int(tape_x_right + 7), int(CY - box_h/2), box_w_spd, box_h)
        painter.setPen(QPen(QColor(255, 255, 255), 1.5))
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.drawRect(box_rect_spd)
        painter.setFont(QFont("Google Sans", max(8, int(9 * scale_f)), QFont.Bold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(box_rect_spd, Qt.AlignCenter, f"{self.speed:.1f}")
        
        # --- Bottom Center Horizontal Situation Compass Dial (HSI Rose) ---
        X_comp = CX
        Y_comp = CY + int(90 * scale_f)
        R_comp = int(45 * scale_f)
        
        # Compass Card Background dial (semi-transparent black dome)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(QBrush(QColor(10, 20, 35, 200)))
        painter.drawEllipse(int(X_comp - R_comp), int(Y_comp - R_comp), int(R_comp * 2), int(R_comp * 2))
        
        # Rotating Compass rose card
        painter.save()
        painter.translate(X_comp, Y_comp)
        painter.rotate(-self.yaw)
        
        # Draw dial ticks & degree marks
        painter.setFont(QFont("Google Sans", max(5, int(5.5 * scale_f)), QFont.Bold))
        for d in range(0, 360, 30):
            painter.save()
            painter.rotate(d)
            painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
            painter.drawLine(0, -R_comp, 0, -R_comp + 4)
            label = ""
            if d == 0: label = "N"
            elif d == 90: label = "E"
            elif d == 180: label = "S"
            elif d == 270: label = "W"
            else: label = str(d // 10)
            
            painter.drawText(-8, -int(R_comp - 6), 16, 8, Qt.AlignCenter, label)
            painter.restore()
            
        # Draw yellow pointer line for Course Bearing relative to compass
        painter.setPen(QPen(QColor(255, 214, 0), 1.5))
        painter.rotate(self.course)
        painter.drawLine(0, 0, 0, -int(R_comp - 3))
        # Draw Arrowhead
        arrow_poly_crs = QPolygon([
            QPoint(0, -int(R_comp - 3)),
            QPoint(-3, -int(R_comp - 8)),
            QPoint(3, -int(R_comp - 8))
        ])
        painter.setBrush(QBrush(QColor(255, 214, 0)))
        painter.drawPolygon(arrow_poly_crs)
        
        painter.restore() # Restore compass rotation
        
        # Draw center crosshair over compass card
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawLine(int(X_comp - 6), int(Y_comp), int(X_comp + 6), int(Y_comp))
        painter.drawLine(int(X_comp), int(Y_comp - 6), int(X_comp), int(Y_comp + 6))
        
        # Heading Pointer Box at the top of the compass rose
        hdg_box_w = int(40 * scale_f)
        hdg_box_h = int(12 * scale_f)
        hdg_box_rect = QRect(int(X_comp - hdg_box_w/2), int(Y_comp - R_comp - 9), hdg_box_w, hdg_box_h)
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.drawRect(hdg_box_rect)
        painter.setFont(QFont("Google Sans", max(7, int(8 * scale_f)), QFont.Bold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(hdg_box_rect, Qt.AlignCenter, f"{int(self.yaw)}°")
        
        # --- Top Text overlay bar (ROLL: +1.5° PITCH: -0.8° YAW: 142.0°) ---
        top_bar_rect = QRect(int(pfd_x + 10), 4, int(pfd_w - 20), 14)
        painter.setFont(QFont("Google Sans", 7, QFont.Bold))
        painter.setPen(QColor(180, 220, 255))
        telem_str = f"ROLL: {self.roll:+.1f}°   PITCH: {self.pitch:+.1f}°   YAW: {self.yaw:.1f}°"
        painter.drawText(top_bar_rect, Qt.AlignCenter, telem_str)
        
        # --- Bottom overlay text values ---
        font_sz_bottom = max(7, int(8.5 * scale_f))
        painter.setFont(QFont("Google Sans", font_sz_bottom, QFont.Bold))
        painter.setPen(QColor(255, 255, 255))
        # Left Bottom labels: Heading and Course
        painter.drawText(int(pfd_x + 15), int(h - 26), f"HDG: {int(self.yaw)}°")
        painter.setPen(QColor(255, 214, 0))
        painter.drawText(int(pfd_x + 15), int(h - 14), f"CRS: {int(self.course)}°")
        
        # Right Bottom labels: Distance to Waypoint (DTW)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(int(w - 85), int(h - 14), f"DTW: {int(self.dtw)}m")
        
        painter.restore() # Restore main clipping boundary

class BatteryGauge(QWidget):
    """
    A custom premium battery display widget showing charge percentage, state of health, and fill animations.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.soc = 100
        self.setMinimumSize(80, 160)

    def set_soc(self, soc):
        self.soc = max(0, min(100, int(soc)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        
        # Dimensions (Scaled down slightly to fit fully inside 160px height)
        bat_w = 40
        bat_h = 90
        x = cx - bat_w / 2
        y = cy - bat_h / 2 - 10
        
        # Draw battery tip (cap)
        cap_w = 16
        cap_h = 6
        painter.setPen(QPen(QColor(0, 229, 255, 100), 2))
        painter.setBrush(QBrush(QColor(0, 229, 255, 40)))
        painter.drawRect(cx - cap_w / 2, y - cap_h, cap_w, cap_h)
        
        # Draw battery body contour
        painter.setPen(QPen(QColor(0, 229, 255, 150), 2))
        painter.setBrush(QBrush(QColor(10, 22, 37)))
        painter.drawRoundedRect(x, y, bat_w, bat_h, 5, 5)
        
        # Fill percentage
        fill_h = int((bat_h - 8) * (self.soc / 100.0))
        fill_y = y + bat_h - 4 - fill_h
        
        # Determine battery color based on SOC
        if self.soc > 50:
            color = QColor(0, 230, 118) # Neon Green
        elif self.soc > 20:
            color = QColor(255, 145, 0) # Orange
        else:
            color = QColor(255, 23, 73) # Hot Red
            
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(x + 4, fill_y, bat_w - 8, fill_h, 3, 3)
        
        # Percentage text overlay (shifted up to avoid clipping)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Google Sans", 10, QFont.Bold))
        painter.drawText(0, int(y + bat_h + 16), w, 18, Qt.AlignCenter, f"{self.soc}%")


class ActuatorsGauge(QWidget):
    """
    A custom gauge showing output power levels of the 3 subsea thrusters side-by-side.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.p1 = 1500
        self.p2 = 1500
        self.p3 = 1500
        self.setMinimumSize(180, 150)

    def set_values(self, p1, p2, p3):
        self.p1 = max(1000, min(2000, int(p1)))
        self.p2 = max(1000, min(2000, int(p2)))
        self.p3 = max(1000, min(2000, int(p3)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        bar_w = 20
        spacing = 32
        margin = (w - (3 * bar_w + 2 * spacing)) / 2
        
        pwms = [self.p1, self.p2, self.p3]
        labels = ["T1", "T2", "T3"]
        
        for i in range(3):
            # Calculate column x coordinates
            col_x = margin + i * (bar_w + spacing)
            col_y = 15
            col_h = h - 55
            
            # Draw background channel with a lighter gray glow border
            painter.setPen(QPen(QColor(60, 60, 60), 1))
            painter.setBrush(QBrush(QColor(25, 25, 25)))
            painter.drawRoundedRect(col_x, col_y, bar_w, col_h, 3, 3)
            
            # Center neutral line
            mid_y = col_y + col_h / 2
            painter.setPen(QPen(QColor(100, 100, 100, 150), 1, Qt.DashLine))
            painter.drawLine(col_x - 4, mid_y, col_x + bar_w + 4, mid_y)
            
            # Draw actual thrust height from center (1500 neutral)
            val = pwms[i]
            offset = (val - 1500) / 500.0 # Range: -1.0 to +1.0
            
            if offset != 0:
                fill_h = int(abs(offset) * (col_h / 2.0))
                if offset > 0:
                    fill_y = mid_y - fill_h
                    color = QColor(0, 229, 255) # Cyan forward
                else:
                    fill_y = mid_y
                    color = QColor(255, 23, 73) # Red reverse
                
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawRect(col_x + 1, fill_y, bar_w - 2, fill_h)
                
            # Draw cursor marker indicator (slider handle style)
            marker_y = mid_y - (offset * (col_h / 2.0))
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            if offset > 0:
                painter.setBrush(QBrush(QColor(0, 229, 255)))
            elif offset < 0:
                painter.setBrush(QBrush(QColor(255, 23, 73)))
            else:
                painter.setBrush(QBrush(QColor(150, 150, 150)))
            painter.drawRoundedRect(col_x - 3, int(marker_y - 3), bar_w + 6, 6, 2, 2)
                
            # Text label
            painter.setPen(QPen(QColor(180, 180, 180)))
            painter.setFont(QFont("Google Sans", 9, QFont.Bold))
            painter.drawText(col_x - 10, int(col_y + col_h + 8), bar_w + 20, 15, Qt.AlignCenter, labels[i])
            
            # Value label
            painter.setPen(QPen(QColor(0, 229, 255)))
            painter.setFont(QFont("Google Sans", 8))
            painter.drawText(col_x - 15, int(col_y + col_h + 23), bar_w + 30, 15, Qt.AlignCenter, str(pwms[i]))





