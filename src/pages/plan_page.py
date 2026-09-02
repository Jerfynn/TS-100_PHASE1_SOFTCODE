import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QSplitter, QFrame, QLabel, QPushButton, QTableWidget, QHeaderView
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from src.pages.earth_page import ConsoleWebEnginePage
from src.widgets import MarineHorizon, MarineCompass

def create_plan_page(parent):
    page = QWidget()
    main_layout = QHBoxLayout(page)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)
    
    # Left container split area
    left_container = QWidget()
    left_layout = QVBoxLayout(left_container)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(0)
    
    # Create Vertical Splitter for Map and Bottom Drawer
    parent.plan_splitter = QSplitter(Qt.Vertical)
    parent.plan_splitter.setStyleSheet("""
        QSplitter::handle {
            background-color: #333333;
            height: 4px;
        }
        QSplitter::handle:hover {
            background-color: #FF9100;
        }
    """)
    
    # Map Container Widget with QGridLayout to support overlay instruments
    map_container = QWidget()
    map_grid_layout = QGridLayout(map_container)
    map_grid_layout.setContentsMargins(0, 0, 0, 0)
    
    # Web view map
    parent.plan_web_view = QWebEngineView()
    parent.plan_web_view.setPage(ConsoleWebEnginePage(parent.plan_web_view, callback=parent.handle_plan_console))
    
    # Read plan_map.html content and set
    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plan_map.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        parent.plan_web_view.setHtml(html_content)
        parent.plan_web_view.loadFinished.connect(
            lambda ok: parent.plan_web_view.page().runJavaScript(f"setVesselIcon('{parent.vessel_icon_type}');") if ok else None
        )
    except Exception as e:
        print(f"Error loading plan_map.html: {e}")
        
    map_grid_layout.addWidget(parent.plan_web_view, 0, 0)
    
    # Clear trail action
    def clear_plan_trail():
        if hasattr(parent, 'plan_web_view') and parent.plan_web_view:
            parent.plan_web_view.page().runJavaScript("clearTrack();")
            print("[Plan Map] Vessel navigation trail cleared.")
            if hasattr(parent, 'show_toast_alert'):
                parent.show_toast_alert("Vessel navigation trail cleared", is_critical=False)
    parent.clear_plan_trail = clear_plan_trail

    # 1. Top-Left Overlay Panel for Map Tools (Clear Trail)
    plan_tools_panel = QFrame()
    plan_tools_panel.setStyleSheet("""
        QFrame {
            background: transparent;
            border: none;
            padding: 0px;
            margin: 20px;
        }
    """)
    plan_tools_layout = QHBoxLayout(plan_tools_panel)
    plan_tools_layout.setContentsMargins(0, 0, 0, 0)
    plan_tools_layout.setSpacing(10)
    
    parent.btn_plan_clear_trail = QPushButton("CLEAR TRAIL")
    parent.btn_plan_clear_trail.setStyleSheet("""
        QPushButton {
            background-color: rgba(20, 20, 20, 0.90);
            border: 1.5px solid #333333;
            border-radius: 4px;
            color: #00E5FF;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 0.5px;
            padding: 8px 16px;
        }
        QPushButton:hover {
            background-color: #0078D4;
            border-color: #00E5FF;
            color: #FFFFFF;
        }
        QPushButton:pressed {
            background-color: #106EBE;
        }
    """)
    parent.btn_plan_clear_trail.clicked.connect(clear_plan_trail)
    plan_tools_layout.addWidget(parent.btn_plan_clear_trail)
    map_grid_layout.addWidget(plan_tools_panel, 0, 0, Qt.AlignTop | Qt.AlignLeft)

    # 2. Top-Right Overlay Panel for Attitude (Horizon) & Compass instruments
    plan_instruments_panel = QFrame()
    plan_instruments_panel.setStyleSheet("""
        QFrame {
            background: transparent;
            border: none;
            padding: 0px;
            margin: 20px;
        }
    """)
    plan_instruments_layout = QVBoxLayout(plan_instruments_panel)
    plan_instruments_layout.setContentsMargins(0, 0, 0, 0)
    plan_instruments_layout.setSpacing(15)
    
    # Horizon Indicator
    parent.plan_map_horizon = MarineHorizon(theme="cockpit")
    parent.plan_map_horizon.setFixedSize(190, 190)
    
    # Compass Indicator
    parent.plan_map_compass = MarineCompass(theme="cockpit")
    parent.plan_map_compass.setFixedSize(190, 190)
    
    plan_instruments_layout.addWidget(parent.plan_map_horizon)
    plan_instruments_layout.addWidget(parent.plan_map_compass)
    
    map_grid_layout.addWidget(plan_instruments_panel, 0, 0, Qt.AlignTop | Qt.AlignRight)

    parent.plan_splitter.addWidget(map_container)
    
    # 2. Control Panel (Docked on Right Side - fixed width)
    control_panel = QFrame()
    control_panel.setObjectName("PlanControlPanel")
    control_panel.setFixedWidth(280)
    control_panel.setStyleSheet("""
        QFrame#PlanControlPanel {
            background-color: #121212;
            border-left: 1px solid #333333;
            border-right: none;
            border-top: none;
            border-bottom: none;
            border-radius: 0px;
            padding: 10px;
        }
        QLabel {
            color: #A0A0A0;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
            text-transform: uppercase;
            border: none;
            background: transparent;
        }
        QPushButton {
            background-color: #1A1A1A;
            border: 1px solid #333333;
            border-radius: 4px;
            color: #A0A0A0;
            padding: 8px 12px;
            font-weight: bold;
            font-size: 10px;
        }
        QPushButton:hover {
            background-color: #242424;
            border-color: #FF9100;
            color: #FFFFFF;
        }
        QPushButton[checked="true"] {
            background-color: #FF9100;
            border-color: #FF9100;
            color: #FFFFFF;
        }
    """)
    
    panel_layout = QVBoxLayout(control_panel)
    panel_layout.setContentsMargins(15, 15, 15, 15)
    panel_layout.setSpacing(15)
    
    # Mode selector header label
    mode_label = QLabel("VEHICLE NAVIGATION MODE")
    panel_layout.addWidget(mode_label)
    
    # Horizontal layout for Manual / Automatic buttons
    mode_buttons_layout = QHBoxLayout()
    mode_buttons_layout.setSpacing(6)
    
    parent.btn_manual = QPushButton("MANUAL")
    parent.btn_manual.setCheckable(True)
    parent.btn_manual.setChecked(True)
    parent.btn_manual.setProperty("checked", "true")
    
    parent.btn_auto = QPushButton("AUTOMATIC")
    parent.btn_auto.setCheckable(True)
    
    # Button groups/exclusive toggle connections
    parent.btn_manual.clicked.connect(lambda: parent.set_navigation_mode("manual"))
    parent.btn_auto.clicked.connect(lambda: parent.set_navigation_mode("automatic"))
    
    mode_buttons_layout.addWidget(parent.btn_manual)
    mode_buttons_layout.addWidget(parent.btn_auto)
    panel_layout.addLayout(mode_buttons_layout)
    
    # Automatic Mode Actions Widget (visible only in Auto mode)
    parent.auto_actions_widget = QWidget()
    parent.auto_actions_widget.setStyleSheet("border: none; background: transparent; padding: 0px;")
    actions_layout = QVBoxLayout(parent.auto_actions_widget)
    actions_layout.setContentsMargins(0, 0, 0, 0)
    actions_layout.setSpacing(12)
    
    blue_btn_style = """
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
        QPushButton:pressed {
            background-color: #0A1625;
        }
    """
    
    wp_hdr = QLabel("WAYPOINT ROUTING", parent.auto_actions_widget)
    wp_hdr.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 10px; margin-bottom: 2px;")
    actions_layout.addWidget(wp_hdr)
    
    parent.btn_load_wp = QPushButton("LOAD MISSION", parent.auto_actions_widget)
    parent.btn_load_wp.setStyleSheet(blue_btn_style)
    parent.btn_load_wp.clicked.connect(parent.load_mission_file)
    actions_layout.addWidget(parent.btn_load_wp)
    
    parent.btn_save_wp = QPushButton("SAVE MISSION", parent.auto_actions_widget)
    parent.btn_save_wp.setStyleSheet(blue_btn_style)
    parent.btn_save_wp.clicked.connect(parent.save_mission_file)
    actions_layout.addWidget(parent.btn_save_wp)
    
    parent.btn_send_wp = QPushButton("SEND WAYPOINTS", parent.auto_actions_widget)
    parent.btn_send_wp.setStyleSheet(blue_btn_style)
    parent.btn_send_wp.clicked.connect(parent.upload_planned_route)
    actions_layout.addWidget(parent.btn_send_wp)
    
    parent.btn_clear_wp = QPushButton("CLEAR WAYPOINTS", parent.auto_actions_widget)
    parent.btn_clear_wp.setStyleSheet(blue_btn_style)
    parent.btn_clear_wp.clicked.connect(parent.clear_planned_route)
    actions_layout.addWidget(parent.btn_clear_wp)

    parent.btn_plan_clear_trail_panel = QPushButton("CLEAR TRAIL", parent.auto_actions_widget)
    parent.btn_plan_clear_trail_panel.setStyleSheet(blue_btn_style)
    parent.btn_plan_clear_trail_panel.clicked.connect(clear_plan_trail)
    actions_layout.addWidget(parent.btn_plan_clear_trail_panel)
    
    ctrl_hdr = QLabel("MISSION CONTROL", parent.auto_actions_widget)
    ctrl_hdr.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 10px; margin-bottom: 2px;")
    actions_layout.addWidget(ctrl_hdr)
    
    parent.btn_arm = QPushButton("ARM VEHICLE", parent.auto_actions_widget)
    parent.btn_arm.setStyleSheet(blue_btn_style)
    parent.btn_arm.setEnabled(False) # Disabled until waypoints uploaded & ACK received
    parent.btn_arm.clicked.connect(parent.arm_vehicle)
    actions_layout.addWidget(parent.btn_arm)
    
    parent.btn_disarm = QPushButton("DISARM", parent.auto_actions_widget)
    parent.btn_disarm.setStyleSheet(blue_btn_style)
    parent.btn_disarm.clicked.connect(parent.disarm_vehicle)
    actions_layout.addWidget(parent.btn_disarm)
    
    parent.btn_start = QPushButton("START ROUTE", parent.auto_actions_widget)
    parent.btn_start.setStyleSheet(blue_btn_style)
    parent.btn_start.clicked.connect(parent.start_mission)
    actions_layout.addWidget(parent.btn_start)
    
    parent.btn_stop = QPushButton("STOP ROUTE", parent.auto_actions_widget)
    parent.btn_stop.setStyleSheet(blue_btn_style)
    parent.btn_stop.clicked.connect(parent.stop_mission)
    actions_layout.addWidget(parent.btn_stop)
 
    parent.btn_rth = QPushButton("RETURN TO HOME", parent.auto_actions_widget)
    parent.btn_rth.setStyleSheet(blue_btn_style)
    parent.btn_rth.clicked.connect(parent.return_to_home)
    actions_layout.addWidget(parent.btn_rth)
    
    parent.blue_btn_style = blue_btn_style
 
    panel_layout.addWidget(parent.auto_actions_widget)
    parent.auto_actions_widget.setVisible(False) # Default to manual mode
    
    # Manual Mode Actions Widget (visible only in Manual mode)
    parent.manual_actions_widget = QWidget()
    parent.manual_actions_widget.setStyleSheet("border: none; background: transparent; padding: 0px;")
    manual_layout = QVBoxLayout(parent.manual_actions_widget)
    manual_layout.setContentsMargins(0, 10, 0, 0)
    manual_layout.setSpacing(8)
    
    joy_status_title = QLabel("JOYSTICK STATUS")
    joy_status_title.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 10px; margin-bottom: 2px;")
    manual_layout.addWidget(joy_status_title)
    
    parent.lbl_plan_joy_status = QLabel("DISCONNECTED")
    parent.lbl_plan_joy_status.setStyleSheet("color: #EF5350; font-weight: bold; font-size: 11px; margin-bottom: 10px;")
    manual_layout.addWidget(parent.lbl_plan_joy_status)
    
    # Add ARM/DISARM control buttons for Manual Mode
    ctrl_hdr_manual = QLabel("MISSION CONTROL", parent.manual_actions_widget)
    ctrl_hdr_manual.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 10px; margin-bottom: 2px;")
    manual_layout.addWidget(ctrl_hdr_manual)
    
    parent.btn_manual_arm = QPushButton("ARM VEHICLE", parent.manual_actions_widget)
    parent.btn_manual_arm.setStyleSheet(blue_btn_style)
    parent.btn_manual_arm.clicked.connect(parent.arm_vehicle)
    manual_layout.addWidget(parent.btn_manual_arm)
    
    parent.btn_manual_disarm = QPushButton("DISARM", parent.manual_actions_widget)
    parent.btn_manual_disarm.setStyleSheet(blue_btn_style)
    parent.btn_manual_disarm.clicked.connect(parent.disarm_vehicle)
    manual_layout.addWidget(parent.btn_manual_disarm)
    
    parent.btn_manual_start = QPushButton("START", parent.manual_actions_widget)
    parent.btn_manual_start.setStyleSheet(blue_btn_style)
    parent.btn_manual_start.clicked.connect(parent.start_manual)
    manual_layout.addWidget(parent.btn_manual_start)
    
    parent.btn_manual_stop = QPushButton("STOP", parent.manual_actions_widget)
    parent.btn_manual_stop.setStyleSheet(blue_btn_style)
    parent.btn_manual_stop.clicked.connect(parent.stop_manual)
    manual_layout.addWidget(parent.btn_manual_stop)
    
    panel_layout.addWidget(parent.manual_actions_widget)
    panel_layout.addStretch()
    
    # Widget 2: Bottom Panel (resizes/drags vertically in splitter)
    parent.bottom_panel = QFrame()
    parent.bottom_panel.setObjectName("BottomPanel")
    parent.bottom_panel.setMinimumHeight(180)
    parent.bottom_panel.setMaximumHeight(400)
    parent.bottom_panel.setStyleSheet("""
        QFrame#BottomPanel {
            background-color: #121212;
            border-top: 1px solid #333333;
            border-bottom: none;
            border-left: none;
            border-right: none;
            border-radius: 0px;
            padding: 10px;
        }
        QTableWidget {
            background-color: transparent;
            border: none;
            color: #FFFFFF;
            font-size: 10px;
        }
        QHeaderView::section {
            background-color: transparent;
            color: #A0A0A0;
            padding: 6px;
            border: none;
            font-weight: bold;
            font-size: 9px;
        }
    """)
    
    bottom_layout = QHBoxLayout(parent.bottom_panel)
    bottom_layout.setContentsMargins(15, 10, 15, 10)
    bottom_layout.setSpacing(0)
    
    # Table of waypoints (9 columns matching the image)
    parent.wp_table = QTableWidget(0, 9)
    parent.wp_table.setHorizontalHeaderLabels(["WP", "LATITUDE", "LONGITUDE", "DIST (m)", "STATUS", "DEL", "UP", "DN", "OFFSET"])
    parent.wp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    parent.wp_table.setShowGrid(False)
    
    bottom_layout.addWidget(parent.wp_table, 1)
    
    # Add bottom panel to splitter
    parent.plan_splitter.addWidget(parent.bottom_panel)
    
    # Set splitter sizes
    parent.plan_splitter.setSizes([500, 200])
    
    # Assemble main layouts
    left_layout.addWidget(parent.plan_splitter)
    main_layout.addWidget(left_container, 1)
    main_layout.addWidget(control_panel)
    
    # Default hidden on startup
    parent.bottom_panel.setVisible(False)
    
    # Explicitly initialize to manual mode state on startup once all widgets exist
    parent.set_navigation_mode("manual")
    
    return page
