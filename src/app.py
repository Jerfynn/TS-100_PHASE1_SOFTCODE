import os
import math
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel, QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QSlider, QPushButton, QSplitter, QComboBox, QScrollArea, QTextEdit
from PySide6.QtCore import Qt, Slot, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QPen, QBrush
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from src.widgets import TopBar, TelemetryCard, MarineCompass, MarineHorizon, Sidebar, MagnetometerVectorWidget, RealTimeChart, Marine3DHorizon, Ping360SonarWidget, VisionTargetWidget, ROVPositionWidget, AcousticFFTWidget, RadialGaugeWidget, VerticalDepthGauge, BatteryGauge, ActuatorsGauge
from src.connection import MarineTelemetryThread
from src.styles import OCEAN_STYLESHEET



class MultiWidgetProxy:
    """
    Wraps multiple UI widgets or Card/Chart shims, forwarding method calls to all instances.
    Enables multi-monitor projections to mirror updates without breaking the main window.
    """
    def __init__(self, widgets=None):
        self._widgets = widgets if widgets is not None else []
        
    def add_widget(self, w):
        if w not in self._widgets:
            self._widgets.append(w)
            
    def remove_widget(self, w):
        if w in self._widgets:
            self._widgets.remove(w)
            
    def __getattr__(self, name):
        def method_wrapper(*args, **kwargs):
            results = []
            for w in list(self._widgets):
                try:
                    # Verify C++ object validity
                    w.parent()
                except RuntimeError:
                    if w in self._widgets:
                        self._widgets.remove(w)
                    continue
                    
                try:
                    attr = getattr(w, name)
                    if callable(attr):
                        results.append(attr(*args, **kwargs))
                    else:
                        results.append(attr)
                except Exception:
                    pass
            
            if not results:
                return None
                
            # If values returned are QObjects or dict objects, wrap in a sub-proxy for chained calls
            from PySide6.QtCore import QObject
            if all(isinstance(r, QObject) or hasattr(r, '__dict__') for r in results):
                return MultiWidgetProxy(results)
            return results[0]
            
        return method_wrapper


class MultiMonitorParentProxy:
    """
    Temporary proxy parent passed to page creators during multi-monitor setup.
    Captures new widgets without immediately contaminating the main window attributes,
    preventing Layout TypeError crashes during instantiation.
    """
    def __init__(self, real_parent):
        self._real_parent = real_parent
        self._new_widgets = {}
        
    def __getattr__(self, name):
        if name in self._new_widgets:
            return self._new_widgets[name]
        return getattr(self._real_parent, name)
        
    def __setattr__(self, name, value):
        if name in ('_real_parent', '_new_widgets'):
            super().__setattr__(name, value)
        else:
            self._new_widgets[name] = value


class ConsoleWebEnginePage(QWebEnginePage):
    """
    Subclassed WebEnginePage to route JavaScript warnings/errors to Python stdout.
    """
    def __init__(self, parent=None, callback=None):
        super().__init__(parent)
        self.callback = callback
        
    def javaScriptConsoleMessage(self, level, message, line, source):
        if self.callback:
            self.callback(message)
        print(f"[JS Console] {message} (Line: {line})")


class MarineGroundStation(QMainWindow):
    """
    Main Application Window of the Marine Control Groundstation.
    """
    def __setattr__(self, name, value):
        from PySide6.QtWidgets import QWidget
        
        # We proxy QWidgets and custom shims (CardShim, ChartShim) to support multi-monitor updates
        is_proxyable = (
            isinstance(value, QWidget) or 
            type(value).__name__ in ('CardShim', 'ChartShim')
        ) and not isinstance(value, (QMainWindow, QStackedWidget))
        
        if is_proxyable:
            existing = self.__dict__.get(name)
            if existing is not None and (isinstance(existing, QWidget) or type(existing).__name__ in ('CardShim', 'ChartShim') or isinstance(existing, MultiWidgetProxy)):
                if not isinstance(existing, MultiWidgetProxy):
                    proxy = MultiWidgetProxy()
                    proxy.add_widget(existing)
                    self.__dict__[name] = proxy
                else:
                    proxy = existing
                
                proxy.add_widget(value)
                return
                
        super().__setattr__(name, value)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marine Control Groundstation - ASV")
        self.resize(1100, 650)
        self.setMinimumSize(850, 500)
        
        # Apply the global stylesheet with dynamically resolved absolute paths
        import os
        src_dir = os.path.dirname(os.path.abspath(__file__))
        down_arrow_path = os.path.join(src_dir, "down_arrow.png").replace("\\", "/")
        check_path = os.path.join(src_dir, "check.png").replace("\\", "/")
        check_dark_path = os.path.join(src_dir, "check_dark.png").replace("\\", "/")
        
        app_stylesheet = OCEAN_STYLESHEET.replace("src/down_arrow.png", down_arrow_path)
        app_stylesheet = app_stylesheet.replace("src/check.png", check_path)
        app_stylesheet = app_stylesheet.replace("src/check_dark.png", check_dark_path)
        self.setStyleSheet(app_stylesheet)
        
        self.telemetry_thread = None
        self.current_theme = "cockpit"
        self.wp_reach_threshold = 5.0
        self.thruster_min_limit = 1100
        self.thruster_max_limit = 1900
        self.planned_waypoints = []
        self.last_lat = None
        self.last_lon = None
        self.last_time = None
        self.current_speed = 0.0
        self.vessel_icon_type = "auv_top"
        self.visual_heading_offset = -90.0
        self.logging_enabled = True
        self.wp_upload_acknowledged = False
        self.sim_gps_loss = False
        self.sim_sonar_dropout = False
        self._docking_sonar_angle = 0.0
        self.sim_low_battery = False
        default_log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        if not os.path.exists(default_log_dir):
            try:
                os.makedirs(default_log_dir)
            except:
                pass
        self.log_folder_path = default_log_dir
        self.log_file_path = None
        
        # Mission state variables
        self.mission_active = False
        self.manual_running = False
        self.current_wp_idx = 0
        self.is_armed = False
        self.light_state = 0
        self.camera_state = 0
        
        # PID Controller and AHRS parameters
        self.linear_kp = 0.0
        self.linear_ki = 0.0
        self.linear_kd = 0.0
        self.angular_kp = 0.0
        self.angular_ki = 0.0
        self.angular_kd = 0.0
        self.ahrs_offset = 0.0
        self.last_yaw = 0.0
        self.is_configuration_mode = False
        self.load_pid_config()
        
        # Initialize pygame for joystick support
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
        except Exception as e:
            print(f"Error initializing pygame: {e}")
            
        self.joystick = None
        self.joystick_timer = QTimer(self)
        self.joystick_timer.setInterval(20) # 50Hz, 20ms update interval
        self.joystick_timer.timeout.connect(self.poll_joystick_input)
        
        self.joystick_refresh_timer = QTimer(self)
        self.joystick_refresh_timer.setInterval(2000) # 2 seconds
        self.joystick_refresh_timer.timeout.connect(self.refresh_joystick_devices)
        
        # Joystick auto-detect variables
        self.detecting_axis_key = None
        self.detecting_button_key = None
        self.detecting_initial_axes = {}
        self.joystick_auto_reconnect = False
        
        # Watchdog to monitor telemetry data activity
        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.setInterval(2000) # 2 seconds watchdog timeout
        self.watchdog_timer.timeout.connect(self.on_data_timeout)
        
        
        
        self.init_ui()
        self.clear_telemetry_data()
        self.joystick_refresh_timer.start()

    def init_ui(self):
        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. Top Bar
        self.top_bar = TopBar()
        self.top_bar.connect_requested.connect(self.connect_serial)
        self.top_bar.disconnect_requested.connect(self.disconnect_serial)
        self.top_bar.alert_badge.clicked.connect(self.on_alert_badge_clicked)
        main_layout.addWidget(self.top_bar)
        
        # Flashing Warning Banner Frame (placed globally below the top bar, visible on all pages!)
        self.warning_banner_frame = QFrame()
        self.warning_banner_frame.setObjectName("WarningBannerFrame")
        self.warning_banner_frame.setStyleSheet("""
            QFrame#WarningBannerFrame {
                background-color: #2D080D;
                border: 2px solid #D32F2F;
                border-radius: 6px;
                padding: 10px 15px;
            }
            QLabel#WarningBannerLabel {
                color: #FF5252;
                font-family: 'Google Sans', sans-serif;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
        """)
        wb_layout = QHBoxLayout(self.warning_banner_frame)
        wb_layout.setContentsMargins(15, 10, 15, 10)
        wb_layout.setSpacing(10)
        self.lbl_warning_banner = QLabel("⚠️ SYSTEM WARNING: NO FAULTS SIMULATED")
        self.lbl_warning_banner.setObjectName("WarningBannerLabel")
        wb_layout.addWidget(self.lbl_warning_banner)
        wb_layout.addStretch()
        main_layout.addWidget(self.warning_banner_frame)
        self.warning_banner_frame.setVisible(False) # Hidden by default
        
        # Warning flash timer
        self.warning_flash_timer = QTimer(self)
        self.warning_flash_timer.setInterval(500)
        self.warning_flash_timer.timeout.connect(self.flash_warning_banner)
        self.warning_flash_state = False
        
        # 2. Main Body Horizontal Frame (contains sidebar + stacked pages)
        body_frame = QFrame()
        body_frame.setObjectName("BodyFrame")
        body_layout = QHBoxLayout(body_frame)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        
        # 3. Sidebar Widget
        self.sidebar = Sidebar()
        body_layout.addWidget(self.sidebar)
        
        # 4. Stacked Widget containing all view pages
        self.stacked_widget = QStackedWidget()
        body_layout.addWidget(self.stacked_widget)
        
        # Connection: Click sidebar buttons to switch pages
        self.sidebar.page_changed.connect(self.stacked_widget.setCurrentIndex)
        
        # -------------------------------------------------------------
        # PAGE 0: DASHBOARD (4 Clean Sensor Panels: AHRS, GPS, Altimeter, Magnetic Sensor)
        # -------------------------------------------------------------
        page_dashboard = QWidget()
        dashboard_main_layout = QVBoxLayout(page_dashboard)
        dashboard_main_layout.setContentsMargins(15, 15, 15, 15)
        dashboard_main_layout.setSpacing(10)
        

        
        dashboard_layout = QHBoxLayout()
        dashboard_layout.setSpacing(15)
        dashboard_main_layout.addLayout(dashboard_layout)
        
        # 1. Card Instantiation (Expanded for all cockpit parameters)
        self.cards = {
            "roll": TelemetryCard("Roll", "0.00", "deg", theme="cockpit"),
            "pitch": TelemetryCard("Pitch", "0.00", "deg", theme="cockpit"),
            "yaw": TelemetryCard("Yaw / Heading", "000.00", "deg", theme="cockpit"),
            "latitude": TelemetryCard("Latitude", "00.000000", "N/S", theme="cockpit"),
            "longitude": TelemetryCard("Longitude", "00.000000", "E/W", theme="cockpit"),
            "satellites": TelemetryCard("Satellites", "0", "SATS", theme="cockpit"),
            "chamber_temp": TelemetryCard("Chamber Temp", "0.00", "°C", theme="cockpit"),
            "chamber_hum": TelemetryCard("Chamber Hum", "0.00", "%", theme="cockpit"),
            "volts": TelemetryCard("Voltage", "0.00", "V", theme="cockpit"),
            "amps": TelemetryCard("Current", "0.000", "A", theme="cockpit"),
            "watts": TelemetryCard("Power", "0.00", "W", theme="cockpit"),
            "soc": TelemetryCard("SOC", "0", "%", theme="cockpit"),
            "soh": TelemetryCard("SOH", "0", "%", theme="cockpit"),
            "p1": TelemetryCard("T1 PWM", "1500", "us", theme="cockpit"),
            "p2": TelemetryCard("T2 PWM", "1500", "us", theme="cockpit"),
            "p3": TelemetryCard("T3 PWM", "1500", "us", theme="cockpit"),
            
            # Instantiated hidden shims for backward compatibility
            "distance": TelemetryCard("Distance", "0.00", "m", theme="cockpit"),
            "confidence": TelemetryCard("Confidence", "0", "%", theme="cockpit"),
            "mx": TelemetryCard("Mag X", "0.0", "uT", theme="cockpit"),
            "my": TelemetryCard("Mag Y", "0.0", "uT", theme="cockpit"),
            "mz": TelemetryCard("Mag Z", "0.0", "uT", theme="cockpit")
        }
        
        # Three columns layout
        col_left = QVBoxLayout()
        col_left.setSpacing(15)
        
        col_center = QVBoxLayout()
        col_center.setSpacing(15)
        
        col_right = QVBoxLayout()
        col_right.setSpacing(15)
        
        # Style helper for the sensor panels (target specific panel IDs to prevent inheritance borders on child QFrames)
        panel_style = """
            QFrame#AHRSPanel, QFrame#GPSPanel, QFrame#EnvironmentPanel, QFrame#PowerPanel, QFrame#ActuatorsPanel {
                background-color: #1A1A1A;
                border: 1px solid #333333;
                border-radius: 10px;
            }
            QLabel#PanelHeader {
                color: #A0A0A0;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1.5px;
                text-transform: uppercase;
                border: none;
                background: transparent;
            }
        """
        
        # ==========================================
        # PANEL 1: AHRS (Attitude and Heading)
        # ==========================================
        ahrs_panel = QFrame()
        ahrs_panel.setObjectName("AHRSPanel")
        ahrs_panel.setStyleSheet(panel_style)
        ahrs_layout = QVBoxLayout(ahrs_panel)
        ahrs_layout.setContentsMargins(15, 12, 15, 12)
        ahrs_layout.setSpacing(10)
        
        ahrs_hdr = QLabel("AHRS - ATTITUDE & HEADING")
        ahrs_hdr.setObjectName("PanelHeader")
        ahrs_layout.addWidget(ahrs_hdr, 0, Qt.AlignLeft)
        
        # Numeric Row
        ahrs_cards = QHBoxLayout()
        ahrs_cards.setSpacing(10)
        ahrs_cards.addWidget(self.cards["roll"])
        ahrs_cards.addWidget(self.cards["pitch"])
        ahrs_cards.addWidget(self.cards["yaw"])
        ahrs_layout.addLayout(ahrs_cards)
        
        # Dials Row (Horizon, 3D Horizon, & Compass placed side-by-side horizontally)
        dials_layout = QHBoxLayout()
        dials_layout.setSpacing(10)
        dials_layout.setAlignment(Qt.AlignCenter)
        self.horizon_widget = MarineHorizon(theme="cockpit")
        self.horizon_widget.setFixedSize(140, 140)
        self.horizon_3d_widget = Marine3DHorizon(theme="cockpit")
        self.horizon_3d_widget.setFixedSize(140, 140)
        self.compass_widget = MarineCompass(theme="cockpit")
        self.compass_widget.setFixedSize(140, 140)
        dials_layout.addWidget(self.horizon_widget)
        dials_layout.addWidget(self.horizon_3d_widget)
        dials_layout.addWidget(self.compass_widget)
        ahrs_layout.addLayout(dials_layout)
        
        # Scrolling Chart
        self.attitude_chart = RealTimeChart("VEHICLE ATTITUDE DYNAMICS", -20.0, 20.0, "deg", theme="cockpit")
        self.attitude_chart.add_series("Roll", "#00E676")   # green
        self.attitude_chart.add_series("Pitch", "#FF9100")  # orange
        self.attitude_chart.setMinimumHeight(130)
        ahrs_layout.addWidget(self.attitude_chart)
        
        col_left.addWidget(ahrs_panel)
        
        # ==========================================
        # PANEL 2: GPS (Satellite Positioning)
        # ==========================================
        gps_panel = QFrame()
        gps_panel.setObjectName("GPSPanel")
        gps_panel.setStyleSheet(panel_style)
        gps_layout = QVBoxLayout(gps_panel)
        gps_layout.setContentsMargins(15, 12, 15, 12)
        gps_layout.setSpacing(10)
        
        gps_hdr = QLabel("GPS - POSITIONING SYSTEM")
        gps_hdr.setObjectName("PanelHeader")
        gps_layout.addWidget(gps_hdr, 0, Qt.AlignLeft)
        
        gps_cards = QHBoxLayout()
        gps_cards.setSpacing(10)
        gps_cards.addWidget(self.cards["latitude"])
        gps_cards.addWidget(self.cards["longitude"])
        gps_cards.addWidget(self.cards["satellites"])
        gps_layout.addLayout(gps_cards)
        
        self.gps_chart = RealTimeChart("SATELLITE RECEPTION STRENGTH", 0.0, 20.0, "sats", theme="cockpit")
        self.gps_chart.add_series("Satellites", "#2979FF")  # Blue
        self.gps_chart.setMinimumHeight(120)
        gps_layout.addWidget(self.gps_chart)
        
        col_center.addWidget(gps_panel)
        
        # ==========================================
        # PANEL 3: ENVIRONMENT (Chamber Temperature & Humidity)
        # ==========================================
        env_panel = QFrame()
        env_panel.setObjectName("EnvironmentPanel")
        env_panel.setStyleSheet(panel_style)
        env_layout = QVBoxLayout(env_panel)
        env_layout.setContentsMargins(15, 12, 15, 12)
        env_layout.setSpacing(10)
        
        env_hdr = QLabel("CHAMBER ENVIRONMENT")
        env_hdr.setObjectName("PanelHeader")
        env_layout.addWidget(env_hdr, 0, Qt.AlignLeft)
        
        env_cards = QHBoxLayout()
        env_cards.setSpacing(10)
        env_cards.addWidget(self.cards["chamber_temp"])
        env_cards.addWidget(self.cards["chamber_hum"])
        env_layout.addLayout(env_cards)
        
        self.env_chart = RealTimeChart("CHAMBER TEMPERATURE & HUMIDITY", 0.0, 100.0, "C/%", theme="cockpit")
        self.env_chart.add_series("Temp", "#FF1744")  # Red
        self.env_chart.add_series("Humidity", "#00E676")  # Green
        self.env_chart.setMinimumHeight(120)
        env_layout.addWidget(self.env_chart)
        
        col_center.addWidget(env_panel)
        
        # ==========================================
        # PANEL 4: POWER SYSTEM (BMS)
        # ==========================================
        power_panel = QFrame()
        power_panel.setObjectName("PowerPanel")
        power_panel.setStyleSheet(panel_style)
        power_layout = QVBoxLayout(power_panel)
        power_layout.setContentsMargins(15, 12, 15, 12)
        power_layout.setSpacing(10)
        
        power_hdr = QLabel("BMS - BATTERY MANAGEMENT SYSTEM")
        power_hdr.setObjectName("PanelHeader")
        power_layout.addWidget(power_hdr, 0, Qt.AlignLeft)
        
        power_cards_1 = QHBoxLayout()
        power_cards_1.setSpacing(10)
        power_cards_1.addWidget(self.cards["volts"])
        power_cards_1.addWidget(self.cards["amps"])
        power_cards_1.addWidget(self.cards["watts"])
        power_layout.addLayout(power_cards_1)
        
        power_cards_2 = QHBoxLayout()
        power_cards_2.setSpacing(10)
        power_cards_2.addWidget(self.cards["soc"])
        power_cards_2.addWidget(self.cards["soh"])
        power_layout.addLayout(power_cards_2)
        
        power_visuals = QHBoxLayout()
        power_visuals.setSpacing(10)
        
        self.battery_gauge = BatteryGauge()
        self.power_chart = RealTimeChart("POWER DIAGNOSTICS", 0.0, 30.0, "V/A", theme="cockpit")
        self.power_chart.add_series("Voltage", "#00E5FF")  # Cyan
        self.power_chart.add_series("Current", "#D500F9")  # Purple
        self.power_chart.setMinimumHeight(120)
        
        power_visuals.addWidget(self.battery_gauge)
        power_visuals.addWidget(self.power_chart)
        power_layout.addLayout(power_visuals)
        
        col_right.addWidget(power_panel)
        
        # ==========================================
        # PANEL 5: ACTUATOR OUTPUTS (PWM)
        # ==========================================
        actuators_panel = QFrame()
        actuators_panel.setObjectName("ActuatorsPanel")
        actuators_panel.setStyleSheet(panel_style)
        actuators_layout = QVBoxLayout(actuators_panel)
        actuators_layout.setContentsMargins(15, 12, 15, 12)
        actuators_layout.setSpacing(10)
        
        actuators_hdr = QLabel("ACTUATOR OUTPUTS - PWM SPEEDS")
        actuators_hdr.setObjectName("PanelHeader")
        actuators_layout.addWidget(actuators_hdr, 0, Qt.AlignLeft)
        
        actuators_cards = QHBoxLayout()
        actuators_cards.setSpacing(10)
        actuators_cards.addWidget(self.cards["p1"])
        actuators_cards.addWidget(self.cards["p2"])
        actuators_cards.addWidget(self.cards["p3"])
        actuators_layout.addLayout(actuators_cards)
        
        actuators_visuals = QHBoxLayout()
        actuators_visuals.setSpacing(10)
        
        self.actuators_gauge = ActuatorsGauge()
        self.actuators_chart = RealTimeChart("THRUSTER PWM CHANNELS", 1000.0, 2000.0, "us", theme="cockpit")
        self.actuators_chart.add_series("T1", "#FFD600") # Yellow
        self.actuators_chart.add_series("T2", "#00E676") # Green
        self.actuators_chart.add_series("T3", "#FF1744") # Red
        self.actuators_chart.setMinimumHeight(120)
        
        actuators_visuals.addWidget(self.actuators_gauge)
        actuators_visuals.addWidget(self.actuators_chart)
        actuators_layout.addLayout(actuators_visuals)
        
        col_right.addWidget(actuators_panel)
        
        # Assemble dashboard columns
        dashboard_layout.addLayout(col_left, 12)
        dashboard_layout.addLayout(col_center, 10)
        dashboard_layout.addLayout(col_right, 12)
        
        # Register Stacked Pages
        self.stacked_widget.addWidget(page_dashboard)                      # 0: Dashboard
        self.stacked_widget.addWidget(self.create_earth_page())            # 1: Earth Navigation Map
        self.stacked_widget.addWidget(self.create_plan_page())            # 2: Plan
        self.stacked_widget.addWidget(self.create_setup_page())           # 3: Setup
        self.stacked_widget.addWidget(self.create_settings_page())        # 4: Settings
        self.stacked_widget.addWidget(self.create_about_page())           # 5: About
        
        
        # Default select the first page (index 1: Earth Map)
        self.stacked_widget.setCurrentIndex(1)
        
        main_layout.addWidget(body_frame, 1) # Expand body_frame to occupy space
        
        # Populate Serial Ports on load
        self.refresh_ports()
        
        # Create a timer to periodically update port listings when not connected
        self.port_refresh_timer = QTimer(self)
        self.port_refresh_timer.timeout.connect(self.refresh_ports)
        self.port_refresh_timer.start(3000) # Every 3 seconds


    def set_thruster_limits(self):
        try:
            min_val = int(self.input_thruster_min.text().strip())
            max_val = int(self.input_thruster_max.text().strip())
            
            # Enforce hardware safety boundaries
            if min_val < 1000 or min_val > 1500 or max_val < 1500 or max_val > 2000:
                self.lbl_thruster_feedback.setStyleSheet("color: #FF1744; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
                self.lbl_thruster_feedback.setText("Limits must satisfy 1000 <= min <= 1500 <= max <= 2000")
                return
                
            self.thruster_min_limit = min_val
            self.thruster_max_limit = max_val
            
            # Save limits to configuration
            self.save_joystick_config()
            
            # Transmit speed limits to backend
            if self.telemetry_thread and self.telemetry_thread.isRunning():
                payload = f"$LIMIT,{min_val},{max_val}"
                self.telemetry_thread.write_data(payload)
                print(f"[Mission Control] Sent speed limits to backend: {payload}")
                
            self.lbl_thruster_feedback.setStyleSheet("color: #8BC34A; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            self.lbl_thruster_feedback.setText("Limits applied and saved successfully!")
            QTimer.singleShot(3000, lambda: self.lbl_thruster_feedback.setText(""))
        except ValueError:
            self.lbl_thruster_feedback.setStyleSheet("color: #FF1744; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            self.lbl_thruster_feedback.setText("Invalid integers entered.")



    def flash_warning_banner(self):
        self.warning_flash_state = not self.warning_flash_state
        has_critical = (getattr(self, 'batt_state', 'normal') == 'critical' or getattr(self, 'temp_state', 'normal') == 'critical')
        
        # Color schemes based on alert level
        if has_critical:
            # Crimson alert style
            bg_active = "#5C0B14"  # Dark Crimson
            bg_inactive = "#2D080D"
            border_color = "#FF4757" # Crimson
        else:
            # Amber warning style
            bg_active = "#4F2F00"  # Dark Amber/Orange
            bg_inactive = "#2A1800"
            border_color = "#FF9F43" # Amber
            
        if self.warning_flash_state:
            self.warning_banner_frame.setStyleSheet(f"""
                QFrame#WarningBannerFrame {{
                    background-color: {bg_active};
                    border: 2px solid {border_color};
                    border-radius: 6px;
                    padding: 10px 15px;
                }}
                QLabel#WarningBannerLabel {{
                    color: #FFFFFF;
                    font-family: 'Google Sans', sans-serif;
                    font-size: 11px;
                    font-weight: bold;
                    letter-spacing: 0.5px;
                }}
            """)
        else:
            self.warning_banner_frame.setStyleSheet(f"""
                QFrame#WarningBannerFrame {{
                    background-color: {bg_inactive};
                    border: 2px solid {border_color};
                    border-radius: 6px;
                    padding: 10px 15px;
                }}
                QLabel#WarningBannerLabel {{
                    color: #FFFFFF;
                    font-family: 'Google Sans', sans-serif;
                    font-size: 11px;
                    font-weight: bold;
                    letter-spacing: 0.5px;
                }}
            """)

    def create_earth_page(self):
        from src.pages.earth_page import create_earth_page
        return create_earth_page(self)

    def create_plan_page(self):
        from src.pages.plan_page import create_plan_page
        return create_plan_page(self)

    def create_setup_page(self):
        from src.pages.setup_page import create_setup_page
        return create_setup_page(self)

    def create_settings_page(self):
        from src.pages.settings_page import create_settings_page
        return create_settings_page(self)

    def log_mission(self, message):
        import time
        timestamp = time.strftime("[%H:%M:%S]")
        if hasattr(self, 'txt_mission_logs'):
            self.txt_mission_logs.append(f"{timestamp} {message}")
        if hasattr(self, 'txt_nav_mission_logs'):
            self.txt_nav_mission_logs.append(f"{timestamp} {message}")
            
        # Dynamically append log to the MISSION TELEMETRY LOGS table in navigation view
        if hasattr(self, 'tbl_nav_logs') and self.tbl_nav_logs:
            lvl = "INFO"
            src = "SYSTEM"
            msg = message
            
            upper_msg = message.upper()
            if "WARN" in upper_msg:
                lvl = "WARN"
            elif "ALERT" in upper_msg or "ERROR" in upper_msg or "FAIL" in upper_msg:
                lvl = "ERROR"
            
            if "GPS" in upper_msg:
                src = "GPS"
            elif "AHRS" in upper_msg:
                src = "AHRS"
            elif "VESSEL" in upper_msg or "ARM" in upper_msg or "AUTOPILOT" in upper_msg or "ROUTE" in upper_msg:
                src = "MISSION"
            elif "LINK" in upper_msg or "CONNECTION" in upper_msg or "FAILSAFE" in upper_msg:
                src = "COMM"
                
            self.tbl_nav_logs.insertRow(0)
            
            t_str = time.strftime("%H:%M:%S")
            t_item = QTableWidgetItem(t_str)
            l_item = QTableWidgetItem(lvl)
            s_item = QTableWidgetItem(src)
            m_item = QTableWidgetItem(msg)
            
            if lvl == "WARN":
                l_item.setForeground(QColor(255, 179, 0))
            elif lvl == "ERROR":
                l_item.setForeground(QColor(244, 67, 54))
            else:
                l_item.setForeground(QColor(0, 230, 118))
                
            self.tbl_nav_logs.setItem(0, 0, t_item)
            self.tbl_nav_logs.setItem(0, 1, l_item)
            self.tbl_nav_logs.setItem(0, 2, s_item)
            self.tbl_nav_logs.setItem(0, 3, m_item)
            
            if self.tbl_nav_logs.rowCount() > 100:
                self.tbl_nav_logs.setRowCount(100)
                
        print(f"[Mission Log] {message}")
        self.show_map_overlay_message(message)

    def show_map_overlay_message(self, message):
        if not hasattr(self, 'map_overlay_lbl') or self.map_overlay_lbl is None:
            self.map_overlay_lbl = QLabel(self.plan_web_view)
            self.map_overlay_lbl.setAlignment(Qt.AlignCenter)
            self.map_overlay_lbl.setStyleSheet("""
                QLabel {
                    background-color: rgba(10, 22, 37, 0.92);
                    border: 1.5px solid #00E5FF;
                    border-radius: 6px;
                    color: #FFFFFF;
                    font-family: 'Google Sans', sans-serif;
                    font-weight: bold;
                    font-size: 11px;
                    padding: 8px 18px;
                }
            """)
            from PySide6.QtWidgets import QGraphicsDropShadowEffect
            shadow = QGraphicsDropShadowEffect(self.map_overlay_lbl)
            shadow.setBlurRadius(10)
            shadow.setColor(QColor(0, 0, 0, 180))
            shadow.setOffset(0, 3)
            self.map_overlay_lbl.setGraphicsEffect(shadow)
            
            self.map_overlay_timer = QTimer(self)
            self.map_overlay_timer.setSingleShot(True)
            self.map_overlay_timer.timeout.connect(self.map_overlay_lbl.hide)
            
        self.map_overlay_lbl.setText(message)
        self.map_overlay_lbl.adjustSize()
        
        parent_w = self.plan_web_view.width()
        lbl_w = self.map_overlay_lbl.width()
        x = (parent_w - lbl_w) // 2
        y = 20
        self.map_overlay_lbl.move(x, y)
        
        self.map_overlay_lbl.show()
        self.map_overlay_lbl.raise_()
        
        self.map_overlay_timer.start(3500)

    def return_to_home(self):
        self.log_mission("Return to Home (RTH) command sent. Aborting route.")
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.write_data("$RTH")

    def handle_wp_ack(self):
        self.wp_upload_acknowledged = True
        self.btn_arm.setEnabled(True)
        self.log_mission("Vessel acknowledged waypoint route upload. Arming enabled.")

    def create_about_page(self):
        page = QWidget()
        page.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #FFFFFF;
                font-family: 'Google Sans', sans-serif;
            }
            QLabel {
                color: #FFFFFF;
            }
        """)
        
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)
        layout.setAlignment(Qt.AlignTop)
        
        # Header Label
        header_lbl = QLabel("ⓘ About ASV Control Groundstation")
        header_lbl.setStyleSheet("color: #00E5FF; font-size: 18px; font-weight: bold; font-family: 'Google Sans', sans-serif;")
        layout.addWidget(header_lbl)
        
        # Divider Line
        divider = QFrame()
        divider.setStyleSheet("background-color: #333333; min-height: 1px; max-height: 1px; border: none;")
        layout.addWidget(divider)
        
        logo = QLabel("XERA ROBOTICS")
        logo.setStyleSheet("color: #FF9100; font-size: 15px; font-weight: bold; letter-spacing: 0.5px;")
        logo.setAlignment(Qt.AlignCenter)
        
        dept = QLabel("Marine Autonomous Surface Vessels Control Groundstation")
        dept.setStyleSheet("color: #CCCCCC; font-size: 12px; font-weight: bold;")
        dept.setAlignment(Qt.AlignCenter)
        
        ver = QLabel("Product Version: 2.0 (Enterprise Release)")
        ver.setStyleSheet("color: #888888; font-size: 11px;")
        ver.setAlignment(Qt.AlignCenter)
        
        desc = QLabel(
            "This enterprise ground control application is designed to communicate with Marine Autonomous Surface Vehicles (ASVs) "
            "and subsea telemetry nodes. It manages path configurations, secure serial datalinks, acoustic modem communications, "
            "and telemetry updates. Unauthorized copying or redistribution is strictly prohibited."
        )
        desc.setStyleSheet("color: #AAAAAA; font-size: 12px; line-height: 1.6; margin-top: 10px;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        
        # Add system information table for classic enterprise look (NO FRAME OUTLINE, JUST FLAT CLEAN GRID)
        sys_info_box = QWidget()
        sys_layout = QVBoxLayout(sys_info_box)
        sys_layout.setContentsMargins(0, 20, 0, 0)
        sys_layout.setSpacing(8)
        
        sys_title = QLabel("System Configuration Information:")
        sys_title.setStyleSheet("font-weight: bold; color: #00E5FF; font-size: 11px;")
        sys_layout.addWidget(sys_title)
        
        import platform
        infos = [
            ("Operating System:", platform.system() + " " + platform.release()),
            ("Python Runtime:", platform.python_version()),
            ("GUI Framework:", "PySide6 (Qt 6.x.x)"),
            ("Active Interfaces:", "COM Serial, HMAC Telemetry Link"),
            ("Copyright:", "© Xera Robotics. All rights reserved.")
        ]
        
        for key, val in infos:
            row = QHBoxLayout()
            row.setSpacing(10)
            kl = QLabel(key)
            kl.setStyleSheet("font-weight: bold; color: #888888; font-size: 10px; min-width: 130px;")
            vl = QLabel(val)
            vl.setStyleSheet("color: #FFFFFF; font-size: 10px;")
            row.addWidget(kl)
            row.addWidget(vl)
            row.addStretch()
            sys_layout.addLayout(row)
            
        layout.addWidget(logo)
        layout.addWidget(dept)
        layout.addWidget(ver)
        layout.addWidget(desc)
        layout.addWidget(sys_info_box)
        layout.addStretch()
        return page


    def refresh_ports(self):
        if self.top_bar.status_state == "disconnected":
            active_ports = MarineTelemetryThread.get_available_ports()
            # Save the current index so we don't disrupt selection
            curr_text = self.top_bar.port_combo.currentText()
            self.top_bar.populate_ports(active_ports)
            if curr_text in active_ports:
                self.top_bar.port_combo.setCurrentText(curr_text)



    @Slot(str, str)
    def connect_serial(self, port, baud):
        # Stop previous thread if it exists
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.stop()
            
        self.telemetry_thread = MarineTelemetryThread(port, baud)
        self.telemetry_thread.light_state = self.light_state
        self.telemetry_thread.camera_state = self.camera_state
        self.telemetry_thread.data_received.connect(self.update_telemetry)
        self.telemetry_thread.connection_status.connect(self.on_connection_status_changed)
        self.telemetry_thread.wp_ack_received.connect(self.handle_wp_ack)
        self.telemetry_thread.log_received.connect(self.log_mission)
        self.telemetry_thread.raw_line_received.connect(self.log_diagnostics_raw)
        
        # Initially transition UI status to connecting (amber) waiting for valid format data
        self.top_bar.set_connection_status("connecting", "Waiting Data")
        for card in self.cards.values():
            card.set_status("connecting")
            
        self.port_refresh_timer.stop()
        self.watchdog_timer.start()
        
        self.telemetry_thread.start()

    @Slot()
    def disconnect_serial(self):
        self.watchdog_timer.stop()
        if self.telemetry_thread:
            self.telemetry_thread.stop()
            self.telemetry_thread = None
            
        self.top_bar.set_connection_status("disconnected", "Standby")
        self.log_file_path = None
        for card in self.cards.values():
            card.set_status("disconnected")
            card.setStyleSheet("")
            
        self.warning_banner_frame.setVisible(False)
        self.warning_flash_timer.stop()
        self.port_refresh_timer.start(3000)
        self.clear_telemetry_data()

    def trigger_emergency_stop(self):
        print("[Emergency Stop] Triggered! Disarming and stopping vessel.")
        self.disarm_vehicle()
        self.set_navigation_mode("manual")
        self.stop_mission()
        
        # Override warning banner to show emergency shutdown
        self.lbl_warning_banner.setText("🚨 EMERGENCY STOP ACTIVE: VEHICLE DISARMED & SHUTDOWN!")
        self.warning_banner_frame.setVisible(True)
        if not self.warning_flash_timer.isActive():
            self.warning_flash_timer.start()
            
        # Send explicit disarm and zero-thrust commands multiple times for redundancy/packet loss recovery
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            for delay in [0, 50, 100, 150, 200]:
                QTimer.singleShot(delay, lambda: self.telemetry_thread.write_data("DISARM"))

    def clear_telemetry_data(self):
        # Reset GPS data
        if hasattr(self, 'lbl_nav_lat') and self.lbl_nav_lat:
            self.lbl_nav_lat.setText("--")
            self.lbl_nav_lat.setStyleSheet("color: #FF1744; font-family: 'Google Sans', monospace; font-size: 10px; font-weight: bold;")
        if hasattr(self, 'lbl_nav_lon') and self.lbl_nav_lon:
            self.lbl_nav_lon.setText("--")
            self.lbl_nav_lon.setStyleSheet("color: #FF1744; font-family: 'Google Sans', monospace; font-size: 10px; font-weight: bold;")
        if hasattr(self, 'lbl_nav_sats') and self.lbl_nav_sats:
            self.lbl_nav_sats.setText("0")
            self.lbl_nav_sats.setStyleSheet("color: #FF1744; font-family: 'Google Sans', monospace; font-size: 10px; font-weight: bold;")
            
        if hasattr(self, 'lbl_nav_status') and self.lbl_nav_status:
            self.lbl_nav_status.setText("DISCONNECTED")
            self.lbl_nav_status.setStyleSheet("color: #FF1744; font-weight: bold; font-size: 10px;")
        if hasattr(self, 'lbl_nav_quality') and self.lbl_nav_quality:
            self.lbl_nav_quality.setText("0%")
            self.lbl_nav_quality.setStyleSheet("color: #FF1744; font-family: 'Google Sans', monospace; font-size: 10px; font-weight: bold;")
        if hasattr(self, 'lbl_nav_time') and self.lbl_nav_time:
            self.lbl_nav_time.setText("--")
            self.lbl_nav_time.setStyleSheet("color: #FF1744; font-family: 'Google Sans', monospace; font-size: 10px; font-weight: bold;")

        # Reset Top Bar indicators
        self.top_bar.set_gps_count("--")
        self.top_bar.set_battery_percentage("--")
        self.top_bar.set_chamber_temp("--")

        # Reset BMS readouts
        if hasattr(self, 'lbl_nav_voltage') and self.lbl_nav_voltage:
            self.lbl_nav_voltage.setText("0.00 V")
        if hasattr(self, 'lbl_nav_current') and self.lbl_nav_current:
            self.lbl_nav_current.setText("0.00 A")
        if hasattr(self, 'lbl_nav_soc') and self.lbl_nav_soc:
            self.lbl_nav_soc.setText("0 %")
        if hasattr(self, 'lbl_nav_rem_ah') and self.lbl_nav_rem_ah:
            self.lbl_nav_rem_ah.setText("0.00 Ah")
        if hasattr(self, 'lbl_nav_soh') and self.lbl_nav_soh:
            self.lbl_nav_soh.setText("0 %")
        if hasattr(self, 'lbl_nav_batt_temp') and self.lbl_nav_batt_temp:
            self.lbl_nav_batt_temp.setText("0.0 °C")

        # Reset Cards
        for key in self.cards.keys():
            if key in ["latitude", "longitude"]:
                self.cards[key].set_value("--")
            elif key in ["satellites", "confidence", "soc", "soh"]:
                self.cards[key].set_value("0")
            elif key in ["p1", "p2", "p3"]:
                self.cards[key].set_value("1500")
            else:
                self.cards[key].set_value("0.0")

        # Reset instrument widgets
        self.compass_widget.set_yaw(0.0)
        self.horizon_widget.set_attitude(0.0, 0.0)
        self.horizon_3d_widget.set_attitude(0.0, 0.0)
        if hasattr(self, 'mag_vector_widget') and self.mag_vector_widget:
            self.mag_vector_widget.set_mag_values(0.0, 0.0, 0.0)
        if hasattr(self, 'battery_gauge') and self.battery_gauge:
            self.battery_gauge.set_soc(100)
        if hasattr(self, 'actuators_gauge') and self.actuators_gauge:
            self.actuators_gauge.set_values(1500, 1500, 1500)

        # Reset dynamic scrolling plots
        self.attitude_chart.append_data([0.0, 0.0])
        if hasattr(self, 'sonar_chart') and self.sonar_chart:
            self.sonar_chart.append_data([0.0])
        if hasattr(self, 'gps_chart') and self.gps_chart:
            self.gps_chart.append_data([0.0])
        if hasattr(self, 'env_chart') and self.env_chart:
            self.env_chart.append_data([0.0, 0.0])
        if hasattr(self, 'power_chart') and self.power_chart:
            self.power_chart.append_data([0.0, 0.0])
        if hasattr(self, 'actuators_chart') and self.actuators_chart:
            self.actuators_chart.append_data([1500, 1500, 1500])
        if hasattr(self, 'mag_chart') and self.mag_chart:
            self.mag_chart.append_data([0.0, 0.0, 0.0])

        # Reset Docking Widgets
        if hasattr(self, 'docking_sonar'):
            self.docking_sonar.update_scan_line(0.0, 0.0, [0]*60)
        if hasattr(self, 'docking_mag'):
            self.docking_mag.set_mag_values(0.0, 0.0, 0.0)
        if hasattr(self, 'docking_vision'):
            self.docking_vision.set_target(0.0, 0.0, False)
        if hasattr(self, 'docking_alignment') and self.docking_alignment:
            self.docking_alignment.set_alignment(0.0, 0.0, 0.0, 0)
        if hasattr(self, 'docking_mag_history') and self.docking_mag_history:
            self.docking_mag_history.add_data(0.0, 0.0, 0.0)
        if hasattr(self, 'docking_mag_vector') and self.docking_mag_vector:
            self.docking_mag_vector.set_vector(0.0, 0.0, 0.0)

        # Reset Docking readouts
        if hasattr(self, 'lbl_docking_sonar_range') and self.lbl_docking_sonar_range:
            self.lbl_docking_sonar_range.setText("0.0 m")
        if hasattr(self, 'lbl_docking_sonar_bearing') and self.lbl_docking_sonar_bearing:
            self.lbl_docking_sonar_bearing.setText("0.0°")
        if hasattr(self, 'lbl_docking_val_mx') and self.lbl_docking_val_mx:
            self.lbl_docking_val_mx.setText("+0.00")
        if hasattr(self, 'lbl_docking_val_my') and self.lbl_docking_val_my:
            self.lbl_docking_val_my.setText("+0.00")
        if hasattr(self, 'lbl_docking_val_mz') and self.lbl_docking_val_mz:
            self.lbl_docking_val_mz.setText("+0.00")
        if hasattr(self, 'lbl_docking_val_mb') and self.lbl_docking_val_mb:
            self.lbl_docking_val_mb.setText("0.00")
            
        if hasattr(self, 'lbl_raw_sonar_range') and self.lbl_raw_sonar_range:
            self.lbl_raw_sonar_range.setText("0.0 m")
        if hasattr(self, 'lbl_raw_sonar_bearing') and self.lbl_raw_sonar_bearing:
            self.lbl_raw_sonar_bearing.setText("0.0°")
        if hasattr(self, 'lbl_raw_mag_mx') and self.lbl_raw_mag_mx:
            self.lbl_raw_mag_mx.setText("+0.00")
        if hasattr(self, 'lbl_raw_mag_my') and self.lbl_raw_mag_my:
            self.lbl_raw_mag_my.setText("-0.00")
        if hasattr(self, 'lbl_raw_mag_mz') and self.lbl_raw_mag_mz:
            self.lbl_raw_mag_mz.setText("+0.00")
        if hasattr(self, 'lbl_raw_mag_total') and self.lbl_raw_mag_total:
            self.lbl_raw_mag_total.setText("0.00")
            
        if hasattr(self, 'lbl_raw_vision_dist') and self.lbl_raw_vision_dist:
            self.lbl_raw_vision_dist.setText("0.0 m")
        if hasattr(self, 'lbl_raw_vision_angle') and self.lbl_raw_vision_angle:
            self.lbl_raw_vision_angle.setText("+0.0°")
        if hasattr(self, 'lbl_raw_vision_status') and self.lbl_raw_vision_status:
            self.lbl_raw_vision_status.setText("LOST")
            self.lbl_raw_vision_status.setStyleSheet("color: #FF1744; font-size: 9px; font-weight: bold;")
            
        if hasattr(self, 'lbl_docking_v_dist') and self.lbl_docking_v_dist:
            self.lbl_docking_v_dist.setText("0.0 m")
        if hasattr(self, 'lbl_docking_v_angle') and self.lbl_docking_v_angle:
            self.lbl_docking_v_angle.setText("+0.0°")
        if hasattr(self, 'lbl_docking_v_status') and self.lbl_docking_v_status:
            self.lbl_docking_v_status.setText("LOST")
            self.lbl_docking_v_status.setStyleSheet("color: #FF1744; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_docking_v_conf') and self.lbl_docking_v_conf:
            self.lbl_docking_v_conf.setText("0 %")
            
        if hasattr(self, 'lbl_dock_align_lat') and self.lbl_dock_align_lat:
            self.lbl_dock_align_lat.setText("0.00 m")
        if hasattr(self, 'lbl_dock_align_ang') and self.lbl_dock_align_ang:
            self.lbl_dock_align_ang.setText("+0.0°")
        if hasattr(self, 'lbl_dock_align_dist') and self.lbl_dock_align_dist:
            self.lbl_dock_align_dist.setText("0.0 m")
        if hasattr(self, 'lbl_dock_align_qual_bar') and self.lbl_dock_align_qual_bar:
            self.lbl_dock_align_qual_bar.setText("░" * 16)
            self.lbl_dock_align_qual_bar.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 8.5px;")
        if hasattr(self, 'lbl_dock_align_qual_num') and self.lbl_dock_align_qual_num:
            self.lbl_dock_align_qual_num.setText("0%")

        # Reset Docking Status checklist rows
        if hasattr(self, 'lbl_dock_status_sonar_dot') and self.lbl_dock_status_sonar_dot:
            self.lbl_dock_status_sonar_dot.setText("●")
            self.lbl_dock_status_sonar_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_dock_status_mag_dot') and self.lbl_dock_status_mag_dot:
            self.lbl_dock_status_mag_dot.setText("●")
            self.lbl_dock_status_mag_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_dock_status_vision_dot') and self.lbl_dock_status_vision_dot:
            self.lbl_dock_status_vision_dot.setText("●")
            self.lbl_dock_status_vision_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_dock_status_target_dot') and self.lbl_dock_status_target_dot:
            self.lbl_dock_status_target_dot.setText("●")
            self.lbl_dock_status_target_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_dock_status_align_dot') and self.lbl_dock_status_align_dot:
            self.lbl_dock_status_align_dot.setText("●")
            self.lbl_dock_status_align_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_dock_status_align_val') and self.lbl_dock_status_align_val:
            self.lbl_dock_status_align_val.setText("INACTIVE")
            self.lbl_dock_status_align_val.setStyleSheet("color: #888888; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_dock_status_ready_dot') and self.lbl_dock_status_ready_dot:
            self.lbl_dock_status_ready_dot.setText("●")
            self.lbl_dock_status_ready_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_dock_status_ready_val') and self.lbl_dock_status_ready_val:
            self.lbl_dock_status_ready_val.setText("INACTIVE")
            self.lbl_dock_status_ready_val.setStyleSheet("color: #888888; font-size: 9.5px; font-weight: bold;")

        # Reset Communication Page Widgets
        if hasattr(self, 'comm_modem_widget') and self.comm_modem_widget:
            self.comm_modem_widget.update_modem("00:00:00", 0.0, 0.0, 0, "INACTIVE")
        if hasattr(self, 'comm_rov_positioning') and self.comm_rov_positioning:
            self.comm_rov_positioning.update_position(0.0, 0.0, 0.0, 0.0, 0.0)
        if hasattr(self, 'comm_hydrophone') and self.comm_hydrophone:
            self.comm_hydrophone.update_audio(0.0, -100.0, 0.0, "STANDBY")

        # Reset Communication Page Boxes & Labels
        if hasattr(self, 'lbl_comm_modem_rate') and self.lbl_comm_modem_rate:
            self.lbl_comm_modem_rate.setText("0.0 kbps")
        if hasattr(self, 'lbl_comm_modem_lat') and self.lbl_comm_modem_lat:
            self.lbl_comm_modem_lat.setText("0 ms")
        if hasattr(self, 'lbl_comm_modem_qual') and self.lbl_comm_modem_qual:
            self.lbl_comm_modem_qual.setText("INACTIVE")
            self.lbl_comm_modem_qual.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_comm_stat_tx') and self.lbl_comm_stat_tx:
            self.lbl_comm_stat_tx.setText("0")
        if hasattr(self, 'lbl_comm_stat_rx') and self.lbl_comm_stat_rx:
            self.lbl_comm_stat_rx.setText("0")
        if hasattr(self, 'lbl_comm_stat_loss') and self.lbl_comm_stat_loss:
            self.lbl_comm_stat_loss.setText("0.00 %")
            self.lbl_comm_stat_loss.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_comm_stat_err') and self.lbl_comm_stat_err:
            self.lbl_comm_stat_err.setText("0")
        if hasattr(self, 'lbl_comm_rov_range') and self.lbl_comm_rov_range:
            self.lbl_comm_rov_range.setText("0.00 m")
        if hasattr(self, 'lbl_comm_rov_bearing') and self.lbl_comm_rov_bearing:
            self.lbl_comm_rov_bearing.setText("0.0°")
        if hasattr(self, 'lbl_comm_stat_pq') and self.lbl_comm_stat_pq:
            self.lbl_comm_stat_pq.setText("INACTIVE")
            self.lbl_comm_stat_pq.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_comm_stat_hdop') and self.lbl_comm_stat_hdop:
            self.lbl_comm_stat_hdop.setText("0.00")
        if hasattr(self, 'lbl_comm_hist_max') and self.lbl_comm_hist_max:
            self.lbl_comm_hist_max.setText("0.00 m")
        if hasattr(self, 'lbl_comm_hist_avg') and self.lbl_comm_hist_avg:
            self.lbl_comm_hist_avg.setText("0.00 m")
        if hasattr(self, 'lbl_comm_hist_min') and self.lbl_comm_hist_min:
            self.lbl_comm_hist_min.setText("0.00 m")
        if hasattr(self, 'lbl_comm_hydro_pf') and self.lbl_comm_hydro_pf:
            self.lbl_comm_hydro_pf.setText("0.0 kHz")
        if hasattr(self, 'lbl_comm_hydro_sl') and self.lbl_comm_hydro_sl:
            self.lbl_comm_hydro_sl.setText("-100 dB")
            self.lbl_comm_hydro_sl.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_comm_hydro_doa') and self.lbl_comm_hydro_doa:
            self.lbl_comm_hydro_doa.setText("0.0°")
        if hasattr(self, 'lbl_comm_hydro_time') and self.lbl_comm_hydro_time:
            self.lbl_comm_hydro_time.setText("--")
        if hasattr(self, 'lbl_comm_hydro_bw') and self.lbl_comm_hydro_bw:
            self.lbl_comm_hydro_bw.setText("0.0 kHz")
        if hasattr(self, 'lbl_comm_hydro_stat') and self.lbl_comm_hydro_stat:
            self.lbl_comm_hydro_stat.setText("STANDBY")
            self.lbl_comm_hydro_stat.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")

        # Reset Depth Page Widgets
        if hasattr(self, 'depth_dvl_widget') and self.depth_dvl_widget:
            self.depth_dvl_widget.update_dvl(0.0, False, 0, 0.0, 0.0, 0.0)
        if hasattr(self, 'depth_pressure') and self.depth_pressure:
            self.depth_pressure.update_pressure(0.0, 0.0)
        if hasattr(self, 'water_column') and self.water_column:
            self.water_column.update_depth(0.0, 0.0)
        if hasattr(self, 'depth_quality_widget') and self.depth_quality_widget:
            self.depth_quality_widget.update_quality(0.0, 0.0, 0.0)
        if hasattr(self, 'altimeter_widget') and self.altimeter_widget:
            self.altimeter_widget.update_altimeter(0.0, 0.0)

        # Reset Depth Page Box & Checklist Labels
        if hasattr(self, 'lbl_depth_altimeter_val') and self.lbl_depth_altimeter_val:
            self.lbl_depth_altimeter_val.setText("0.00 m")
        if hasattr(self, 'lbl_depth_altimeter_conf') and self.lbl_depth_altimeter_conf:
            self.lbl_depth_altimeter_conf.setText("0 %")
            self.lbl_depth_altimeter_conf.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 12px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_dvl_depth') and self.lbl_depth_dvl_depth:
            self.lbl_depth_dvl_depth.setText("0.00 m")
        if hasattr(self, 'lbl_depth_dvl_lock') and self.lbl_depth_dvl_lock:
            self.lbl_depth_dvl_lock.setText("LOST")
            self.lbl_depth_dvl_lock.setStyleSheet("color: #FF1744; font-family: 'Google Sans', monospace; font-size: 12px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_dvl_qual') and self.lbl_depth_dvl_qual:
            self.lbl_depth_dvl_qual.setText("0 %")
            self.lbl_depth_dvl_qual.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 12px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_alt_dot') and self.lbl_depth_status_alt_dot:
            self.lbl_depth_status_alt_dot.setText("●")
            self.lbl_depth_status_alt_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_alt_val') and self.lbl_depth_status_alt_val:
            self.lbl_depth_status_alt_val.setText("INACTIVE")
            self.lbl_depth_status_alt_val.setStyleSheet("color: #888888; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_press_dot') and self.lbl_depth_status_press_dot:
            self.lbl_depth_status_press_dot.setText("●")
            self.lbl_depth_status_press_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_press_val') and self.lbl_depth_status_press_val:
            self.lbl_depth_status_press_val.setText("INACTIVE")
            self.lbl_depth_status_press_val.setStyleSheet("color: #888888; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_dvl_dot') and self.lbl_depth_status_dvl_dot:
            self.lbl_depth_status_dvl_dot.setText("●")
            self.lbl_depth_status_dvl_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_dvl_val') and self.lbl_depth_status_dvl_val:
            self.lbl_depth_status_dvl_val.setText("INACTIVE")
            self.lbl_depth_status_dvl_val.setStyleSheet("color: #888888; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_lock_dot') and self.lbl_depth_status_lock_dot:
            self.lbl_depth_status_lock_dot.setText("●")
            self.lbl_depth_status_lock_dot.setStyleSheet("color: #FF1744; font-size: 11px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_lock_val') and self.lbl_depth_status_lock_val:
            self.lbl_depth_status_lock_val.setText("LOST")
            self.lbl_depth_status_lock_val.setStyleSheet("color: #FF1744; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_quality') and self.lbl_depth_status_quality:
            self.lbl_depth_status_quality.setText("INACTIVE")
            self.lbl_depth_status_quality.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_acc') and self.lbl_depth_status_acc:
            self.lbl_depth_status_acc.setText("0.00 m")
            self.lbl_depth_status_acc.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
        if hasattr(self, 'lbl_depth_status_conf') and self.lbl_depth_status_conf:
            self.lbl_depth_status_conf.setText("0 %")
            self.lbl_depth_status_conf.setStyleSheet("color: #888888; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")

        # Reset Raw Sensor Sidebar Labels (Depth Page)
        if hasattr(self, 'lbl_raw_depth_alt_val') and self.lbl_raw_depth_alt_val:
            self.lbl_raw_depth_alt_val.setText("0.00")
        if hasattr(self, 'lbl_raw_depth_alt_conf') and self.lbl_raw_depth_alt_conf:
            self.lbl_raw_depth_alt_conf.setText("0")
        if hasattr(self, 'lbl_raw_depth_press_bar') and self.lbl_raw_depth_press_bar:
            self.lbl_raw_depth_press_bar.setText("0.000")
        if hasattr(self, 'lbl_raw_depth_press_kpa') and self.lbl_raw_depth_press_kpa:
            self.lbl_raw_depth_press_kpa.setText("0.0")
        if hasattr(self, 'lbl_raw_depth_press_depth') and self.lbl_raw_depth_press_depth:
            self.lbl_raw_depth_press_depth.setText("0.00")
        if hasattr(self, 'lbl_raw_depth_press_temp') and self.lbl_raw_depth_press_temp:
            self.lbl_raw_depth_press_temp.setText("0.0")
        if hasattr(self, 'lbl_raw_depth_chamber_temp') and self.lbl_raw_depth_chamber_temp:
            self.lbl_raw_depth_chamber_temp.setText("0.0")
        if hasattr(self, 'lbl_raw_depth_dvl_val') and self.lbl_raw_depth_dvl_val:
            self.lbl_raw_depth_dvl_val.setText("0.00")
        if hasattr(self, 'lbl_raw_depth_dvl_vx') and self.lbl_raw_depth_dvl_vx:
            self.lbl_raw_depth_dvl_vx.setText("0.00")
        if hasattr(self, 'lbl_raw_depth_dvl_vy') and self.lbl_raw_depth_dvl_vy:
            self.lbl_raw_depth_dvl_vy.setText("0.00")
        if hasattr(self, 'lbl_raw_depth_dvl_vz') and self.lbl_raw_depth_dvl_vz:
            self.lbl_raw_depth_dvl_vz.setText("0.00")
        if hasattr(self, 'lbl_raw_depth_dvl_lock') and self.lbl_raw_depth_dvl_lock:
            self.lbl_raw_depth_dvl_lock.setText("LOST")
            self.lbl_raw_depth_dvl_lock.setStyleSheet("color: #FF1744; font-size: 9px; font-weight: bold;")

        # Clear logs and detections tables
        if hasattr(self, 'tbl_packet_monitor') and self.tbl_packet_monitor:
            self.tbl_packet_monitor.setRowCount(0)
        if hasattr(self, 'tbl_hydro_detections') and self.tbl_hydro_detections:
            self.tbl_hydro_detections.setRowCount(0)
        if hasattr(self, 'tbl_depth_logs') and self.tbl_depth_logs:
            self.tbl_depth_logs.setRowCount(0)
        if hasattr(self, 'tbl_docking_logs') and self.tbl_docking_logs:
            self.tbl_docking_logs.setRowCount(0)



    @Slot(dict)
    def update_telemetry(self, data):
        # Ensure all key telemetry variables have safe defaults to prevent KeyErrors
        default_keys = {
            "roll": 0.0, "pitch": 0.0, "yaw": 0.0,
            "latitude": 0.0, "longitude": 0.0, "satellites": 0,
            "chamber_temp": 0.0, "chamber_hum": 0.0,
            "bms_volt": 0.0, "bms_curr": 0.0, "bms_soc": 0, "bms_soh": 100,
            "bms_temp": 0.0,
            "pwm_rc1": 1500, "pwm_rc2": 1500, "pwm_rc3": 1500,
            "distance": 0.0, "confidence": 100.0,
            "mx": 0.0, "my": 0.0, "mz": 0.0
        }
        for k, v in default_keys.items():
            if k not in data or data[k] is None:
                data[k] = v

        # 1. GPS Satellites Filtering (bounds check [0, 32], fallback to last known valid count)
        sats = data.get('satellites', 0)
        if not hasattr(self, '_last_valid_sats'):
            self._last_valid_sats = 8  # Fallback baseline count
        if 0 <= sats <= 32:
            self._last_valid_sats = sats
        else:
            sats = self._last_valid_sats
        data['satellites'] = sats

        # 2. GPS Latitude/Longitude Smoothening Filter (Exponential Moving Average)
        if data['latitude'] != 0.0 and data['longitude'] != 0.0:
            if not hasattr(self, '_filtered_lat') or self._filtered_lat is None:
                self._filtered_lat = data['latitude']
            if not hasattr(self, '_filtered_lon') or self._filtered_lon is None:
                self._filtered_lon = data['longitude']
            
            alpha = 0.2  # Smoothing factor (alpha)
            self._filtered_lat = alpha * data['latitude'] + (1 - alpha) * self._filtered_lat
            self._filtered_lon = alpha * data['longitude'] + (1 - alpha) * self._filtered_lon
            
            data['latitude'] = self._filtered_lat
            data['longitude'] = self._filtered_lon

        # Capture original values for top bar update
        original_gps = data['satellites']
        original_soc = data['bms_soc']
        self.last_sats = original_gps
        self.last_yaw = data.get('yaw', 0.0)
        self.last_roll = data.get('roll', 0.0)
        self.last_pitch = data.get('pitch', 0.0)

        self._docking_sonar_angle = getattr(self, '_docking_sonar_angle', 0.0) + 1.0
        
        # NOTE: The zeroing-out block below is commented out to prevent:
        # - False critical battery failsafes when navigating away from the dashboard
        # - Telemetry data log corruption with zeroes
        # - GPS map jumping to 0.0, 0.0 (Null Island)
        # Showcase data receiving only in the 5 dashboard viewing pages (visualization). Make others to 0.
        current_page = self.stacked_widget.currentIndex()
        # if current_page not in [0, 6, 7, 8, 9]:
        #     data = data.copy()
        #     for k in data.keys():
        #         if k == 'mode':
        #             continue
        #         if isinstance(data[k], float):
        #             data[k] = 0.0
        #         elif isinstance(data[k], int):
        #             data[k] = 0
        
        # We received a valid data packet! Reset watchdog timer
        self.watchdog_timer.start()
        
        # Override data fields based on simulated alarm flags
        active_warnings = []
        
        if getattr(self, 'sim_gps_loss', False):
            data['satellites'] = 0
            data['latitude'] = 0.0
            data['longitude'] = 0.0
            active_warnings.append("CRITICAL: GPS SIGNAL LOSS (0 SATS)")
            # Flashing card styles for GPS loss
            if current_page == 0:
                self.cards["latitude"].setStyleSheet("QFrame { border: 2.5px solid #FF1744; background-color: #2D080D; }")
                self.cards["longitude"].setStyleSheet("QFrame { border: 2.5px solid #FF1744; background-color: #2D080D; }")
                self.cards["satellites"].setStyleSheet("QFrame { border: 2.5px solid #FF1744; background-color: #2D080D; }")
        else:
            if current_page == 0:
                self.cards["latitude"].setStyleSheet("")
                self.cards["longitude"].setStyleSheet("")
                self.cards["satellites"].setStyleSheet("")
            
        if getattr(self, 'sim_sonar_dropout', False):
            data['distance'] = 0.0
            data['confidence'] = 0.0
            active_warnings.append("WARNING: SONAR ALTIMETER DROPOUT")
            if current_page == 0:
                self.cards["distance"].setStyleSheet("QFrame { border: 2.5px solid #FF1744; background-color: #2D080D; }")
                self.cards["confidence"].setStyleSheet("QFrame { border: 2.5px solid #FF1744; background-color: #2D080D; }")
        else:
            if current_page == 0:
                self.cards["distance"].setStyleSheet("")
                self.cards["confidence"].setStyleSheet("")
            
        if getattr(self, 'sim_low_battery', False):
            active_warnings.append("CRITICAL: LOW BATTERY FAULT (<11.2V)")
            if current_page == 0:
                self.cards["roll"].setStyleSheet("QFrame { border: 2.5px solid #FF1744; background-color: #2D080D; }")
                self.cards["pitch"].setStyleSheet("QFrame { border: 2.5px solid #FF1744; background-color: #2D080D; }")
        else:
            if current_page == 0:
                self.cards["roll"].setStyleSheet("")
                self.cards["pitch"].setStyleSheet("")
            
        # --- 1. Battery SOC Safety State Machine with Hysteresis ---
        soc_val = data.get('bms_soc', 100)
        if not hasattr(self, 'batt_state'):
            self.batt_state = "normal"
            
        if soc_val > 0:
            if self.batt_state == "normal":
                if soc_val <= 30:
                    self.batt_state = "critical"
                elif soc_val < 45:
                    self.batt_state = "warning"
            elif self.batt_state == "warning":
                if soc_val <= 30:
                    self.batt_state = "critical"
                elif soc_val >= 47:
                    self.batt_state = "normal"
            elif self.batt_state == "critical":
                if soc_val >= 33:
                    if soc_val >= 47:
                        self.batt_state = "normal"
                    else:
                        self.batt_state = "warning"
        else:
            self.batt_state = "normal"
                    
        # Apply battery card styles and warnings
        if self.batt_state == "warning":
            active_warnings.append("⚠️ LOW BATTERY WARNING: Battery SOC is below 45%!")
            if current_page == 0:
                self.cards["soc"].setStyleSheet("QFrame { border: 2.5px solid #FF9F43; background-color: #2A1800; }")
                self.cards["volts"].setStyleSheet("QFrame { border: 2.5px solid #FF9F43; background-color: #2A1800; }")
        elif self.batt_state == "critical":
            active_warnings.append("🚨 CRITICAL BATTERY FAILSAFE (SOC ≤ 30%)! All thrusters, camera & light disabled.")
            if current_page == 0:
                self.cards["soc"].setStyleSheet("QFrame { border: 2.5px solid #FF4757; background-color: #2D080D; }")
                self.cards["volts"].setStyleSheet("QFrame { border: 2.5px solid #FF4757; background-color: #2D080D; }")
        else:
            if current_page == 0:
                self.cards["soc"].setStyleSheet("")
                self.cards["volts"].setStyleSheet("")

        # --- 2. Chamber Temperature Safety State Machine with Hysteresis ---
        temp_val = data.get('chamber_temp', 0.0)
        if not hasattr(self, 'temp_state'):
            self.temp_state = "normal"
            
        if self.temp_state == "normal":
            if temp_val > 55.0:
                self.temp_state = "critical"
            elif temp_val > 48.0:
                self.temp_state = "warning"
        elif self.temp_state == "warning":
            if temp_val > 55.0:
                self.temp_state = "critical"
            elif temp_val <= 46.5:
                self.temp_state = "normal"
        elif self.temp_state == "critical":
            if temp_val <= 53.0:
                if temp_val <= 46.5:
                    self.temp_state = "normal"
                else:
                    self.temp_state = "warning"
                    
        # Apply temperature card styles and warnings
        if self.temp_state == "warning":
            active_warnings.append("⚠️ HIGH CHAMBER TEMP WARNING: Temperature is > 48°C!")
            if current_page == 0:
                self.cards["chamber_temp"].setStyleSheet("QFrame { border: 2.5px solid #FF9F43; background-color: #2A1800; }")
        elif self.temp_state == "critical":
            active_warnings.append("🚨 CRITICAL OVERHEATING FAILSAFE (Chamber Temp > 55°C)! Emergency shutdown activated.")
            if current_page == 0:
                self.cards["chamber_temp"].setStyleSheet("QFrame { border: 2.5px solid #FF4757; background-color: #2D080D; }")
        else:
            if current_page == 0:
                self.cards["chamber_temp"].setStyleSheet("")

        # --- 3. Evaluate Failsafe Actions & Enforce Limits ---
        is_now_failsafe = (self.batt_state == "critical" or self.temp_state == "critical")
        if is_now_failsafe:
            if not getattr(self, 'failsafe_active', False):
                self.failsafe_active = True
                print("[SAFETY] Critical failsafe active! Zeroing thrusters and turning off relays.")
            
            # Force relays OFF
            if self.light_state == 1:
                self.update_light_ui_state(False)
            if self.camera_state == 1:
                self.update_camera_ui_state(False)
            if self.telemetry_thread and self.telemetry_thread.isRunning():
                self.telemetry_thread.light_state = 0
                self.telemetry_thread.camera_state = 0
                
            # Zero output fields to neutral
            for rc_key in ["rc1", "rc2", "rc3"]:
                if rc_key in self.rc_output_fields:
                    self.rc_output_fields[rc_key].setText("1500")
            # Immediately transmit neutral commands to node
            self.send_immediate_cmd()
        else:
            if getattr(self, 'failsafe_active', False):
                self.failsafe_active = False
                print("[SAFETY] Failsafe released. Resuming normal operations.")
                
        # Enable or disable UI toggles based on failsafe state
        if hasattr(self, 'chk_light') and self.chk_light:
            self.chk_light.setEnabled(not self.failsafe_active)
        if hasattr(self, 'chk_camera') and self.chk_camera:
            self.chk_camera.setEnabled(not self.failsafe_active)

        # --- 4. Asynchronous Sound Triggers ---
        import time
        now_time = time.time()
        
        def play_warning_sound(freq, is_critical):
            try:
                import winsound
                if is_critical:
                    winsound.Beep(freq, 120)
                    import time
                    time.sleep(0.08)
                    winsound.Beep(freq, 120)
                else:
                    winsound.Beep(freq, 150)
            except:
                pass

        # Temperature Sound Play
        if self.temp_state != "normal":
            is_crit = (self.temp_state == "critical")
            freq = 1800 if is_crit else 1200
            cooldown = 3.0 if is_crit else 5.0
            if not hasattr(self, '_last_temp_sound_time'):
                self._last_temp_sound_time = 0.0
            if now_time - self._last_temp_sound_time >= cooldown:
                self._last_temp_sound_time = now_time
                import threading
                threading.Thread(target=play_warning_sound, args=(freq, is_crit), daemon=True).start()

        # Battery Sound Play (staggered slightly if temp warning is also active to avoid conflicts)
        if self.batt_state != "normal":
            is_crit = (self.batt_state == "critical")
            freq = 1600 if is_crit else 1000
            cooldown = 3.0 if is_crit else 5.0
            if not hasattr(self, '_last_batt_sound_time'):
                self._last_batt_sound_time = 0.0
            delay = 0.5 if (self.temp_state != "normal") else 0.0
            if now_time - self._last_batt_sound_time >= cooldown:
                self._last_batt_sound_time = now_time
                def delayed_play():
                    if delay > 0:
                        import time
                        time.sleep(delay)
                    play_warning_sound(freq, is_crit)
                import threading
                threading.Thread(target=delayed_play, daemon=True).start()

        # Update Warning Banner
        if active_warnings:
            warn_text = "  |  ".join(active_warnings)
            self.lbl_warning_banner.setText(f"⚠️ SYSTEM WARNINGS: {warn_text}")
            self.warning_banner_frame.setVisible(True)
            if not self.warning_flash_timer.isActive():
                self.warning_flash_timer.start()
        else:
            self.warning_banner_frame.setVisible(False)
            self.warning_flash_timer.stop()

        # Update Top Bar Alert Badge (Option 2: Pulsing Pill)
        if active_warnings:
            has_crit = (getattr(self, 'batt_state', 'normal') == 'critical' or getattr(self, 'temp_state', 'normal') == 'critical')
            alert_count = len(active_warnings)
            badge_text = f"🚨 {alert_count} FAILSAFE" if has_crit else f"⚠️ {alert_count} ALERTS"
            self.top_bar.alert_badge.setText(badge_text)
            self.top_bar.alert_badge.setVisible(True)
            
            border_color = "#FF4757" if has_crit else "#FF9F43"
            if self.warning_flash_state:
                bg_col = "#5C0B14" if has_crit else "#4F2F00"
            else:
                bg_col = "#2D080D" if has_crit else "#2A1800"
                
            self.top_bar.alert_badge.setStyleSheet(f"""
                QPushButton#TopBarAlertBadge {{
                    background-color: {bg_col};
                    border: 1px solid {border_color};
                    border-radius: 10px;
                    color: {border_color};
                    font-family: 'Google Sans', sans-serif;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 2px 10px;
                }}
            """)
        else:
            self.top_bar.alert_badge.setVisible(False)

        # Trigger Slide-in Toast Notifications (Option 1)
        if not hasattr(self, '_prev_active_warnings'):
            self._prev_active_warnings = set()
            
        current_warnings_set = set(active_warnings)
        
        # New warnings trigger toasts
        new_warnings = current_warnings_set - self._prev_active_warnings
        for warn in new_warnings:
            is_crit = ("CRITICAL" in warn or "FAILSAFE" in warn)
            self.show_toast_alert(warn, is_crit)
            
        # Old resolved warnings close their toasts
        resolved_warnings = self._prev_active_warnings - current_warnings_set
        for warn in resolved_warnings:
            if hasattr(self, '_active_toasts') and warn in self._active_toasts:
                self._active_toasts[warn].close_toast()
                
        self._prev_active_warnings = current_warnings_set
        
        # Log telemetry data if enabled
        if hasattr(self, 'logging_enabled') and self.logging_enabled:
            try:
                if not self.log_file_path:
                    import time
                    timestamp_fn = time.strftime("asv_telemetry_%Y%m%d_%H%M%S.csv")
                    self.log_file_path = os.path.join(self.log_folder_path, timestamp_fn)
                    
                from PySide6.QtCore import QDateTime
                t_str = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
                ct_val = data.get('chamber_temp', 0.0)
                bms_volt = data.get('bms_volt', 0.0)
                bms_curr = data.get('bms_curr', 0.0)
                bms_soc = data.get('bms_soc', 0)
                
                # Fetch PWM pulses (either from telemetry data packet or live Ground Station joystick outputs)
                pwm_rc1 = data.get('pwm_rc1')
                pwm_rc2 = data.get('pwm_rc2')
                pwm_rc3 = data.get('pwm_rc3')
                
                if pwm_rc1 is None or pwm_rc2 is None or pwm_rc3 is None:
                    try:
                        pwm_rc1 = int(self.rc_output_fields["rc1"].text())
                        pwm_rc2 = int(self.rc_output_fields["rc2"].text())
                        pwm_rc3 = int(self.rc_output_fields["rc3"].text())
                    except:
                        pwm_rc1 = pwm_rc1 if pwm_rc1 is not None else 1500
                        pwm_rc2 = pwm_rc2 if pwm_rc2 is not None else 1500
                        pwm_rc3 = pwm_rc3 if pwm_rc3 is not None else 1500

                import math
                ms5837_press = data.get('ms5837_press')
                ms5837_temp = data.get('ms5837_temp')
                ms5837_depth = data.get('ms5837_depth')
                if ms5837_press is None:
                    ms5837_press = 1.013 + (15.0 - data['distance']) * 0.1
                if ms5837_temp is None:
                    ms5837_temp = 22.6 + math.sin(self._docking_sonar_angle * 0.05) * 0.2
                if ms5837_depth is None:
                    ms5837_depth = max(0.0, (15.0 - data['distance']))

                alert_str = ";".join(active_warnings) if active_warnings else "NONE"
                log_line = (f"{t_str},{data['roll']:.2f},{data['pitch']:.2f},{data['yaw']:.2f},"
                            f"{data['latitude']:.6f},{data['longitude']:.6f},{data['satellites']},"
                            f"{data.get('chamber_temp', 0.0):.2f},{data.get('chamber_hum', 0.0):.2f},"
                            f"{bms_volt:.2f},{bms_curr:.3f},{bms_soc},"
                            f"{data.get('bms_temp', 0.0):.2f},"
                            f"{pwm_rc1},{pwm_rc2},{pwm_rc3},"
                            f"{1 if self.light_state == 1 else 0},"
                            f"{0 if self.light_state == 1 else 1},"
                            f"\"{alert_str}\"\n")
                write_header = not os.path.exists(self.log_file_path)
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    if write_header:
                        f.write("TIMESTAMP,ROLL,PITCH,YAW,LATITUDE,LONGITUDE,SATELLITES,CHAMBER_TEMP,CHAMBER_HUMIDITY,BMS_VOLT,BMS_CURR,BMS_SOC,BATT_TEMP,PWM_RC1,PWM_RC2,PWM_RC3,LIGHT_ON,LIGHT_OFF,ALERT_STATUS\n")
                    f.write(log_line)
            except Exception as e:
                print(f"Error writing telemetry to log file: {e}")
        
        # Rate-limit all GUI rendering updates to 10Hz (once every 100ms)
        import time
        now_time = time.time()
        if not hasattr(self, '_last_gui_update_time'):
            self._last_gui_update_time = 0.0
        if now_time - self._last_gui_update_time < 0.1:
            # Return early (watchdog and telemetry logger still run at full rate above)
            return
        self._last_gui_update_time = now_time

        # If UI is not in connected state, transition it now (green glow)
        if self.top_bar.status_state != "connected":
            port_label = self.telemetry_thread.port.upper()
            self.top_bar.set_connection_status("connected", f"{port_label} Active")
            if current_page == 0:
                for card in self.cards.values():
                    card.set_status("connected")
        
        # Always update top bar statistics at 10Hz
        self.top_bar.set_gps_count(original_gps)
        self.top_bar.set_battery_percentage(original_soc)
        self.top_bar.set_chamber_temp(data.get('chamber_temp', 0.0))
        
        # Compute visual yaw incorporating UI nose offset for rendering
        visual_offset = getattr(self, 'visual_heading_offset', -90.0)
        visual_yaw = (data['yaw'] + visual_offset) % 360.0

        # Only update Dashboard-specific widgets if Dashboard is the active tab
        if current_page == 0:
            # Update cards
            self.cards["roll"].set_value(f"{data['roll']:.2f}")
            self.cards["pitch"].set_value(f"{data['pitch']:.2f}")
            self.cards["yaw"].set_value(f"{visual_yaw:.2f}")
            
            self.cards["latitude"].set_value(f"{abs(data['latitude']):.6f}")
            self.cards["latitude"].unit_label.setText("N" if data['latitude'] >= 0 else "S")
            
            self.cards["longitude"].set_value(f"{abs(data['longitude']):.6f}")
            self.cards["longitude"].unit_label.setText("E" if data['longitude'] >= 0 else "W")
            
            self.cards["satellites"].set_value(data['satellites'])
            self.cards["chamber_temp"].set_value(f"{data.get('chamber_temp', 0.0):.2f}")
            self.cards["chamber_hum"].set_value(f"{data.get('chamber_hum', 0.0):.2f}")
            
            bms_volt = data.get('bms_volt', 0.0)
            bms_curr = data.get('bms_curr', 0.0)
            bms_soc = data.get('bms_soc', 0)
            bms_soh = data.get('bms_soh', 100)
            self.cards["volts"].set_value(f"{bms_volt:.2f}")
            self.cards["amps"].set_value(f"{bms_curr:.3f}")
            self.cards["watts"].set_value(f"{(bms_volt * bms_curr):.2f}")
            self.cards["soc"].set_value(bms_soc)
            self.cards["soh"].set_value(bms_soh)
            
            pwm_rc1_val = data.get('pwm_rc1', 1500)
            pwm_rc2_val = data.get('pwm_rc2', 1500)
            pwm_rc3_val = data.get('pwm_rc3', 1500)
            self.cards["p1"].set_value(pwm_rc1_val)
            self.cards["p2"].set_value(pwm_rc2_val)
            self.cards["p3"].set_value(pwm_rc3_val)
            
            # Shim cards update
            self.cards["distance"].set_value(f"{data.get('distance', 0.0):.2f}")
            self.cards["confidence"].set_value(f"{int(data.get('confidence', 0.0))}")
            self.cards["mx"].set_value(f"{data.get('mx', 0.0):.1f}")
            self.cards["my"].set_value(f"{data.get('my', 0.0):.1f}")
            self.cards["mz"].set_value(f"{data.get('mz', 0.0):.1f}")
            
            # Update instrument widgets
            self.compass_widget.set_yaw(visual_yaw)
            self.horizon_widget.set_attitude(data['roll'], data['pitch'])
            self.horizon_3d_widget.set_attitude(data['roll'], data['pitch'])
            
            # Update custom visual gauges
            self.battery_gauge.set_soc(bms_soc)
            self.actuators_gauge.set_values(pwm_rc1_val, pwm_rc2_val, pwm_rc3_val)
            
            # Update dynamic scrolling plots
            self.attitude_chart.append_data([data['roll'], data['pitch']])
            self.gps_chart.append_data([data['satellites']])
            self.env_chart.append_data([data.get('chamber_temp', 0.0), data.get('chamber_hum', 0.0)])
            self.power_chart.append_data([bms_volt, bms_curr])
            self.actuators_chart.append_data([pwm_rc1_val, pwm_rc2_val, pwm_rc3_val])
            
        # Get target bearing to next waypoint if mission is active
        target_bearing = None
        if self.mission_active and self.planned_waypoints and self.current_wp_idx < len(self.planned_waypoints):
            target_lat, target_lon = self.planned_waypoints[self.current_wp_idx]
            target_bearing = self.calculate_bearing(data['latitude'], data['longitude'], target_lat, target_lon)

        # Update Navigation Page Widgets
        if current_page == 1:
            if hasattr(self, 'nav_vessel_3d') and self.nav_vessel_3d:
                self.nav_vessel_3d.set_attitude(data['roll'], data['pitch'], visual_yaw)
            if hasattr(self, 'nav_horizon') and self.nav_horizon:
                self.nav_horizon.set_attitude(data['roll'], data['pitch'], visual_yaw)
            if hasattr(self, 'nav_compass_widget') and self.nav_compass_widget:
                self.nav_compass_widget.set_heading(visual_yaw)
            if hasattr(self, 'nav_skyplot') and self.nav_skyplot:
                self.nav_skyplot.set_satellites(data['satellites'])
            
                
            if hasattr(self, 'lbl_nav_roll') and self.lbl_nav_roll:
                self.lbl_nav_roll.setText(f"+{data['roll']:.1f}°" if data['roll'] >= 0 else f"{data['roll']:.1f}°")
            if hasattr(self, 'lbl_nav_pitch') and self.lbl_nav_pitch:
                self.lbl_nav_pitch.setText(f"+{data['pitch']:.1f}°" if data['pitch'] >= 0 else f"{data['pitch']:.1f}°")
            if hasattr(self, 'lbl_nav_yaw') and self.lbl_nav_yaw:
                self.lbl_nav_yaw.setText(f"{visual_yaw:.1f}°")
                
            if hasattr(self, 'lbl_nav_lat') and self.lbl_nav_lat:
                lat_dir = "N" if data['latitude'] >= 0 else "S"
                self.lbl_nav_lat.setText(f"{abs(data['latitude']):.6f}° {lat_dir}")
            if hasattr(self, 'lbl_nav_lon') and self.lbl_nav_lon:
                lon_dir = "E" if data['longitude'] >= 0 else "W"
                self.lbl_nav_lon.setText(f"{abs(data['longitude']):.6f}° {lon_dir}")
            if hasattr(self, 'lbl_nav_sats') and self.lbl_nav_sats:
                self.lbl_nav_sats.setText(str(data['satellites']))
                
            if hasattr(self, 'lbl_nav_status') and self.lbl_nav_status:
                self.lbl_nav_status.setText("CONNECTED" if self.top_bar.status_state == "connected" else "DISCONNECTED")
                self.lbl_nav_status.setStyleSheet("color: #00E676; font-weight: bold; font-size: 10px;" if self.top_bar.status_state == "connected" else "color: #FF1744; font-weight: bold; font-size: 10px;")
            if hasattr(self, 'lbl_nav_quality') and self.lbl_nav_quality:
                self.lbl_nav_quality.setText(f"{int(data['confidence'] * 10):d}%" if 'confidence' in data else "98%")
            if hasattr(self, 'lbl_nav_time') and self.lbl_nav_time:
                self.lbl_nav_time.setText(QDateTime.currentDateTime().toString("hh:mm:ss"))
                
            # Update BMS labels
            if hasattr(self, 'lbl_nav_voltage') and self.lbl_nav_voltage:
                self.lbl_nav_voltage.setText(f"{data.get('bms_volt', 0.0):.2f} V")
            if hasattr(self, 'lbl_nav_current') and self.lbl_nav_current:
                self.lbl_nav_current.setText(f"{data.get('bms_curr', 0.0):.2f} A")
            if hasattr(self, 'lbl_nav_soc') and self.lbl_nav_soc:
                self.lbl_nav_soc.setText(f"{data.get('bms_soc', 0)} %")
            if hasattr(self, 'lbl_nav_rem_ah') and self.lbl_nav_rem_ah:
                self.lbl_nav_rem_ah.setText(f"{data.get('bms_remaining_ah', 0.0):.2f} Ah")
            if hasattr(self, 'lbl_nav_max_ah') and self.lbl_nav_max_ah:
                self.lbl_nav_max_ah.setText(f"{data.get('bms_max_ah', 15.0):.2f} Ah")
            if hasattr(self, 'lbl_nav_soh') and self.lbl_nav_soh:
                self.lbl_nav_soh.setText(f"{data.get('bms_soh', 0)} %")
            if hasattr(self, 'lbl_nav_batt_temp') and self.lbl_nav_batt_temp:
                self.lbl_nav_batt_temp.setText(f"{data.get('bms_temp', 0.0):.1f} °C")
            
        # Update Docking Page Widgets
        if current_page in [6, 7, 8, 9]:
            if hasattr(self, 'docking_sonar'):
                self.docking_sonar.update_scan_line(0.0, 12.0, [0]*60)
                
            if hasattr(self, 'docking_mag'):
                self.docking_mag.set_mag_values(0.0, 0.0, 0.0)
                
            if hasattr(self, 'docking_vision'):
                self.docking_vision.set_target(0.0, 0.0, False)
                
            # Update extra docking widgets
            if hasattr(self, 'docking_alignment') and self.docking_alignment:
                self.docking_alignment.set_alignment(0.0, 0.0, 0.0, 0)
                
            if hasattr(self, 'docking_mag_history') and self.docking_mag_history:
                self.docking_mag_history.add_data(0.0, 0.0, 0.0)
                
            if hasattr(self, 'docking_mag_vector') and self.docking_mag_vector:
                self.docking_mag_vector.set_vector(0.0, 0.0, 0.0)
                
            # Update digital readout labels
            if hasattr(self, 'lbl_docking_sonar_range') and self.lbl_docking_sonar_range:
                self.lbl_docking_sonar_range.setText("0.0 m")
            if hasattr(self, 'lbl_docking_sonar_bearing') and self.lbl_docking_sonar_bearing:
                self.lbl_docking_sonar_bearing.setText("0.0°")
                
            if hasattr(self, 'lbl_docking_val_mx') and self.lbl_docking_val_mx:
                self.lbl_docking_val_mx.setText("+0.00")
            if hasattr(self, 'lbl_docking_val_my') and self.lbl_docking_val_my:
                self.lbl_docking_val_my.setText("+0.00")
            if hasattr(self, 'lbl_docking_val_mz') and self.lbl_docking_val_mz:
                self.lbl_docking_val_mz.setText("+0.00")
            if hasattr(self, 'lbl_docking_val_mb') and self.lbl_docking_val_mb:
                self.lbl_docking_val_mb.setText("0.00")
                
            # Update raw sidebar
            if hasattr(self, 'lbl_raw_sonar_range') and self.lbl_raw_sonar_range:
                self.lbl_raw_sonar_range.setText("0.0 m")
            if hasattr(self, 'lbl_raw_sonar_bearing') and self.lbl_raw_sonar_bearing:
                self.lbl_raw_sonar_bearing.setText("0.0°")
                
            if hasattr(self, 'lbl_raw_mag_mx') and self.lbl_raw_mag_mx:
                self.lbl_raw_mag_mx.setText("+0.00")
            if hasattr(self, 'lbl_raw_mag_my') and self.lbl_raw_mag_my:
                self.lbl_raw_mag_my.setText("+0.00")
            if hasattr(self, 'lbl_raw_mag_mz') and self.lbl_raw_mag_mz:
                self.lbl_raw_mag_mz.setText("+0.00")
            if hasattr(self, 'lbl_raw_mag_total') and self.lbl_raw_mag_total:
                self.lbl_raw_mag_total.setText("0.00")
                
            if hasattr(self, 'lbl_raw_vision_dist') and self.lbl_raw_vision_dist:
                self.lbl_raw_vision_dist.setText("0.0 m")
            if hasattr(self, 'lbl_raw_vision_angle') and self.lbl_raw_vision_angle:
                self.lbl_raw_vision_angle.setText("+0.0°")
            if hasattr(self, 'lbl_raw_vision_status') and self.lbl_raw_vision_status:
                self.lbl_raw_vision_status.setText("LOST")
                self.lbl_raw_vision_status.setStyleSheet("color: #FF1744; font-size: 9px; font-weight: bold;")
                
            # Update vision readouts
            if hasattr(self, 'lbl_docking_v_dist') and self.lbl_docking_v_dist:
                self.lbl_docking_v_dist.setText("0.0 m")
            if hasattr(self, 'lbl_docking_v_angle') and self.lbl_docking_v_angle:
                self.lbl_docking_v_angle.setText("+0.0°")
            if hasattr(self, 'lbl_docking_v_status') and self.lbl_docking_v_status:
                self.lbl_docking_v_status.setText("LOST")
            if hasattr(self, 'lbl_docking_v_conf') and self.lbl_docking_v_conf:
                self.lbl_docking_v_conf.setText("0 %")
                
            # Update alignment readouts
            if hasattr(self, 'lbl_dock_align_lat') and self.lbl_dock_align_lat:
                self.lbl_dock_align_lat.setText("0.00 m")
            if hasattr(self, 'lbl_dock_align_ang') and self.lbl_dock_align_ang:
                self.lbl_dock_align_ang.setText("+0.0°")
            if hasattr(self, 'lbl_dock_align_dist') and self.lbl_dock_align_dist:
                self.lbl_dock_align_dist.setText("0.0 m")
            if hasattr(self, 'lbl_dock_align_qual_bar') and self.lbl_dock_align_qual_bar:
                self.lbl_dock_align_qual_bar.setText("░" * 16)
            if hasattr(self, 'lbl_dock_align_qual_num') and self.lbl_dock_align_qual_num:
                self.lbl_dock_align_qual_num.setText("0%")
                
            # Update Docking Status checklist rows when connected/simulator is active
            if hasattr(self, 'lbl_dock_status_sonar_dot') and self.lbl_dock_status_sonar_dot:
                self.lbl_dock_status_sonar_dot.setText("✔")
                self.lbl_dock_status_sonar_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_dock_status_mag_dot') and self.lbl_dock_status_mag_dot:
                self.lbl_dock_status_mag_dot.setText("✔")
                self.lbl_dock_status_mag_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_dock_status_vision_dot') and self.lbl_dock_status_vision_dot:
                self.lbl_dock_status_vision_dot.setText("✔")
                self.lbl_dock_status_vision_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_dock_status_target_dot') and self.lbl_dock_status_target_dot:
                self.lbl_dock_status_target_dot.setText("✔")
                self.lbl_dock_status_target_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_dock_status_align_dot') and self.lbl_dock_status_align_dot:
                self.lbl_dock_status_align_dot.setText("●")
                self.lbl_dock_status_align_dot.setStyleSheet("color: #FFB300; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_dock_status_align_val') and self.lbl_dock_status_align_val:
                self.lbl_dock_status_align_val.setText("IN PROGRESS")
                self.lbl_dock_status_align_val.setStyleSheet("color: #FFB300; font-size: 9.5px; font-weight: bold;")
            if hasattr(self, 'lbl_dock_status_ready_dot') and self.lbl_dock_status_ready_dot:
                self.lbl_dock_status_ready_dot.setText("●")
                self.lbl_dock_status_ready_dot.setStyleSheet("color: #2196F3; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_dock_status_ready_val') and self.lbl_dock_status_ready_val:
                self.lbl_dock_status_ready_val.setText("STANDBY")
                self.lbl_dock_status_ready_val.setStyleSheet("color: #2196F3; font-size: 9.5px; font-weight: bold;")
            
        # Update Communication Page Widgets
        if current_page == 3:
            if hasattr(self, 'comm_modem_widget') and self.comm_modem_widget:
                import time
                if not hasattr(self, '_start_time'):
                    self._start_time = time.time()
                uptime_sec = int(time.time() - self._start_time) + 9918
                h_u = uptime_sec // 3600
                m_u = (uptime_sec % 3600) // 60
                s_u = uptime_sec % 60
                uptime_str = f"{h_u:02d}:{m_u:02d}:{s_u:02d}"
                
                sig_strength = 78.0 + math.sin(self._docking_sonar_angle * 0.1) * 1.5
                self.comm_modem_widget.update_modem(uptime_str, sig_strength, 9.6, 85, "GOOD")
                
            if hasattr(self, 'comm_rov_positioning') and self.comm_rov_positioning:
                angle = getattr(self, '_docking_sonar_angle', 0)
                rx = 2.34 + math.sin(angle * 0.05) * 0.4
                ry = -1.87 + math.cos(angle * 0.05) * 0.3
                rz = -3.12 + math.sin(angle * 0.08) * 0.1
                r_range = math.sqrt(rx**2 + ry**2 + rz**2)
                r_bearing = (132.6 + math.sin(angle * 0.05) * 5.0) % 360
                self.comm_rov_positioning.update_position(rx, ry, rz, r_range, r_bearing)
                
                if hasattr(self, 'lbl_comm_rov_range'):
                    self.lbl_comm_rov_range.setText(f"{r_range:.2f} m")
                if hasattr(self, 'lbl_comm_rov_bearing'):
                    self.lbl_comm_rov_bearing.setText(f"{r_bearing:.1f}°")
                    
            if hasattr(self, 'comm_rov_history') and self.comm_rov_history:
                angle = getattr(self, '_docking_sonar_angle', 0)
                rx = 2.34 + math.sin(angle * 0.05) * 0.4
                ry = -1.87 + math.cos(angle * 0.05) * 0.3
                rz = -3.12 + math.sin(angle * 0.08) * 0.1
                self.comm_rov_history.add_history(rx, ry, rz)
                
            if hasattr(self, 'comm_hydrophone') and self.comm_hydrophone:
                angle = getattr(self, '_docking_sonar_angle', 0)
                doa_val = (215.4 + math.sin(angle * 0.08) * 3.0) % 360
                level_val = -72 + int(math.sin(angle * 0.12) * 2)
                self.comm_hydrophone.update_audio(24.6, level_val, doa_val, "LISTENING")
                
                if hasattr(self, 'lbl_comm_hydro_pf'):
                    self.lbl_comm_hydro_pf.setText("24.6 kHz")
                if hasattr(self, 'lbl_comm_hydro_sl'):
                    self.lbl_comm_hydro_sl.setText(f"{level_val} dB")
                if hasattr(self, 'lbl_comm_hydro_doa'):
                    self.lbl_comm_hydro_doa.setText(f"{doa_val:.1f}°")
                    
            if hasattr(self, 'tbl_packet_monitor') and self.tbl_packet_monitor:
                from PySide6.QtCore import QDateTime
                from PySide6.QtGui import QColor
                from PySide6.QtWidgets import QTableWidgetItem
                import random
                
                if random.random() < 0.15:
                    t_str = QDateTime.currentDateTime().toString("hh:mm:ss.zzz")
                    is_rx = random.choice([True, False])
                    dir_str = "↓ RX" if is_rx else "↑ TX"
                    pkt_type = random.choice(["TELEMETRY", "COMMAND", "ACK", "STATUS"])
                    pkt_sz = str(random.choice([32, 48, 64, 128]))
                    seq_val = str(random.randint(45000, 46000) if is_rx else random.randint(22000, 23000))
                    
                    self.tbl_packet_monitor.insertRow(0)
                    
                    t_item = QTableWidgetItem(t_str)
                    d_item = QTableWidgetItem(dir_str)
                    y_item = QTableWidgetItem(pkt_type)
                    z_item = QTableWidgetItem(pkt_sz)
                    q_item = QTableWidgetItem(seq_val)
                    s_item = QTableWidgetItem("OK")
                    
                    if is_rx:
                        d_item.setForeground(QColor(0, 230, 118))
                    else:
                        d_item.setForeground(QColor(33, 150, 243))
                    s_item.setForeground(QColor(0, 230, 118))
                    
                    self.tbl_packet_monitor.setItem(0, 0, t_item)
                    self.tbl_packet_monitor.setItem(0, 1, d_item)
                    self.tbl_packet_monitor.setItem(0, 2, y_item)
                    self.tbl_packet_monitor.setItem(0, 3, z_item)
                    self.tbl_packet_monitor.setItem(0, 4, q_item)
                    self.tbl_packet_monitor.setItem(0, 5, s_item)
                    
                    if self.tbl_packet_monitor.rowCount() > 50:
                        self.tbl_packet_monitor.setRowCount(50)
                
        # Update Depth Page Widgets
        if current_page == 6:
            if hasattr(self, 'depth_gauge'):
                self.depth_gauge.set_values(data['distance'], max(0.2, 15.0 - data['distance']))
            if hasattr(self, 'pressure_gauge'):
                self.pressure_gauge.set_value(data['distance'] * 0.1)
            if hasattr(self, 'dvl_vx_card'):
                angle = getattr(self, '_docking_sonar_angle', 0)
                vx_val = math.sin(angle * 0.08) * 0.3
                self.dvl_vx_card.set_value(f"{vx_val:+.2f}")
            if hasattr(self, 'dvl_vy_card'):
                angle = getattr(self, '_docking_sonar_angle', 0)
                vy_val = math.cos(angle * 0.08) * 0.2
                self.dvl_vy_card.set_value(f"{vy_val:+.2f}")
            if hasattr(self, 'dvl_lock_card'):
                self.dvl_lock_card.set_value("BOTTOM LOCKED" if data['confidence'] > 40 else "NO LOCK")
            if hasattr(self, 'dvl_vector'):
                angle = getattr(self, '_docking_sonar_angle', 0)
                vx_val = math.sin(angle * 0.08) * 0.3
                vy_val = math.cos(angle * 0.08) * 0.2
                self.dvl_vector.set_velocities(vx_val, vy_val)
            if hasattr(self, 'depth_chart'):
                self.depth_chart.append_data([data['distance']])
                
            # Update extra depth widgets
            if hasattr(self, 'depth_altimeter') and self.depth_altimeter:
                self.depth_altimeter.update_altimeter(data['distance'], 92.0)
                
            # Extract MS5837 sensor readings (or fall back to simulated values)
            press_bar = data.get('ms5837_press')
            water_temp = data.get('ms5837_temp')
            depth_val = data.get('ms5837_depth')
            
            if press_bar is None:
                press_bar = 1.013 + (15.0 - data['distance']) * 0.1
            if water_temp is None:
                water_temp = 22.6 + math.sin(self._docking_sonar_angle * 0.05) * 0.2
            if depth_val is None:
                depth_val = max(0.0, (15.0 - data['distance']))
    
            if hasattr(self, 'depth_pressure') and self.depth_pressure:
                self.depth_pressure.update_pressure(press_bar, water_temp)
                
            if hasattr(self, 'depth_dvl_widget') and self.depth_dvl_widget:
                angle = getattr(self, '_docking_sonar_angle', 0)
                vx_val = math.sin(angle * 0.08) * 0.12
                vy_val = math.cos(angle * 0.08) * -0.08
                vz_val = -0.03 + math.sin(angle * 0.15) * 0.01
                locked = data['confidence'] > 40
                dvl_depth = 15.0 - data['distance'] - 0.06
                self.depth_dvl_widget.update_dvl(dvl_depth, locked, 95.0, vx_val, vy_val, vz_val)
                
            if hasattr(self, 'depth_profile_chart') and self.depth_profile_chart:
                dp_press = depth_val
                dp_dvl = 15.0 - data['distance'] - 0.06
                self.depth_profile_chart.add_data(dp_press, dp_dvl)
                
            if hasattr(self, 'depth_water_column') and self.depth_water_column:
                altitude = data['distance']
                self.depth_water_column.update_depth(altitude, depth_val)
                
            if hasattr(self, 'depth_quality_indicators') and self.depth_quality_indicators:
                alt_q = 92.0 + math.sin(self._docking_sonar_angle * 0.15) * 1
                press_q = 96.0
                dvl_q = 95.0 if data['confidence'] > 40 else 20.0
                self.depth_quality_indicators.update_quality(alt_q, press_q, dvl_q)
                
            # Update text labels
            if hasattr(self, 'lbl_depth_altimeter_val') and self.lbl_depth_altimeter_val:
                self.lbl_depth_altimeter_val.setText(f"{data['distance']:.2f} m")
            if hasattr(self, 'lbl_depth_altimeter_conf') and self.lbl_depth_altimeter_conf:
                self.lbl_depth_altimeter_conf.setText(f"{int(92.0 + math.sin(self._docking_sonar_angle * 0.15) * 1):d} %")
                
            if hasattr(self, 'lbl_depth_pressure_val') and self.lbl_depth_pressure_val:
                self.lbl_depth_pressure_val.setText(f"{press_bar:.3f} bar")
            if hasattr(self, 'lbl_depth_from_pressure') and self.lbl_depth_from_pressure:
                self.lbl_depth_from_pressure.setText(f"{depth_val:.2f} m")
            if hasattr(self, 'lbl_depth_water_temp') and self.lbl_depth_water_temp:
                self.lbl_depth_water_temp.setText(f"{water_temp:.1f} °C")
            if hasattr(self, 'lbl_depth_chamber_temp') and self.lbl_depth_chamber_temp:
                self.lbl_depth_chamber_temp.setText(f"{data.get('chamber_temp', 0.0):.1f} °C")
                
            # Update raw sidebar
            if hasattr(self, 'lbl_raw_depth_alt_val') and self.lbl_raw_depth_alt_val:
                self.lbl_raw_depth_alt_val.setText(f"{data['distance']:.2f}")
            if hasattr(self, 'lbl_raw_depth_alt_conf') and self.lbl_raw_depth_alt_conf:
                self.lbl_raw_depth_alt_conf.setText(f"{int(92.0 + math.sin(self._docking_sonar_angle * 0.15) * 1):d}")
                
            if hasattr(self, 'lbl_raw_depth_press_bar') and self.lbl_raw_depth_press_bar:
                self.lbl_raw_depth_press_bar.setText(f"{press_bar:.3f}")
            if hasattr(self, 'lbl_raw_depth_press_kpa') and self.lbl_raw_depth_press_kpa:
                press_kpa = press_bar * 100.0
                self.lbl_raw_depth_press_kpa.setText(f"{press_kpa:.1f}")
            if hasattr(self, 'lbl_raw_depth_press_depth') and self.lbl_raw_depth_press_depth:
                self.lbl_raw_depth_press_depth.setText(f"{depth_val:.2f}")
            if hasattr(self, 'lbl_raw_depth_press_temp') and self.lbl_raw_depth_press_temp:
                self.lbl_raw_depth_press_temp.setText(f"{water_temp:.1f}")
            if hasattr(self, 'lbl_raw_depth_chamber_temp') and self.lbl_raw_depth_chamber_temp:
                self.lbl_raw_depth_chamber_temp.setText(f"{data.get('chamber_temp', 0.0):.1f}")
                
            if hasattr(self, 'lbl_raw_depth_dvl_val') and self.lbl_raw_depth_dvl_val:
                dvl_depth = 15.0 - data['distance'] - 0.06
                self.lbl_raw_depth_dvl_val.setText(f"{dvl_depth:.2f}")
            if hasattr(self, 'lbl_raw_depth_dvl_vx') and self.lbl_raw_depth_dvl_vx:
                angle = getattr(self, '_docking_sonar_angle', 0)
                vx_val = math.sin(angle * 0.08) * 0.12
                self.lbl_raw_depth_dvl_vx.setText(f"{vx_val:+.2f}")
            if hasattr(self, 'lbl_raw_depth_dvl_vy') and self.lbl_raw_depth_dvl_vy:
                angle = getattr(self, '_docking_sonar_angle', 0)
                vy_val = math.cos(angle * 0.08) * -0.08
                self.lbl_raw_depth_dvl_vy.setText(f"{vy_val:+.2f}")
            if hasattr(self, 'lbl_raw_depth_dvl_vz') and self.lbl_raw_depth_dvl_vz:
                angle = getattr(self, '_docking_sonar_angle', 0)
                vz_val = -0.03 + math.sin(angle * 0.15) * 0.01
                self.lbl_raw_depth_dvl_vz.setText(f"{vz_val:+.2f}")
            if hasattr(self, 'lbl_raw_depth_dvl_lock') and self.lbl_raw_depth_dvl_lock:
                self.lbl_raw_depth_dvl_lock.setText("LOCKED" if data['confidence'] > 40 else "LOST")
                self.lbl_raw_depth_dvl_lock.setStyleSheet("color: #00E676; font-size: 9px; font-weight: bold;" if data['confidence'] > 40 else "color: #FF1744; font-size: 9px; font-weight: bold;")
                
            # Update DVL readouts
            if hasattr(self, 'lbl_depth_dvl_depth') and self.lbl_depth_dvl_depth:
                dvl_depth = 15.0 - data['distance'] - 0.06
                self.lbl_depth_dvl_depth.setText(f"{dvl_depth:.2f} m")
            if hasattr(self, 'lbl_depth_dvl_lock') and self.lbl_depth_dvl_lock:
                self.lbl_depth_dvl_lock.setText("LOCKED" if data['confidence'] > 40 else "LOST")
                self.lbl_depth_dvl_lock.setStyleSheet("color: #00E676; font-family: 'Google Sans', monospace; font-size: 12px; font-weight: bold;" if data['confidence'] > 40 else "color: #FF1744; font-family: 'Google Sans', monospace; font-size: 12px; font-weight: bold;")
            if hasattr(self, 'lbl_depth_dvl_qual') and self.lbl_depth_dvl_qual:
                self.lbl_depth_dvl_qual.setText("95 %" if data['confidence'] > 40 else "20 %")
                self.lbl_depth_dvl_qual.setStyleSheet("color: #00E676; font-family: 'Google Sans', monospace; font-size: 12px; font-weight: bold;" if data['confidence'] > 40 else "color: #FF1744; font-family: 'Google Sans', monospace; font-size: 12px; font-weight: bold;")
                
            # Update Depth checklist dots and values when connection is active
            if hasattr(self, 'lbl_depth_status_alt_dot') and self.lbl_depth_status_alt_dot:
                self.lbl_depth_status_alt_dot.setText("✔")
                self.lbl_depth_status_alt_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_depth_status_alt_val') and self.lbl_depth_status_alt_val:
                self.lbl_depth_status_alt_val.setText("ACTIVE")
                self.lbl_depth_status_alt_val.setStyleSheet("color: #00E676; font-size: 9.5px; font-weight: bold;")
                
            if hasattr(self, 'lbl_depth_status_press_dot') and self.lbl_depth_status_press_dot:
                self.lbl_depth_status_press_dot.setText("✔")
                self.lbl_depth_status_press_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_depth_status_press_val') and self.lbl_depth_status_press_val:
                self.lbl_depth_status_press_val.setText("ACTIVE")
                self.lbl_depth_status_press_val.setStyleSheet("color: #00E676; font-size: 9.5px; font-weight: bold;")
                
            if hasattr(self, 'lbl_depth_status_dvl_dot') and self.lbl_depth_status_dvl_dot:
                self.lbl_depth_status_dvl_dot.setText("✔")
                self.lbl_depth_status_dvl_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_depth_status_dvl_val') and self.lbl_depth_status_dvl_val:
                self.lbl_depth_status_dvl_val.setText("ACTIVE")
                self.lbl_depth_status_dvl_val.setStyleSheet("color: #00E676; font-size: 9.5px; font-weight: bold;")
                
            if hasattr(self, 'lbl_depth_status_lock_dot') and self.lbl_depth_status_lock_dot:
                self.lbl_depth_status_lock_dot.setText("✔" if data['confidence'] > 40 else "●")
                self.lbl_depth_status_lock_dot.setStyleSheet("color: #00E676; font-size: 11px; font-weight: bold;" if data['confidence'] > 40 else "color: #FF1744; font-size: 11px; font-weight: bold;")
            if hasattr(self, 'lbl_depth_status_lock_val') and self.lbl_depth_status_lock_val:
                self.lbl_depth_status_lock_val.setText("LOCKED" if data['confidence'] > 40 else "LOST")
                self.lbl_depth_status_lock_val.setStyleSheet("color: #00E676; font-size: 9.5px; font-weight: bold;" if data['confidence'] > 40 else "color: #FF1744; font-size: 9.5px; font-weight: bold;")
                
            if hasattr(self, 'lbl_depth_status_quality') and self.lbl_depth_status_quality:
                self.lbl_depth_status_quality.setText("GOOD" if data['confidence'] > 40 else "POOR")
                self.lbl_depth_status_quality.setStyleSheet("color: #00E676; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;" if data['confidence'] > 40 else "color: #FF1744; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
            if hasattr(self, 'lbl_depth_status_acc') and self.lbl_depth_status_acc:
                self.lbl_depth_status_acc.setText("0.18 m")
                self.lbl_depth_status_acc.setStyleSheet("color: #00E676; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
            if hasattr(self, 'lbl_depth_status_conf') and self.lbl_depth_status_conf:
                conf_val = int(92.0 + math.sin(self._docking_sonar_angle * 0.15) * 1)
                self.lbl_depth_status_conf.setText(f"{conf_val} %")
                self.lbl_depth_status_conf.setStyleSheet("color: #00E676; font-family: 'Google Sans', monospace; font-size: 9.5px; font-weight: bold;")
    
            # Populate static mock tables with values only when active
            if hasattr(self, 'tbl_hydro_detections') and self.tbl_hydro_detections:
                if self.tbl_hydro_detections.rowCount() == 0:
                    det_mock_rows = [
                        ("12:25:30.125", "24.6", "-72", "215.4", "ROV"),
                        ("12:25:29.821", "18.3", "-81", "198.7", "UNKNOWN"),
                        ("12:25:29.412", "32.1", "-65", "228.9", "PING"),
                        ("12:25:28.993", "12.7", "-88", "204.1", "UNKNOWN"),
                        ("12:25:28.562", "25.4", "-70", "216.2", "ROV"),
                        ("12:25:28.145", "40.2", "-63", "231.6", "PING")
                    ]
                    self.tbl_hydro_detections.setRowCount(len(det_mock_rows))
                    for r_idx, (t_stamp, freq, lvl, doa, cls) in enumerate(det_mock_rows):
                        t_item = QTableWidgetItem(t_stamp)
                        f_item = QTableWidgetItem(freq)
                        l_item = QTableWidgetItem(lvl)
                        d_item = QTableWidgetItem(doa)
                        c_item = QTableWidgetItem(cls)
                        if cls == "ROV":
                            c_item.setForeground(QColor(0, 230, 118))
                        elif cls == "PING":
                            c_item.setForeground(QColor(0, 229, 255))
                        else:
                            c_item.setForeground(QColor(255, 179, 0))
                        self.tbl_hydro_detections.setItem(r_idx, 0, t_item)
                        self.tbl_hydro_detections.setItem(r_idx, 1, f_item)
                        self.tbl_hydro_detections.setItem(r_idx, 2, l_item)
                        self.tbl_hydro_detections.setItem(r_idx, 3, d_item)
                        self.tbl_hydro_detections.setItem(r_idx, 4, c_item)
    
            if hasattr(self, 'tbl_depth_logs') and self.tbl_depth_logs:
                if self.tbl_depth_logs.rowCount() == 0:
                    depth_mock_logs = [
                        ("12:25:12.145", "INFO", "ALTIMETER", "Altitude: 2.12 m | Confidence: 92%"),
                        ("12:25:12.287", "INFO", "PRESSURE", "Pressure: 1.022 bar | Depth: 10.21 m | Temp: 22.6 °C"),
                        ("12:25:14.362", "INFO", "DVL", "Bottom lock acquired")
                    ]
                    self.tbl_depth_logs.setRowCount(len(depth_mock_logs))
                    for r_idx, (t_stamp, lvl, src, msg) in enumerate(depth_mock_logs):
                        t_item = QTableWidgetItem(t_stamp)
                        l_item = QTableWidgetItem(lvl)
                        s_item = QTableWidgetItem(src)
                        m_item = QTableWidgetItem(msg)
                        l_item.setForeground(QColor(0, 230, 118))
                        s_item.setForeground(QColor(0, 229, 255))
                        self.tbl_depth_logs.setItem(r_idx, 0, t_item)
                        self.tbl_depth_logs.setItem(r_idx, 1, l_item)
                        self.tbl_depth_logs.setItem(r_idx, 2, s_item)
                        self.tbl_depth_logs.setItem(r_idx, 3, m_item)

        if current_page in [6, 7, 8, 9]:
            if hasattr(self, 'tbl_docking_logs') and self.tbl_docking_logs:
                if self.tbl_docking_logs.rowCount() == 0:
                    docking_mock_logs = [
                        ("12:25:01.442", "INFO", "SONAR", "Sonar scanning active | Range: 12.4m"),
                        ("12:25:02.115", "INFO", "MAG", "Magnetic vector locked"),
                        ("12:25:03.955", "INFO", "VISION", "Docking target detected in frame")
                    ]
                    self.tbl_docking_logs.setRowCount(len(docking_mock_logs))
                    for r_idx, (t_stamp, lvl, src, msg) in enumerate(docking_mock_logs):
                        t_item = QTableWidgetItem(t_stamp)
                        l_item = QTableWidgetItem(lvl)
                        s_item = QTableWidgetItem(src)
                        m_item = QTableWidgetItem(msg)
                        l_item.setForeground(QColor(0, 230, 118))
                        s_item.setForeground(QColor(0, 229, 255))
                        self.tbl_docking_logs.setItem(r_idx, 0, t_item)
                        self.tbl_docking_logs.setItem(r_idx, 1, l_item)
                        self.tbl_docking_logs.setItem(r_idx, 2, s_item)
                        self.tbl_docking_logs.setItem(r_idx, 3, m_item)

        # Update map coordinates via Javascript - neglect if lat/lon is exactly or close to 0.0 (GPS signal loss)
        if abs(data['latitude']) > 0.0001 or abs(data['longitude']) > 0.0001:
            if current_page == 1 and hasattr(self, 'web_view') and self.web_view:
                self.web_view.page().runJavaScript(f"updatePosition({data['latitude']}, {data['longitude']}, {visual_yaw});")
            elif current_page == 2 and hasattr(self, 'plan_web_view') and self.plan_web_view:
                self.plan_web_view.page().runJavaScript(f"updatePosition({data['latitude']}, {data['longitude']}, {visual_yaw});")
            
        # Update map overlay instruments if they exist
        if current_page in [1, 2]:
            if hasattr(self, 'map_compass') and self.map_compass:
                self.map_compass.set_yaw(visual_yaw)
            if hasattr(self, 'map_horizon') and self.map_horizon:
                self.map_horizon.set_attitude(data['roll'], data['pitch'])
            if hasattr(self, 'plan_map_compass') and self.plan_map_compass:
                self.plan_map_compass.set_yaw(visual_yaw)
            if hasattr(self, 'plan_map_horizon') and self.plan_map_horizon:
                self.plan_map_horizon.set_attitude(data['roll'], data['pitch'])

        # Check waypoint proximity if mission is active
        if self.mission_active and self.planned_waypoints:
            # Update vehicle speed calculation
            import time
            now_time = time.time()
            if getattr(self, 'last_lat', None) is not None and getattr(self, 'last_lon', None) is not None and getattr(self, 'last_time', None) is not None:
                dt = now_time - self.last_time
                if dt > 0.1:
                    ds = self.haversine_distance(self.last_lat, self.last_lon, data['latitude'], data['longitude'])
                    calc_speed = ds / dt
                    if calc_speed < 10.0: # filter anomalies
                        self.current_speed = 0.8 * self.current_speed + 0.2 * calc_speed
            self.last_lat = data['latitude']
            self.last_lon = data['longitude']
            self.last_time = now_time

            if self.current_wp_idx < len(self.planned_waypoints):
                target_lat, target_lon = self.planned_waypoints[self.current_wp_idx]
                dist = self.haversine_distance(data['latitude'], data['longitude'], target_lat, target_lon)
                
                # Update Mission Profiler Readouts
                wp_label = "HOME" if self.current_wp_idx == 0 else f"WP {self.current_wp_idx}"
                if hasattr(self, 'lbl_profiler_target'):
                    self.lbl_profiler_target.setText(wp_label)
                if hasattr(self, 'lbl_profiler_dist'):
                    self.lbl_profiler_dist.setText(f"{dist:.1f} m")
                
                # Calculate ETA (based on self.current_speed)
                if hasattr(self, 'lbl_profiler_eta'):
                    if self.current_speed > 0.1:
                        eta_sec = dist / self.current_speed
                        if eta_sec < 60.0:
                            self.lbl_profiler_eta.setText(f"{int(eta_sec)} s")
                        else:
                            self.lbl_profiler_eta.setText(f"{int(eta_sec // 60)}m {int(eta_sec % 60)}s")
                    else:
                        self.lbl_profiler_eta.setText("-- (STATIONARY)")
                        
                # Calculate Remaining Route Distance
                if hasattr(self, 'lbl_profiler_route'):
                    route_rem = self.calculate_remaining_route_distance(data['latitude'], data['longitude'])
                    self.lbl_profiler_route.setText(f"{route_rem:.1f} m")

                # Multi-Waypoint Proximity Scanning Check
                # Scan all upcoming waypoints from current_wp_idx forward
                reached_idx = -1
                for check_idx in range(self.current_wp_idx, len(self.planned_waypoints)):
                    wp_lat, wp_lon = self.planned_waypoints[check_idx]
                    d = self.haversine_distance(data['latitude'], data['longitude'], wp_lat, wp_lon)
                    if d < self.wp_reach_threshold:
                        reached_idx = check_idx
                
                if reached_idx >= 0:
                    for mark_idx in range(self.current_wp_idx, reached_idx + 1):
                        wp_label = "HOME" if mark_idx == 0 else f"WP {mark_idx}"
                        print(f"[Mission Control] Reached waypoint: {wp_label} (Index {mark_idx})")
                        
                        # Update bottom drawer table item status
                        if hasattr(self, 'wp_table') and self.wp_table and mark_idx < self.wp_table.rowCount():
                            status_item = self.wp_table.item(mark_idx, 4)
                            if status_item:
                                status_item.setText("REACHED")
                                status_item.setForeground(QColor("#00E676")) # bright neon green
                                status_item.setFont(QFont("Google Sans", 9, QFont.Bold))
                                
                        # Update Leaflet map marker style to green via runJavaScript
                        if hasattr(self, 'plan_web_view') and self.plan_web_view:
                            self.plan_web_view.page().runJavaScript(f"reachWaypoint({mark_idx});")
                            
                    self.current_wp_idx = reached_idx + 1
                    
                    if self.current_wp_idx >= len(self.planned_waypoints):
                        print("[Mission Control] Autonomous mission completed successfully.")
                        self.stop_mission()
        else:
            # Reset speed state
            self.last_lat = None
            self.last_lon = None
            self.last_time = None
            self.current_speed = 0.0
            
            # Reset profiler labels
            if hasattr(self, 'lbl_profiler_target'):
                self.lbl_profiler_target.setText("--")
            if hasattr(self, 'lbl_profiler_dist'):
                self.lbl_profiler_dist.setText("--")
            if hasattr(self, 'lbl_profiler_eta'):
                self.lbl_profiler_eta.setText("--")
            if hasattr(self, 'lbl_profiler_route'):
                self.lbl_profiler_route.setText("--")

    def calculate_remaining_route_distance(self, current_lat, current_lon):
        if not self.planned_waypoints or self.current_wp_idx >= len(self.planned_waypoints):
            return 0.0
            
        # Distance from vehicle to active waypoint
        active_wp = self.planned_waypoints[self.current_wp_idx]
        total_dist = self.haversine_distance(current_lat, current_lon, active_wp[0], active_wp[1])
        
        # Sum of segments from active waypoint to subsequent ones
        for idx in range(self.current_wp_idx, len(self.planned_waypoints) - 1):
            wp1 = self.planned_waypoints[idx]
            wp2 = self.planned_waypoints[idx + 1]
            total_dist += self.haversine_distance(wp1[0], wp1[1], wp2[0], wp2[1])
            
        return total_dist

    @Slot(bool, str)
    def on_connection_status_changed(self, is_connected, message):
        # Thread reported connection closed/error
        if not is_connected:
            self.watchdog_timer.stop()
            self.log_file_path = None
            self.top_bar.set_connection_status("disconnected", message)
            for card in self.cards.values():
                card.set_status("disconnected")
            self.port_refresh_timer.start(3000)
            self.clear_telemetry_data()
        else:
            # Port opened, but wait for first valid format message before showing Connected
            if self.top_bar.status_state != "connected":
                self.top_bar.set_connection_status("connecting", "Waiting Data")
                for card in self.cards.values():
                    card.set_status("connecting")
            
            # Automatically synchronize saved speed limits with the backend on connect
            if self.telemetry_thread and self.telemetry_thread.isRunning():
                payload = f"$LIMIT,{self.thruster_min_limit},{self.thruster_max_limit}"
                self.telemetry_thread.write_data(payload)
                print(f"[Mission Control] Synced speed limits on connect: {payload}")

    @Slot()
    def on_data_timeout(self):
        # Watchdog timeout: no valid telemetry parsed in 2 seconds
        # Drop UI state back to amber "NO DATA"
        self.top_bar.set_connection_status("connecting", "NO DATA")
        for card in self.cards.values():
            card.set_status("connecting")
        self.clear_telemetry_data()

    def set_navigation_mode(self, mode):
        if mode == "manual":
            self.btn_manual.setChecked(True)
            self.btn_manual.setProperty("checked", "true")
            self.btn_auto.setChecked(False)
            self.btn_auto.setProperty("checked", "false")
            self.auto_actions_widget.setVisible(False)
            self.manual_actions_widget.setVisible(True)
            self.bottom_panel.setVisible(False)
            if hasattr(self, 'eta_panel') and self.eta_panel:
                self.eta_panel.setVisible(False)
            if hasattr(self, 'txt_mission_logs') and self.txt_mission_logs:
                self.txt_mission_logs.setVisible(False)
            if hasattr(self, 'plan_web_view'):
                self.plan_web_view.page().runJavaScript("setPlanningMode(false);")
            print("[Navigation Mode] Switched to MANUAL. Waypoints disabled.")
            self.log_mission("Navigation Mode switched to MANUAL.")
        else:
            self.btn_manual.setChecked(False)
            self.btn_manual.setProperty("checked", "false")
            self.btn_auto.setChecked(True)
            self.btn_auto.setProperty("checked", "true")
            self.auto_actions_widget.setVisible(True)
            self.manual_actions_widget.setVisible(False)
            self.bottom_panel.setVisible(True)
            if hasattr(self, 'eta_panel') and self.eta_panel:
                self.eta_panel.setVisible(True)
            if hasattr(self, 'txt_mission_logs') and self.txt_mission_logs:
                self.txt_mission_logs.setVisible(True)
            if hasattr(self, 'plan_splitter'):
                height = self.height()
                self.plan_splitter.setSizes([height - 200, 180])
            if hasattr(self, 'plan_web_view'):
                self.plan_web_view.page().runJavaScript("setPlanningMode(true);")
            print("[Navigation Mode] Switched to AUTOMATIC. Click map to add waypoints.")
            self.log_mission("Navigation Mode switched to AUTOMATIC.")
            
            # Disable ARM button unless waypoints have been uploaded & acknowledged
            self.btn_arm.setEnabled(self.wp_upload_acknowledged)
            
        # Reset running states when switching modes
        self.manual_running = False
        self.mission_active = False
        
        inactive_btn_style = """
            QPushButton {
                background-color: #0F223C;
                border: 1px solid #1C3B65;
                border-radius: 4px;
                padding: 8px 12px;
                color: #E2F1FF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1C3B65;
                border-color: #2D5A8F;
                color: #FFFFFF;
            }
        """
        if hasattr(self, 'btn_start'):
            self.btn_start.setStyleSheet(inactive_btn_style)
        if hasattr(self, 'btn_stop'):
            self.btn_stop.setStyleSheet(inactive_btn_style)
        if hasattr(self, 'btn_manual_start'):
            self.btn_manual_start.setStyleSheet(inactive_btn_style)
        if hasattr(self, 'btn_manual_stop'):
            self.btn_manual_stop.setStyleSheet(inactive_btn_style)

        # Reset configuration mode if active
        if getattr(self, 'is_configuration_mode', False):
            self.is_configuration_mode = False
            if hasattr(self, 'btn_config_mode_toggle') and self.btn_config_mode_toggle is not None:
                self.btn_config_mode_toggle.setChecked(False)
                self.btn_config_mode_toggle.setText("CONFIGURATION: OFF")
                self.btn_config_mode_toggle.setStyleSheet("""
                    QPushButton {
                        background-color: #2D2D2D;
                        border: 1px solid #444444;
                        border-radius: 3px;
                        color: #CCCCCC;
                        font-weight: bold;
                        font-size: 11px;
                        padding: 8px 18px;
                    }
                    QPushButton:hover {
                        background-color: #383838;
                        color: #FFFFFF;
                    }
                """)
            if hasattr(self, 'btn_send_pid') and self.btn_send_pid is not None:
                self.btn_send_pid.setEnabled(False)

        # Re-apply styles
        self.btn_manual.style().unpolish(self.btn_manual)
        self.btn_manual.style().polish(self.btn_manual)
        self.btn_auto.style().unpolish(self.btn_auto)
        self.btn_auto.style().polish(self.btn_auto)
        
        self.send_command_packet()

    def clear_planned_route(self):
        if hasattr(self, 'plan_web_view'):
            self.plan_web_view.page().runJavaScript("clearWaypoints();")
        print("[Waypoint Planner] Cleared waypoints from map.")

    def load_mission_file(self):
        from PySide6.QtWidgets import QFileDialog
        import json
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Mission File",
            "",
            "Mission Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    waypoints = json.load(f)
                if not isinstance(waypoints, list):
                    print("[Mission Load Error] Invalid mission format: expected list of coordinates.")
                    return
                
                # Clear existing route first
                if hasattr(self, 'plan_web_view'):
                    self.plan_web_view.page().runJavaScript("clearWaypoints();")
                
                self.planned_waypoints = []
                self.refresh_waypoints_table()
                
                # Plot each loaded waypoint on the Leaflet map
                if hasattr(self, 'plan_web_view'):
                    for pt in waypoints:
                        if isinstance(pt, list) and len(pt) >= 2:
                            lat, lon = pt[0], pt[1]
                            self.plan_web_view.page().runJavaScript(f"addWaypoint({lat:.6f}, {lon:.6f});")
                            
                print(f"[Mission Load] Mission loaded from: {file_path}")
            except Exception as e:
                print(f"[Mission Load Error] {e}")

    def save_mission_file(self):
        if not self.planned_waypoints:
            print("[Mission Save] No waypoints to save.")
            return
            
        from PySide6.QtWidgets import QFileDialog
        import json
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Mission File",
            "",
            "Mission Files (*.json);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.planned_waypoints, f, indent=4)
                print(f"[Mission Save] Mission successfully saved to: {file_path}")
            except Exception as e:
                print(f"[Mission Save Error] {e}")

    def upload_planned_route(self):
        if not self.planned_waypoints:
            self.log_mission("Error: No waypoints to upload!")
            return
            
        self.wp_upload_acknowledged = True
        self.btn_arm.setEnabled(True)
        self.log_mission(f"Uploading {len(self.planned_waypoints)} waypoints to vessel...")
        
        self.send_command_packet()
            
        self.log_mission("Waypoint upload finished.")
        print("[Waypoint Planner] Upload complete.")

    def handle_plan_console(self, message):
        if "[Waypoint] Added:" in message:
            try:
                coord_str = message.split("[Waypoint] Added:")[1].strip()
                lat_str, lon_str = coord_str.split(",")
                lat = float(lat_str)
                lon = float(lon_str)
                self.planned_waypoints.append((lat, lon))
                self.refresh_waypoints_table()
            except Exception as e:
                print(f"Error parsing waypoint: {e}")
        elif "[Waypoint] Cleared" in message:
            self.planned_waypoints = []
            self.refresh_waypoints_table()
        elif "[Waypoint] Moved:" in message:
            try:
                data_str = message.split("[Waypoint] Moved:")[1].strip()
                idx_str, lat_str, lon_str = data_str.split(",")
                idx = int(idx_str)
                lat = float(lat_str)
                lon = float(lon_str)
                if 0 <= idx < len(self.planned_waypoints):
                    self.planned_waypoints[idx] = (lat, lon)
                    self.refresh_waypoints_table()
            except Exception as e:
                print(f"Error handling moved waypoint: {e}")
        elif "[Waypoint] Inserted:" in message:
            try:
                data_str = message.split("[Waypoint] Inserted:")[1].strip()
                idx_str, lat_str, lon_str = data_str.split(",")
                idx = int(idx_str)
                lat = float(lat_str)
                lon = float(lon_str)
                self.planned_waypoints.insert(idx, (lat, lon))
                self.refresh_waypoints_table()
            except Exception as e:
                print(f"Error handling inserted waypoint: {e}")

    def refresh_waypoints_table(self):
        self.wp_table.setRowCount(0)
        n = len(self.planned_waypoints)
        for i in range(n):
            lat, lon = self.planned_waypoints[i]
            
            # Distance (m): segment from previous to current
            if i == 0:
                dist_str = "--"
            else:
                prev_lat, prev_lon = self.planned_waypoints[i - 1]
                dist = self.haversine_distance(prev_lat, prev_lon, lat, lon)
                dist_str = f"{dist:.1f}"
                
            # Offset (Bearing):
            if i == 0:
                if n > 1:
                    next_lat, next_lon = self.planned_waypoints[1]
                    bearing = self.calculate_bearing(lat, lon, next_lat, next_lon)
                    offset_str = f"{bearing:.1f} deg"
                else:
                    offset_str = "--"
            else:
                prev_lat, prev_lon = self.planned_waypoints[i - 1]
                bearing = self.calculate_bearing(prev_lat, prev_lon, lat, lon)
                offset_str = f"{bearing:.1f} deg"
                
            self.wp_table.insertRow(i)
            
            # 1. WP
            wp_name = "HOME" if i == 0 else f"WP {i}"
            item_name = QTableWidgetItem(wp_name)
            item_name.setFont(QFont("Google Sans", 9, QFont.Bold))
            self.wp_table.setItem(i, 0, item_name)
            
            # 2. LATITUDE
            self.wp_table.setItem(i, 1, QTableWidgetItem(f"{lat:.5f}"))
            
            # 3. LONGITUDE
            self.wp_table.setItem(i, 2, QTableWidgetItem(f"{lon:.5f}"))
            
            # 4. DIST (m)
            self.wp_table.setItem(i, 3, QTableWidgetItem(dist_str))
            
            # 5. STATUS
            if i < getattr(self, 'current_wp_idx', 0):
                item_status = QTableWidgetItem("REACHED")
                item_status.setForeground(QColor("#00E676")) # bright neon green
                item_status.setFont(QFont("Google Sans", 9, QFont.Bold))
            else:
                item_status = QTableWidgetItem("WAIT")
                item_status.setForeground(QColor("#A0A0A0")) # subtle gray
            self.wp_table.setItem(i, 4, item_status)
            
            # 6. DEL (✕)
            del_btn = QPushButton("✕")
            if i == 0:
                del_btn.setEnabled(False)
                del_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        color: #444444;
                        font-weight: bold;
                        font-size: 12px;
                    }
                """)
            else:
                del_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: none;
                        color: #EF5350;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        color: #FF1744;
                    }
                """)
                del_btn.clicked.connect(lambda checked=False, idx=i: self.delete_waypoint_at(idx))
            self.wp_table.setCellWidget(i, 5, del_btn)
            
            # 7. UP (▲)
            btn_up = QPushButton("▲")
            btn_up.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #A0A0A0;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #FF9100;
                }
                QPushButton:disabled {
                    color: #444444;
                }
            """)
            btn_up.setEnabled(i > 1) # HOME and WP 1 cannot move UP
            btn_up.clicked.connect(lambda checked=False, idx=i: self.move_waypoint_up(idx))
            self.wp_table.setCellWidget(i, 6, btn_up)
            
            # 8. DN (▼)
            btn_down = QPushButton("▼")
            btn_down.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    color: #A0A0A0;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    color: #FF9100;
                }
                QPushButton:disabled {
                    color: #444444;
                }
            """)
            btn_down.setEnabled(i > 0 and i < n - 1) # HOME cannot move DN, last WP cannot move DN
            btn_down.clicked.connect(lambda checked=False, idx=i: self.move_waypoint_down(idx))
            self.wp_table.setCellWidget(i, 7, btn_down)
            
            # 9. OFFSET
            self.wp_table.setItem(i, 8, QTableWidgetItem(offset_str))
            
        for r in range(self.wp_table.rowCount()):
            for c in [0, 1, 2, 3, 4, 8]:
                item = self.wp_table.item(r, c)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                    
        self.update_eta_calculations()

    def update_eta_calculations(self):
        if not hasattr(self, 'lbl_eta_dist') or self.lbl_eta_dist is None:
            return
        total_dist = 0.0
        n = len(self.planned_waypoints)
        for i in range(1, n):
            lat1, lon1 = self.planned_waypoints[i - 1]
            lat2, lon2 = self.planned_waypoints[i]
            total_dist += self.haversine_distance(lat1, lon1, lat2, lon2)
            
        self.lbl_eta_dist.setText(f"Total Distance: {total_dist:.1f} m")
        
        # Get speed value
        speed_str = self.combo_cruise_speed.currentText().split(" ")[0]
        try:
            speed = float(speed_str)
        except:
            speed = 2.0
            
        if speed > 0:
            duration_s = total_dist / speed
            if duration_s >= 60:
                mins = int(duration_s // 60)
                secs = int(duration_s % 60)
                self.lbl_eta_time.setText(f"Est. Duration: {mins}m {secs}s")
            else:
                self.lbl_eta_time.setText(f"Est. Duration: {duration_s:.1f}s")
        else:
            self.lbl_eta_time.setText("Est. Duration: --")

    def haversine_distance(self, lat1, lon1, lat2, lon2):
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        a = math.sin(delta_phi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2.0)**2
        c = 2.0*math.atan2(math.sqrt(a), math.sqrt(1.0-a))
        return R * c

    def calculate_bearing(self, lat1, lon1, lat2, lon2):
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)
        
        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
        
        bearing = math.atan2(y, x)
        bearing_deg = math.degrees(bearing)
        bearing_deg = (bearing_deg + 180) % 360 - 180
        return bearing_deg

    def delete_waypoint_at(self, idx):
        if idx < 0 or idx >= len(self.planned_waypoints):
            return
        self.planned_waypoints.pop(idx)
        if hasattr(self, 'plan_web_view'):
            self.plan_web_view.page().runJavaScript(f"deleteWaypoint({idx});")
        print(f"[Waypoint Planner] Deleted waypoint at index: {idx}")
        self.refresh_waypoints_table()

    def move_waypoint_up(self, idx):
        if idx <= 0 or idx >= len(self.planned_waypoints):
            return
        self.planned_waypoints[idx], self.planned_waypoints[idx - 1] = \
            self.planned_waypoints[idx - 1], self.planned_waypoints[idx]
        if hasattr(self, 'plan_web_view'):
            self.plan_web_view.page().runJavaScript(f"swapWaypoints({idx}, {idx - 1});")
        print(f"[Waypoint Planner] Swapped waypoint {idx} UP to {idx - 1}")
        self.refresh_waypoints_table()

    def move_waypoint_down(self, idx):
        if idx < 0 or idx >= len(self.planned_waypoints) - 1:
            return
        self.planned_waypoints[idx], self.planned_waypoints[idx + 1] = \
            self.planned_waypoints[idx + 1], self.planned_waypoints[idx]
        if hasattr(self, 'plan_web_view'):
            self.plan_web_view.page().runJavaScript(f"swapWaypoints({idx}, {idx + 1});")
        print(f"[Waypoint Planner] Swapped waypoint {idx} DOWN to {idx + 1}")
        self.refresh_waypoints_table()

    def arm_vehicle(self):
        active_style = """
            QPushButton {
                background-color: #1C3B65;
                border: 1px solid #2D5A8F;
                border-radius: 4px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2D5A8F;
                border-color: #3B72B0;
                color: #FFFFFF;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #0F223C;
                border: 1px solid #1C3B65;
                border-radius: 4px;
                padding: 8px 12px;
                color: #E2F1FF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1C3B65;
                border-color: #2D5A8F;
                color: #FFFFFF;
            }
        """
        self.btn_arm.setStyleSheet(active_style)
        self.btn_disarm.setStyleSheet(inactive_style)
        if hasattr(self, 'btn_manual_arm'):
            self.btn_manual_arm.setStyleSheet(active_style)
        if hasattr(self, 'btn_manual_disarm'):
            self.btn_manual_disarm.setStyleSheet(inactive_style)
        self.is_armed = True
        
        # Send $ARM command - retry 5 times at 150ms intervals for UDP reliability
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            print("[Mission Control] ARM button clicked - sending $ARM to Pi (x5 retries)...")
            def send_arm():
                if self.telemetry_thread and self.telemetry_thread.isRunning():
                    self.telemetry_thread.write_data("$ARM")
            send_arm()
            for delay_ms in [150, 300, 450, 600]:
                QTimer.singleShot(delay_ms, send_arm)
        else:
            print("[Mission Control WARNING] ARM clicked but telemetry thread is NOT running! Check connection.")
 
    def disarm_vehicle(self):
        active_style = """
            QPushButton {
                background-color: #1C3B65;
                border: 1px solid #2D5A8F;
                border-radius: 4px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2D5A8F;
                border-color: #3B72B0;
                color: #FFFFFF;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #0F223C;
                border: 1px solid #1C3B65;
                border-radius: 4px;
                padding: 8px 12px;
                color: #E2F1FF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1C3B65;
                border-color: #2D5A8F;
                color: #FFFFFF;
            }
        """
        self.btn_arm.setStyleSheet(inactive_style)
        self.btn_disarm.setStyleSheet(active_style)
        if hasattr(self, 'btn_manual_arm'):
            self.btn_manual_arm.setStyleSheet(inactive_style)
        if hasattr(self, 'btn_manual_disarm'):
            self.btn_manual_disarm.setStyleSheet(active_style)
            
        self.manual_running = False
        self.mission_active = False
        if hasattr(self, 'btn_start'):
            self.btn_start.setStyleSheet(inactive_style)
        if hasattr(self, 'btn_stop'):
            self.btn_stop.setStyleSheet(inactive_style)
        if hasattr(self, 'btn_manual_start'):
            self.btn_manual_start.setStyleSheet(inactive_style)
        if hasattr(self, 'btn_manual_stop'):
            self.btn_manual_stop.setStyleSheet(inactive_style)
            
        self.is_armed = False
        
        # Send $DISARM command - retry 5 times at 150ms intervals for UDP reliability
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            print("[Mission Control] DISARM button clicked - sending $DISARM to Pi (x5 retries)...")
            def send_disarm():
                if self.telemetry_thread and self.telemetry_thread.isRunning():
                    self.telemetry_thread.write_data("$DISARM")
            send_disarm()
            for delay_ms in [150, 300, 450, 600]:
                QTimer.singleShot(delay_ms, send_disarm)
        else:
            print("[Mission Control WARNING] DISARM clicked but telemetry thread is NOT running! Check connection.")

    def update_light_ui_state(self, is_checked):
        self.light_state = 1 if is_checked else 0
        buttons = []
        if hasattr(self, 'btn_light_toggle'):
            buttons.append(self.btn_light_toggle)
        if hasattr(self, 'btn_auto_light_toggle'):
            buttons.append(self.btn_auto_light_toggle)
        if hasattr(self, 'btn_manual_light_toggle'):
            buttons.append(self.btn_manual_light_toggle)
            
        for btn in buttons:
            btn.setChecked(is_checked)
            if is_checked:
                btn.setText("LIGHT: ON")
                btn.setStyleSheet("background-color: #00E676; border: 1px solid #00C853; border-radius: 4px; padding: 8px 12px; color: #121212; font-family: 'Google Sans', sans-serif; font-weight: bold; font-size: 11px;")
            else:
                btn.setText("LIGHT: OFF")
                btn.setStyleSheet(self.blue_btn_style)

    def toggle_light(self):
        sender = self.sender()
        is_checked = sender.isChecked() if sender else (self.light_state == 0)
        self.update_light_ui_state(is_checked)
        
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.light_state = self.light_state
            self.send_immediate_cmd()

    def update_camera_ui_state(self, is_checked):
        self.camera_state = 1 if is_checked else 0
        buttons = []
        if hasattr(self, 'btn_camera_toggle'):
            buttons.append(self.btn_camera_toggle)
        if hasattr(self, 'btn_auto_camera_toggle'):
            buttons.append(self.btn_auto_camera_toggle)
        if hasattr(self, 'btn_manual_camera_toggle'):
            buttons.append(self.btn_manual_camera_toggle)
            
        for btn in buttons:
            btn.setChecked(is_checked)
            if is_checked:
                btn.setText("CAMERA: ON")
                btn.setStyleSheet("background-color: #00E676; border: 1px solid #00C853; border-radius: 4px; padding: 8px 12px; color: #121212; font-family: 'Google Sans', sans-serif; font-weight: bold; font-size: 11px;")
            else:
                btn.setText("CAMERA: OFF")
                btn.setStyleSheet(self.blue_btn_style)

    def toggle_camera(self):
        sender = self.sender()
        is_checked = sender.isChecked() if sender else (self.camera_state == 0)
        self.update_camera_ui_state(is_checked)
        
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.camera_state = self.camera_state
            self.send_immediate_cmd()
            
    def send_immediate_cmd(self):
        self.send_command_packet()

    def start_mission(self):
        # --- Pre-start Autonomous Mission Safety Pre-checks ---
        # 1. Vehicle is armed
        if not getattr(self, 'is_armed', False):
            self.log_mission("Error: Cannot start route. Vehicle is disarmed! Please ARM the vehicle first.")
            self.show_toast_alert("Reject Start: Vehicle is disarmed!", is_critical=True)
            return

        # 2. At least one waypoint exists
        if not self.planned_waypoints:
            self.log_mission("Error: Cannot start route. Waypoint route list is empty!")
            self.show_toast_alert("Reject Start: No waypoints uploaded!", is_critical=True)
            return

        # 3. GPS is healthy (connected, sats >= 4, coordinates valid)
        last_sats = getattr(self, 'last_sats', 0)
        last_lat = getattr(self, 'last_lat', 0.0)
        last_lon = getattr(self, 'last_lon', 0.0)
        gps_connected = (self.top_bar.status_state == "connected")
        
        gps_ok = (gps_connected and last_sats >= 4 and last_lat != 0.0 and last_lon != 0.0)
        if not gps_ok:
            reasons = []
            if not gps_connected:
                reasons.append("datalink disconnected")
            if last_sats < 4:
                reasons.append(f"sats={last_sats} < 4")
            if last_lat == 0.0 and last_lon == 0.0:
                reasons.append("invalid coordinates")
            self.log_mission(f"Error: Cannot start route. GPS is unhealthy ({', '.join(reasons)}).")
            self.show_toast_alert("Reject Start: GPS is unhealthy!", is_critical=True)
            return

        # 4. AHRS is healthy (connected and receiving telemetry)
        ahrs_ok = (gps_connected and hasattr(self, 'watchdog_timer') and self.watchdog_timer.isActive())
        if not ahrs_ok:
            self.log_mission("Error: Cannot start route. AHRS heading sensor is unhealthy/disconnected.")
            self.show_toast_alert("Reject Start: AHRS is unhealthy!", is_critical=True)
            return

        active_style = """
            QPushButton {
                background-color: #1C3B65;
                border: 1px solid #2D5A8F;
                border-radius: 4px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2D5A8F;
                border-color: #3B72B0;
                color: #FFFFFF;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #0F223C;
                border: 1px solid #1C3B65;
                border-radius: 4px;
                padding: 8px 12px;
                color: #E2F1FF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1C3B65;
                border-color: #2D5A8F;
                color: #FFFFFF;
            }
        """
        self.btn_start.setStyleSheet(active_style)
        self.btn_stop.setStyleSheet(inactive_style)
        self.mission_active = True
        self.current_wp_idx = 0
        if hasattr(self, 'plan_web_view') and self.plan_web_view:
            self.plan_web_view.page().runJavaScript("resetWaypointStatus();")
        self.refresh_waypoints_table()
        self.send_command_packet()
        print("[Mission Control] Autonomous waypoint route execution STARTED.")
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            if hasattr(self.telemetry_thread, 'set_waypoints'):
                self.telemetry_thread.set_waypoints(self.planned_waypoints)
            if hasattr(self.telemetry_thread, 'start_mission'):
                self.telemetry_thread.start_mission()

    def stop_mission(self):
        active_style = """
            QPushButton {
                background-color: #1C3B65;
                border: 1px solid #2D5A8F;
                border-radius: 4px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2D5A8F;
                border-color: #3B72B0;
                color: #FFFFFF;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #0F223C;
                border: 1px solid #1C3B65;
                border-radius: 4px;
                padding: 8px 12px;
                color: #E2F1FF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1C3B65;
                border-color: #2D5A8F;
                color: #FFFFFF;
            }
        """
        self.btn_start.setStyleSheet(inactive_style)
        self.btn_stop.setStyleSheet(active_style)
        self.mission_active = False
        self.send_command_packet()
        print("[Mission Control] Autonomous waypoint route execution STOPPED.")
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            if hasattr(self.telemetry_thread, 'stop_mission'):
                self.telemetry_thread.stop_mission()

    def start_manual(self):
        # Safety Pre-check: Vehicle must be armed
        if not getattr(self, 'is_armed', False):
            self.log_mission("Error: Cannot start manual control. Vehicle is disarmed! Please ARM the vehicle first.")
            self.show_toast_alert("Reject Start: Vehicle is disarmed!", is_critical=True)
            return

        active_style = """
            QPushButton {
                background-color: #1C3B65;
                border: 1px solid #2D5A8F;
                border-radius: 4px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2D5A8F;
                border-color: #3B72B0;
                color: #FFFFFF;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #0F223C;
                border: 1px solid #1C3B65;
                border-radius: 4px;
                padding: 8px 12px;
                color: #E2F1FF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1C3B65;
                border-color: #2D5A8F;
                color: #FFFFFF;
            }
        """
        if hasattr(self, 'btn_manual_start'):
            self.btn_manual_start.setStyleSheet(active_style)
        if hasattr(self, 'btn_manual_stop'):
            self.btn_manual_stop.setStyleSheet(inactive_style)

        self.manual_running = True
        self.send_command_packet()
        print("[Mission Control] Manual vehicle operation STARTED.")
        self.log_mission("Manual vehicle operation STARTED.")

    def stop_manual(self):
        active_style = """
            QPushButton {
                background-color: #1C3B65;
                border: 1px solid #2D5A8F;
                border-radius: 4px;
                padding: 8px 12px;
                color: #FFFFFF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2D5A8F;
                border-color: #3B72B0;
                color: #FFFFFF;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #0F223C;
                border: 1px solid #1C3B65;
                border-radius: 4px;
                padding: 8px 12px;
                color: #E2F1FF;
                font-family: 'Google Sans', sans-serif;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #1C3B65;
                border-color: #2D5A8F;
                color: #FFFFFF;
            }
        """
        if hasattr(self, 'btn_manual_start'):
            self.btn_manual_start.setStyleSheet(inactive_style)
        if hasattr(self, 'btn_manual_stop'):
            self.btn_manual_stop.setStyleSheet(active_style)

        self.manual_running = False
        self.send_command_packet()
        print("[Mission Control] Manual vehicle operation STOPPED.")
        self.log_mission("Manual vehicle operation STOPPED.")

    def refresh_joystick_devices(self):
        # Do not refresh if joystick is active/enabled
        if self.joystick is not None:
            return
            
        try:
            import pygame
            # Re-initialize pygame joystick module to detect hot-plugs on Windows
            pygame.joystick.quit()
            pygame.joystick.init()
            
            count = pygame.joystick.get_count()
            curr_text = self.combo_joystick.currentText()
            self.combo_joystick.clear()
            
            if count == 0:
                self.combo_joystick.addItem("No Device Detected")
                self.combo_joystick.setEnabled(False)
                self.btn_joystick_enable.setEnabled(False)
            else:
                self.combo_joystick.setEnabled(True)
                self.btn_joystick_enable.setEnabled(True)
                    
                for i in range(count):
                    try:
                        joy = pygame.joystick.Joystick(i)
                        joy.init()
                        self.combo_joystick.addItem(f"{joy.get_name()} (Device {i})", i)
                        joy.quit()
                    except:
                        pass
                
                # Restore selection
                index = self.combo_joystick.findText(curr_text)
                if index >= 0:
                    self.combo_joystick.setCurrentIndex(index)
                else:
                    self.combo_joystick.setCurrentIndex(0)
                    
                # Auto-reconnect if it was previously active
                if getattr(self, 'joystick_auto_reconnect', False):
                    print("[Joystick] Target device detected. Attempting auto-reconnection...")
                    self.btn_joystick_enable.setChecked(True)
                    self.load_joystick_config()
        except Exception as e:
            print(f"[Joystick Scan Error] {e}")

    @Slot(bool)
    def toggle_joystick_state(self, checked):
        if checked:
            self.joystick_auto_reconnect = True
            import pygame
            idx = self.combo_joystick.currentData()
            if idx is not None:
                try:
                    self.joystick = pygame.joystick.Joystick(idx)
                    self.joystick.init()
                    j_name = self.joystick.get_name()
                    print(f"[Joystick] Activated device {idx}: {j_name}")
                    
                    self.lbl_config_status.setText(f"Connected: {j_name}")
                    self.lbl_plan_joy_status.setText(f"CONNECTED ({j_name.upper()})")
                    self.lbl_plan_joy_status.setStyleSheet("color: #4CAF50; font-weight: bold; font-size: 11px;")
                    
                    self.joystick_timer.start()
                except Exception as e:
                    print(f"[Joystick Activation Error] {e}")
                    self.btn_joystick_enable.setChecked(False)
                    self.disable_joystick()
            else:
                self.btn_joystick_enable.setChecked(False)
        else:
            self.disable_joystick()

    def disable_joystick(self, unexpected=False):
        self.joystick_timer.stop()
        if self.joystick is not None:
            try:
                self.joystick.quit()
            except:
                pass
            self.joystick = None
            
        self.btn_joystick_enable.setChecked(False)
        self.lbl_config_status.setText("Loaded Config for ArduSub")
        
        if unexpected:
            self.lbl_plan_joy_status.setText("DISCONNECTED (LINK LOST)")
            self.lbl_plan_joy_status.setStyleSheet("color: #FF5252; font-weight: bold; font-size: 11px;")
        else:
            self.joystick_auto_reconnect = False
            self.lbl_plan_joy_status.setText("DISCONNECTED")
            self.lbl_plan_joy_status.setStyleSheet("color: #EF5350; font-weight: bold; font-size: 11px;")
            
        # Reset progress bars
        self.bar_throttle.setValue(0)
        self.bar_steering.setValue(50)
        self.bar_pitch.setValue(50)
        
        # Reset live output labels to defaults
        for rc_key in ["rc1", "rc2", "rc3"]:
            if hasattr(self, 'rc_output_fields') and rc_key in self.rc_output_fields:
                self.rc_output_fields[rc_key].setText("1500")
        for btn_key in ["arm", "disarm", "start", "stop", "rth", "light", "camera"]:
            if hasattr(self, 'btn_output_fields') and btn_key in self.btn_output_fields:
                self.btn_output_fields[btn_key].setText("0")
                
        # Force immediate scan to refresh the joystick list!
        self.refresh_joystick_devices()

    def poll_joystick_input(self):
        try:
            import pygame
            pygame.event.pump()
            
            if self.joystick is None:
                return
                
            num_axes = self.joystick.get_numaxes()
            num_buttons = self.joystick.get_numbuttons()
            
            # --- 1. Handle Auto-Detection ---
            if self.detecting_axis_key is not None:
                for i in range(num_axes):
                    val = self.joystick.get_axis(i)
                    init_val = self.detecting_initial_axes.get(i, 0.0)
                    if abs(val - init_val) > 0.3:
                        combo = self.rc_axis_combos[self.detecting_axis_key]
                        idx = combo.findData(i)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                        print(f"[Joystick Detect] Detected Axis {i} for {self.detecting_axis_key}")
                        self.cancel_detection()
                        break
                        
            if self.detecting_button_key is not None:
                for i in range(num_buttons):
                    if self.joystick.get_button(i) == 1:
                        combo = self.btn_mapping_combos[self.detecting_button_key]
                        idx = combo.findData(i)
                        if idx >= 0:
                            combo.setCurrentIndex(idx)
                        print(f"[Joystick Detect] Detected Button {i} for {self.detecting_button_key}")
                        self.cancel_detection()
                        break
            
            # --- 2. Process Mapped Axes & Update Outputs ---
            axes_data = {}
            for rc_key in ["rc1", "rc2", "rc3"]:
                if getattr(self, 'failsafe_active', False):
                    self.rc_output_fields[rc_key].setText("1500")
                    axes_data[rc_key] = 50
                    continue
                combo = self.rc_axis_combos[rc_key]
                axis_idx = combo.currentData()
                
                if axis_idx is not None and axis_idx < num_axes:
                    val = self.joystick.get_axis(axis_idx)
                    
                    if self.rc_reverse_chks[rc_key].isChecked():
                        val = -val
                        
                    if val < 0.0:
                        pwm = int(1500 + val * (1500 - self.thruster_min_limit))
                    else:
                        pwm = int(1500 + val * (self.thruster_max_limit - 1500))
                    pwm = max(self.thruster_min_limit, min(self.thruster_max_limit, pwm))
                    
                    self.rc_output_fields[rc_key].setText(str(pwm))
                    
                    pct = int((val + 1.0) * 50.0)
                    pct = max(0, min(100, pct))
                    axes_data[rc_key] = pct
                else:
                    self.rc_output_fields[rc_key].setText("1500")
                    axes_data[rc_key] = 50
            
            # Update legacy progress bars
            if "rc3" in axes_data:
                self.bar_throttle.setValue(axes_data["rc3"])
            elif "rc1" in axes_data:
                self.bar_throttle.setValue(axes_data["rc1"])
                
            if "rc1" in axes_data:
                self.bar_steering.setValue(axes_data["rc1"])
            elif "rc2" in axes_data:
                self.bar_steering.setValue(axes_data["rc2"])
                
            if "rc2" in axes_data:
                self.bar_pitch.setValue(axes_data["rc2"])
            elif "rc3" in axes_data:
                self.bar_pitch.setValue(axes_data["rc3"])
                
            # --- 3. Process Mapped Buttons & Trigger Actions ---
            if not hasattr(self, '_prev_btn_states'):
                self._prev_btn_states = {}
                
            for btn_key in ["arm", "disarm", "start", "stop", "rth", "light", "camera"]:
                combo = self.btn_mapping_combos[btn_key]
                btn_idx = combo.currentData()
                
                if btn_idx is not None and btn_idx < num_buttons:
                    curr_state = self.joystick.get_button(btn_idx)
                    self.btn_output_fields[btn_key].setText(str(curr_state))
                    
                    prev_state = self._prev_btn_states.get(btn_key, 0)
                    if curr_state == 1 and prev_state == 0:
                        if btn_key == "arm":
                            self.arm_vehicle()
                        elif btn_key == "disarm":
                            self.disarm_vehicle()
                        elif btn_key == "start":
                            self.start_mission()
                        elif btn_key == "stop":
                            self.stop_mission()
                        elif btn_key == "rth":
                            self.return_to_home()
                        elif btn_key == "light":
                            if not getattr(self, 'failsafe_active', False):
                                new_light_state = not (self.light_state == 1)
                                self.update_light_ui_state(new_light_state)
                                if self.telemetry_thread and self.telemetry_thread.isRunning():
                                    self.telemetry_thread.light_state = self.light_state
                                    self.send_immediate_cmd()
                        elif btn_key == "camera":
                            if not getattr(self, 'failsafe_active', False):
                                new_camera_state = not (self.camera_state == 1)
                                self.update_camera_ui_state(new_camera_state)
                                if self.telemetry_thread and self.telemetry_thread.isRunning():
                                    self.telemetry_thread.camera_state = self.camera_state
                                    self.send_immediate_cmd()
                            
                    self._prev_btn_states[btn_key] = curr_state
                else:
                    self.btn_output_fields[btn_key].setText("0")
            
            # --- 4. Manual Override Safety Check ---
            # If in AUTO mode, check if joystick sticks are moved (outside neutral bounds 1400-1600)
            if not self.btn_manual.isChecked():
                joystick_moved = False
                for rc_key in ["rc1", "rc2", "rc3"]:
                    try:
                        pwm_val = int(self.rc_output_fields[rc_key].text())
                        if abs(pwm_val - 1500) > 100:
                            joystick_moved = True
                    except:
                        pass
                if joystick_moved:
                    print("[Failsafe Override] Gamepad stick movement detected during autonomous mission. Swapping to MANUAL mode!")
                    self.log_mission("Warning: Manual joystick override detected! Mission aborted.")
                    self.set_navigation_mode("manual")
                    self.stop_mission()

            # If manual mode is active, transmit joystick state to telemetry link
            if self.btn_manual.isChecked():
                self.send_command_packet()
                    
        except Exception as e:
            print(f"[Joystick Poll Error] {e}. Disconnecting joystick.")
            self.disable_joystick(unexpected=True)

    def start_auto_detect_axis(self, rc_key):
        self.cancel_detection()
        self.detecting_axis_key = rc_key
        
        import pygame
        pygame.event.pump()
        if self.joystick is not None:
            self.detecting_initial_axes = {}
            for i in range(self.joystick.get_numaxes()):
                self.detecting_initial_axes[i] = self.joystick.get_axis(i)
                
        btn = self.rc_auto_detect_btns[rc_key]
        btn.setText("Detecting...")
        btn.setStyleSheet("background-color: #C62828; color: #FFFFFF; font-weight: bold; font-size: 10px; padding: 4px 8px; min-width: 75px;")

    def start_auto_detect_button(self, btn_key):
        self.cancel_detection()
        self.detecting_button_key = btn_key
        
        btn = self.btn_auto_detect_btns[btn_key]
        btn.setText("Detecting...")
        btn.setStyleSheet("background-color: #C62828; color: #FFFFFF; font-weight: bold; font-size: 10px; padding: 4px 8px; min-width: 75px;")

    def cancel_detection(self):
        if hasattr(self, 'detecting_axis_key') and self.detecting_axis_key is not None:
            key = self.detecting_axis_key
            self.detecting_axis_key = None
            btn = self.rc_auto_detect_btns.get(key)
            if btn:
                btn.setText("Auto Detect")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #8BC34A;
                        border: none;
                        border-radius: 2px;
                        color: #000000;
                        font-weight: bold;
                        font-size: 10px;
                        padding: 4px 8px;
                        min-width: 75px;
                    }
                    QPushButton:hover {
                        background-color: #9CCC65;
                    }
                """)
                
        if hasattr(self, 'detecting_button_key') and self.detecting_button_key is not None:
            key = self.detecting_button_key
            self.detecting_button_key = None
            btn = self.btn_auto_detect_btns.get(key)
            if btn:
                btn.setText("Auto Detect")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #8BC34A;
                        border: none;
                        border-radius: 2px;
                        color: #000000;
                        font-weight: bold;
                        font-size: 10px;
                        padding: 4px 8px;
                        min-width: 75px;
                    }
                    QPushButton:hover {
                        background-color: #9CCC65;
                    }
                """)

    def save_joystick_config(self):
        config = {
            "axes": {},
            "buttons": {},
            "thruster_limits": {
                "min": self.thruster_min_limit,
                "max": self.thruster_max_limit
            }
        }
        
        for rc_key in ["rc1", "rc2", "rc3"]:
            config["axes"][rc_key] = {
                "axis": self.rc_axis_combos[rc_key].currentData(),
                "reverse": self.rc_reverse_chks[rc_key].isChecked()
            }
            
        for btn_key in ["arm", "disarm", "start", "stop", "rth", "light", "camera"]:
            config["buttons"][btn_key] = {
                "button": self.btn_mapping_combos[btn_key].currentData()
            }
            
        import json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "joystick_config.json")
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=4)
            print(f"[Joystick Config] Configuration saved to {config_path}")
            self.lbl_config_status.setText("Config Saved Successfully")
            QTimer.singleShot(2000, lambda: self.lbl_config_status.setText("Loaded Config for ArduSub"))
        except Exception as e:
            print(f"[Joystick Config Save Error] {e}")
            self.lbl_config_status.setText("Error Saving Config")

    def load_joystick_config(self):
        import json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "joystick_config.json")
        if not os.path.exists(config_path):
            print("[Joystick Config] No config file found. Using defaults.")
            self.thruster_min_limit = 1100
            self.thruster_max_limit = 1900
            if hasattr(self, 'input_thruster_min'):
                self.input_thruster_min.setText("1100")
            if hasattr(self, 'input_thruster_max'):
                self.input_thruster_max.setText("1900")
                
            default_axes = {"rc1": 0, "rc2": 1, "rc3": 3}
            default_buttons = {"arm": 0, "disarm": 1, "start": 2, "stop": 3, "rth": 4, "light": 5, "camera": 6}
            
            for rc_key, val in default_axes.items():
                combo = self.rc_axis_combos[rc_key]
                idx = combo.findData(val)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                    
            for btn_key, val in default_buttons.items():
                combo = self.btn_mapping_combos[btn_key]
                idx = combo.findData(val)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            return
            
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
                
            # Load axes
            axes_cfg = config.get("axes", {})
            for rc_key, cfg in axes_cfg.items():
                if rc_key in self.rc_axis_combos:
                    axis_val = cfg.get("axis")
                    combo = self.rc_axis_combos[rc_key]
                    idx = combo.findData(axis_val)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                        
                    rev_val = cfg.get("reverse", False)
                    self.rc_reverse_chks[rc_key].setChecked(rev_val)
                    
            # Load buttons
            btns_cfg = config.get("buttons", {})
            for btn_key, cfg in btns_cfg.items():
                if btn_key in self.btn_mapping_combos:
                    btn_val = cfg.get("button")
                    combo = self.btn_mapping_combos[btn_key]
                    idx = combo.findData(btn_val)
                    if idx >= 0:
                        combo.setCurrentIndex(idx)
                        
            # Load thruster speed limits
            limits = config.get("thruster_limits", {})
            self.thruster_min_limit = limits.get("min", 1100)
            self.thruster_max_limit = limits.get("max", 1900)
            if hasattr(self, 'input_thruster_min'):
                self.input_thruster_min.setText(str(self.thruster_min_limit))
            if hasattr(self, 'input_thruster_max'):
                self.input_thruster_max.setText(str(self.thruster_max_limit))
                
            print(f"[Joystick Config] Configuration loaded from {config_path}")
            self.lbl_config_status.setText("Loaded Config for ArduSub")
        except Exception as e:
            print(f"[Joystick Config Load Error] {e}")

    def closeEvent(self, event):
        # Clean shutdown of worker threads
        self.disable_joystick()
        if self.telemetry_thread:
            self.telemetry_thread.stop()
        event.accept()

    def on_alert_badge_clicked(self):
        # 1. Switch active page stack index to Settings (Index 4)
        self.stacked_widget.setCurrentIndex(4)
        
        # 2. Update sidebar active item highlight
        self.sidebar.select_page(4)
        
        # 3. Switch settings page split category stack to Diagnostics (Index 2)
        if hasattr(self, 'select_diagnostics_settings'):
            self.select_diagnostics_settings()

    def show_toast_alert(self, message, is_critical):
        if not hasattr(self, '_active_toasts'):
            self._active_toasts = {}
        if message in self._active_toasts:
            return
        toast = ToastNotification(message, is_critical, self)
        self._active_toasts[message] = toast
        self.reposition_toasts()

    def reposition_toasts(self):
        if not hasattr(self, '_active_toasts'):
            return
        # Filter hidden/deleted toasts
        self._active_toasts = {msg: t for msg, t in self._active_toasts.items() if not t.isHidden()}
        y_offset = 65  # Offset below the TopBar
        parent_w = self.width()
        for msg, toast in self._active_toasts.items():
            toast.setFixedWidth(320)
            toast.adjustSize()
            x = parent_w - toast.width() - 20
            toast.move(x, y_offset)
            toast.show()
            y_offset += toast.height() + 10

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reposition_toasts()

    def save_pid_config(self):
        import json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pid_config.json")
        config = {
            "linear": {
                "kp": float(getattr(self, 'linear_kp', 0.0)),
                "ki": float(getattr(self, 'linear_ki', 0.0)),
                "kd": float(getattr(self, 'linear_kd', 0.0))
            },
            "angular": {
                "kp": float(getattr(self, 'angular_kp', 0.0)),
                "ki": float(getattr(self, 'angular_ki', 0.0)),
                "kd": float(getattr(self, 'angular_kd', 0.0))
            },
            "ahrs_offset": float(getattr(self, 'ahrs_offset', 0.0)),
            "wp_reach_threshold": float(getattr(self, 'wp_reach_threshold', 5.0))
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
            print(f"[PID/AHRS/Threshold Config] Saved to {config_path}")
        except Exception as e:
            print(f"[PID/AHRS/Threshold Config Save Error] {e}")

    def load_pid_config(self):
        import json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pid_config.json")
        if not os.path.exists(config_path):
            self.linear_kp = 0.0
            self.linear_ki = 0.0
            self.linear_kd = 0.0
            self.angular_kp = 0.0
            self.angular_ki = 0.0
            self.angular_kd = 0.0
            self.ahrs_offset = 0.0
            self.wp_reach_threshold = 5.0
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            lin = config.get("linear", {})
            ang = config.get("angular", {})
            self.linear_kp = float(lin.get("kp", 0.0))
            self.linear_ki = float(lin.get("ki", 0.0))
            self.linear_kd = float(lin.get("kd", 0.0))
            self.angular_kp = float(ang.get("kp", 0.0))
            self.angular_ki = float(ang.get("ki", 0.0))
            self.angular_kd = float(ang.get("kd", 0.0))
            self.ahrs_offset = float(config.get("ahrs_offset", config.get("ahrs", {}).get("offset", 0.0)))
            self.wp_reach_threshold = float(config.get("wp_reach_threshold", 5.0))
            
            if hasattr(self, 'spin_wp_threshold') and self.spin_wp_threshold is not None:
                self.spin_wp_threshold.blockSignals(True)
                self.spin_wp_threshold.setValue(self.wp_reach_threshold)
                self.spin_wp_threshold.blockSignals(False)
            
            if hasattr(self, 'input_linear_kp') and self.input_linear_kp is not None:
                self.input_linear_kp.setText(str(self.linear_kp))
            if hasattr(self, 'input_linear_ki') and self.input_linear_ki is not None:
                self.input_linear_ki.setText(str(self.linear_ki))
            if hasattr(self, 'input_linear_kd') and self.input_linear_kd is not None:
                self.input_linear_kd.setText(str(self.linear_kd))
            if hasattr(self, 'input_angular_kp') and self.input_angular_kp is not None:
                self.input_angular_kp.setText(str(self.angular_kp))
            if hasattr(self, 'input_angular_ki') and self.input_angular_ki is not None:
                self.input_angular_ki.setText(str(self.angular_ki))
            if hasattr(self, 'input_angular_kd') and self.input_angular_kd is not None:
                self.input_angular_kd.setText(str(self.angular_kd))
            if hasattr(self, 'input_ahrs_offset') and self.input_ahrs_offset is not None:
                self.input_ahrs_offset.setText(str(self.ahrs_offset))
        except Exception as e:
            print(f"[PID/AHRS Config Load Error] {e}")

    def build_command_payload(self):
        # Format: [manual(0)orauto(1)orconfig(2),stop(0)orstart(1),no.of waypoints,[waypoints],[linearkp,ki,kd],[angularkp,ki,kd],pwm1,pwm2,pwm3,lightstatus(0 or 1 ),camera_status(0 or 1),ahrs_offset]
        if getattr(self, 'is_configuration_mode', False):
            mode = 2
            start_stop = 0
        else:
            mode = 0 if getattr(self, 'btn_manual', None) and self.btn_manual.isChecked() else 1
            if mode == 0:
                start_stop = 1 if getattr(self, 'manual_running', False) else 0
            else:
                start_stop = 1 if getattr(self, 'mission_active', False) else 0
        wps = [[round(float(lat), 6), round(float(lon), 6)] for lat, lon in getattr(self, 'planned_waypoints', [])]
        num_wps = len(wps)
        
        linear_pid = [
            round(float(getattr(self, 'linear_kp', 0.0)), 4),
            round(float(getattr(self, 'linear_ki', 0.0)), 4),
            round(float(getattr(self, 'linear_kd', 0.0)), 4)
        ]
        angular_pid = [
            round(float(getattr(self, 'angular_kp', 0.0)), 4),
            round(float(getattr(self, 'angular_ki', 0.0)), 4),
            round(float(getattr(self, 'angular_kd', 0.0)), 4)
        ]
        
        if getattr(self, 'btn_manual', None) and self.btn_manual.isChecked() and getattr(self, 'is_armed', False) and getattr(self, 'manual_running', False) and not getattr(self, 'failsafe_active', False):
            try:
                pwm1 = int(self.rc_output_fields["rc1"].text()) if hasattr(self, 'rc_output_fields') and "rc1" in self.rc_output_fields else 1500
            except Exception:
                pwm1 = 1500
            try:
                pwm2 = int(self.rc_output_fields["rc2"].text()) if hasattr(self, 'rc_output_fields') and "rc2" in self.rc_output_fields else 1500
            except Exception:
                pwm2 = 1500
            try:
                pwm3 = int(self.rc_output_fields["rc3"].text()) if hasattr(self, 'rc_output_fields') and "rc3" in self.rc_output_fields else 1500
            except Exception:
                pwm3 = 1500
        else:
            pwm1, pwm2, pwm3 = 1500, 1500, 1500
            
        light_status = 1 if getattr(self, 'light_state', 0) else 0
        camera_status = 1 if getattr(self, 'camera_state', 0) else 0
        ahrs_offset = round(float(getattr(self, 'ahrs_offset', 0.0)), 4)
        
        packet = [
            mode,
            start_stop,
            num_wps,
            wps,
            linear_pid,
            angular_pid,
            pwm1,
            pwm2,
            pwm3,
            light_status,
            camera_status,
            ahrs_offset
        ]
        import json
        return json.dumps(packet, separators=(',', ':'))

    def send_command_packet(self):
        payload = self.build_command_payload()
        if hasattr(self, 'lbl_pid_preview') and self.lbl_pid_preview is not None:
            self.lbl_pid_preview.setText(payload)
        if self.telemetry_thread and self.telemetry_thread.isRunning():
            self.telemetry_thread.write_data(payload)
            print(f"[Command Packet TX] {payload}")
            return True
        else:
            print(f"[Offline Command Packet TX] {payload}")
            return False


class ToastNotification(QFrame):
    def __init__(self, message, is_critical, main_win):
        super().__init__(main_win)
        self.main_win = main_win
        self.message = message
        
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # Color schemes based on alert level
        self.is_critical = is_critical
        border_color = "#FF4757" if is_critical else "#FF9F43"
        bg_color = "rgba(45, 8, 13, 0.95)" if is_critical else "rgba(42, 24, 0, 0.95)"
        text_color = "#FFFFFF"
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1.5px solid {border_color};
                border-left: 6px solid {border_color};
                border-radius: 6px;
            }}
            QLabel {{
                color: {text_color};
                font-family: 'Google Sans', sans-serif;
                font-size: 11px;
                font-weight: bold;
                border: none;
                background: transparent;
            }}
            QPushButton {{
                color: #888888;
                font-family: 'Google Sans', sans-serif;
                font-size: 12px;
                font-weight: bold;
                border: none;
                background: transparent;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 10, 10)
        layout.setSpacing(10)
        
        icon_lbl = QLabel("🚨" if is_critical else "⚠️")
        layout.addWidget(icon_lbl)
        
        self.msg_lbl = QLabel(message)
        self.msg_lbl.setWordWrap(True)
        layout.addWidget(self.msg_lbl, 1)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedWidth(20)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close_toast)
        layout.addWidget(close_btn)
        
        # Auto-close timer for non-critical warnings
        if not is_critical:
            self.timer = QTimer(self)
            self.timer.setInterval(5000)
            self.timer.timeout.connect(self.close_toast)
            self.timer.start()
            
    def close_toast(self):
        self.hide()
        if hasattr(self.main_win, '_active_toasts') and self.message in self.main_win._active_toasts:
            self.main_win._active_toasts.pop(self.message, None)
        self.main_win.reposition_toasts()
        self.deleteLater()
