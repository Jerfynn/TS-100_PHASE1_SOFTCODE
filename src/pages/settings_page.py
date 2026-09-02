import os
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, 
                               QPushButton, QStackedWidget, QComboBox, QDoubleSpinBox, 
                               QLineEdit, QTextEdit, QSplitter, QCheckBox, QFileDialog)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QBrush, QColor, QPen

def browse_log_file(parent):
    folder_path = QFileDialog.getExistingDirectory(
        parent,
        "Select Telemetry Log Directory",
        parent.log_folder_path
    )
    if folder_path:
        parent.log_folder_path = folder_path
        parent.txt_log_path.setText(folder_path)
        parent.log_file_path = None
        print(f"[Settings] Log directory updated to: {folder_path}")

def toggle_logging_state(parent, state):
    parent.logging_enabled = parent.chk_logging.isChecked()
    status_str = "ENABLED" if parent.logging_enabled else "DISABLED"
    print(f"[Settings] Telemetry logging {status_str}")

def on_theme_changed(parent, text):
    selected_theme = "cockpit" if "COCKPIT" in text else "ocean"
    parent.apply_theme(selected_theme)
    
def on_wp_threshold_changed(parent, value):
    parent.wp_reach_threshold = float(value)
    if hasattr(parent, 'save_pid_config'):
        parent.save_pid_config()
    print(f"[Settings] Waypoint reached threshold updated to: {parent.wp_reach_threshold} meters (saved)")

def on_vessel_icon_changed(parent, choice):
    mapping = {
        "AUV Top View (auv_top.png)": "auv_top",
        "Surface Boat (boat.png)": "boat",
        "Missile / Glider (miss.png)": "miss",
        "Directional Arrow": "arrow",
        "Subsea Node (Submarine)": "submarine",
        "Pulse Dot (Default)": "dot"
    }
    parent.vessel_icon_type = mapping.get(choice, "auv_top")
    
    # Immediately push update to the Leaflet maps
    if hasattr(parent, 'web_view') and parent.web_view:
        parent.web_view.page().runJavaScript(f"setVesselIcon('{parent.vessel_icon_type}');")
    if hasattr(parent, 'plan_web_view') and parent.plan_web_view:
        parent.plan_web_view.page().runJavaScript(f"setVesselIcon('{parent.vessel_icon_type}');")
        
    print(f"[Mission Control] Map vessel icon changed to: {parent.vessel_icon_type}")

def on_visual_heading_offset_changed(parent, value):
    parent.visual_heading_offset = float(value)
    visual_yaw = (getattr(parent, 'last_yaw', 0.0) + parent.visual_heading_offset) % 360.0
    
    # Immediately push orientation update to Leaflet map markers
    if hasattr(parent, 'web_view') and parent.web_view:
        parent.web_view.page().runJavaScript(f"rotateMarker({visual_yaw});")
    if hasattr(parent, 'plan_web_view') and parent.plan_web_view:
        parent.plan_web_view.page().runJavaScript(f"rotateMarker({visual_yaw});")
        
    # Immediately update compass gauges
    if hasattr(parent, 'compass_widget') and parent.compass_widget:
        parent.compass_widget.set_yaw(visual_yaw)
    if hasattr(parent, 'map_compass') and parent.map_compass:
        parent.map_compass.set_yaw(visual_yaw)
    if hasattr(parent, 'plan_map_compass') and parent.plan_map_compass:
        parent.plan_map_compass.set_yaw(visual_yaw)
        
    # Update yaw card on dashboard if present
    if hasattr(parent, 'cards') and "yaw" in parent.cards:
        parent.cards["yaw"].set_value(f"{visual_yaw:.2f}")
        
    print(f"[Settings] Vessel nose visual heading offset updated to: {parent.visual_heading_offset}° (Visual Yaw: {visual_yaw:.1f}°)")

def select_general_settings(parent):
    parent.btn_settings_general.setProperty("active", "true")
    parent.btn_settings_general.style().unpolish(parent.btn_settings_general)
    parent.btn_settings_general.style().polish(parent.btn_settings_general)
    
    parent.btn_settings_logger.setProperty("active", "false")
    parent.btn_settings_logger.style().unpolish(parent.btn_settings_logger)
    parent.btn_settings_logger.style().polish(parent.btn_settings_logger)
    
    parent.btn_settings_diagnostics.setProperty("active", "false")
    parent.btn_settings_diagnostics.style().unpolish(parent.btn_settings_diagnostics)
    parent.btn_settings_diagnostics.style().polish(parent.btn_settings_diagnostics)
    
    parent.settings_stacked.setCurrentIndex(0)
    parent.settings_breadcrumb.setText("SYSTEM SETTINGS > GENERAL")

def select_logger_settings(parent):
    parent.btn_settings_general.setProperty("active", "false")
    parent.btn_settings_general.style().unpolish(parent.btn_settings_general)
    parent.btn_settings_general.style().polish(parent.btn_settings_general)
    
    parent.btn_settings_logger.setProperty("active", "true")
    parent.btn_settings_logger.style().unpolish(parent.btn_settings_logger)
    parent.btn_settings_logger.style().polish(parent.btn_settings_logger)
    
    parent.btn_settings_diagnostics.setProperty("active", "false")
    parent.btn_settings_diagnostics.style().unpolish(parent.btn_settings_diagnostics)
    parent.btn_settings_diagnostics.style().polish(parent.btn_settings_diagnostics)
    
    parent.settings_stacked.setCurrentIndex(1)
    parent.settings_breadcrumb.setText("SYSTEM SETTINGS > TELEMETRY LOGGER")

def select_diagnostics_settings(parent):
    parent.btn_settings_general.setProperty("active", "false")
    parent.btn_settings_general.style().unpolish(parent.btn_settings_general)
    parent.btn_settings_general.style().polish(parent.btn_settings_general)
    
    parent.btn_settings_logger.setProperty("active", "false")
    parent.btn_settings_logger.style().unpolish(parent.btn_settings_logger)
    parent.btn_settings_logger.style().polish(parent.btn_settings_logger)
    
    parent.btn_settings_diagnostics.setProperty("active", "true")
    parent.btn_settings_diagnostics.style().unpolish(parent.btn_settings_diagnostics)
    parent.btn_settings_diagnostics.style().polish(parent.btn_settings_diagnostics)
    
    parent.settings_stacked.setCurrentIndex(2)
    parent.settings_breadcrumb.setText("SYSTEM SETTINGS > DATALINK DIAGNOSTICS")

def apply_theme(parent, theme_name):
    parent.current_theme = theme_name.lower()
    
    # 1. Update cards theme property for QSS selector
    for card in parent.cards.values():
        card.setProperty("theme", parent.current_theme)
        card.style().unpolish(card)
        card.style().polish(card)
        
    # 2. Update custom gauges
    gauges_to_update = [
        getattr(parent, 'horizon_widget', None),
        getattr(parent, 'horizon_3d_widget', None),
        getattr(parent, 'compass_widget', None),
        getattr(parent, 'map_horizon', None),
        getattr(parent, 'map_compass', None),
        getattr(parent, 'plan_map_horizon', None),
        getattr(parent, 'plan_map_compass', None),
        getattr(parent, 'battery_gauge', None),
        getattr(parent, 'actuators_gauge', None)
    ]
    for gauge in gauges_to_update:
        if gauge is not None and hasattr(gauge, "theme"):
            gauge.theme = parent.current_theme
            gauge.update()
            
    # 3. Update RealTime charts
    for chart in [parent.attitude_chart, parent.gps_chart, parent.env_chart, parent.power_chart, parent.actuators_chart]:
        if hasattr(chart, "theme"):
            chart.theme = parent.current_theme
            # Update chart styling colors dynamically
            if parent.current_theme == "cockpit":
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
            chart.chart().setBackgroundBrush(QBrush(QColor(bg_hex)))
            chart.chart().setTitleBrush(QBrush(QColor(title_color)))
            chart.setStyleSheet(f"border: 1px solid {border_color}; border-radius: 8px; background-color: {bg_hex};")
            chart.chart().legend().setLabelColor(QColor(title_color))
            chart.axis_y.setLabelsColor(QColor(label_color))
            chart.axis_y.setGridLinePen(QPen(QColor(grid_color), 1, Qt.DashLine))

def send_diagnostics_command(parent):
    cmd = parent.input_diagnostics_cmd.text().strip()
    if not cmd:
        return
        
    parent.txt_diagnostics_terminal.append(f"<span style='color: #FF9100;'>&gt; [TX] {cmd}</span>")
    
    if parent.telemetry_thread and parent.telemetry_thread.isRunning():
        parent.telemetry_thread.write_data(cmd)
    else:
        parent.txt_diagnostics_terminal.append(f"<span style='color: #FF1744;'>[SYS] Datalink inactive. Command not sent.</span>")
        
    parent.input_diagnostics_cmd.clear()

def clear_diagnostics_terminal(parent):
    parent.txt_diagnostics_terminal.clear()

def log_diagnostics_raw(parent, line):
    parent.txt_diagnostics_terminal.append(f"<span style='color: #00FF66;'>&lt; [RX] {line}</span>")

def create_settings_page(parent):
    # Bind helper callbacks to parent dynamically so other components can access them
    parent.browse_log_file = lambda: browse_log_file(parent)
    parent.toggle_logging_state = lambda state: toggle_logging_state(parent, state)
    parent.on_theme_changed = lambda text: on_theme_changed(parent, text)
    parent.on_wp_threshold_changed = lambda value: on_wp_threshold_changed(parent, value)
    parent.on_vessel_icon_changed = Slot(str)(lambda choice: on_vessel_icon_changed(parent, choice))
    parent.on_visual_heading_offset_changed = lambda value: on_visual_heading_offset_changed(parent, value)
    parent.select_general_settings = lambda: select_general_settings(parent)
    parent.select_logger_settings = lambda: select_logger_settings(parent)
    parent.select_diagnostics_settings = lambda: select_diagnostics_settings(parent)
    parent.apply_theme = lambda theme_name: apply_theme(parent, theme_name)
    parent.send_diagnostics_command = lambda: send_diagnostics_command(parent)
    parent.clear_diagnostics_terminal = lambda: clear_diagnostics_terminal(parent)
    parent.log_diagnostics_raw = lambda line: log_diagnostics_raw(parent, line)
    
    # Resolve absolute paths for the settings page assets
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    down_arrow_path = os.path.join(src_dir, "down_arrow.png").replace("\\", "/")
    check_path = os.path.join(src_dir, "check.png").replace("\\", "/")
    
    page = QWidget()
    page.setObjectName("SettingsPage")
    page.setStyleSheet(f"""
        QWidget#SettingsPage {{
            background-color: #1e1e1f;
            color: #FFFFFF;
            font-family: 'Google Sans', sans-serif;
        }}
        QLabel {{
            color: #FFFFFF;
        }}
        QFrame#SettingCard {{
            background-color: #2a2a2b;
            border: 1px solid #3c3c3d;
            border-radius: 6px;
        }}
        QFrame#SettingCard:hover {{
            border-color: #0078D4;
            background-color: #323233;
        }}
        QLabel#SettingTitle {{
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        QLabel#SettingDescription {{
            color: #cccccc;
            font-size: 10px;
            font-weight: normal;
            background: transparent;
            border: none;
        }}
        QComboBox {{
            background-color: #252526;
            border: 1px solid #444445;
            border-bottom: 1px solid #5a5a5b;
            border-radius: 4px;
            padding: 5px 30px 5px 10px;
            color: #FFFFFF;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
            min-width: 180px;
        }}
        QComboBox:hover {{
            background-color: #2c2c2d;
            border-color: #0078D4;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border: none;
        }}
        QComboBox::down-arrow {{
            image: url({down_arrow_path});
            width: 8px;
            height: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: #1f1f1f;
            border: 1px solid #3c3c3d;
            color: #FFFFFF;
            selection-background-color: #0078D4;
            selection-color: #FFFFFF;
            outline: 0px;
            padding: 4px;
        }}
        QDoubleSpinBox {{
            background-color: #252526;
            border: 1px solid #444445;
            border-bottom: 1px solid #5a5a5b;
            border-radius: 4px;
            color: #FFFFFF;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
            padding: 5px 8px;
            min-width: 100px;
        }}
        QDoubleSpinBox:focus {{
            border-color: #0078D4;
        }}
        QLineEdit#SettingLineEdit {{
            background-color: #252526;
            border: 1px solid #444445;
            border-bottom: 1px solid #5a5a5b;
            border-radius: 4px;
            color: #FFFFFF;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
            padding: 5px 8px;
        }}
        QLineEdit#SettingLineEdit:focus {{
            border-color: #0078D4;
        }}
        QPushButton#SettingButton {{
            background-color: #2d2d2d;
            border: 1px solid #444445;
            border-bottom: 1px solid #5a5a5b;
            border-radius: 4px;
            color: #FFFFFF;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
            font-weight: 600;
            padding: 5px 16px;
        }}
        QPushButton#SettingButton:hover {{
            background-color: #353536;
            border-color: #555556;
        }}
        QPushButton#SettingButton:pressed {{
            background-color: #202021;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            background-color: #252526;
            border: 1px solid #444445;
            border-radius: 3px;
        }}
        QCheckBox::indicator:unchecked:hover {{
            background-color: #2c2c2d;
            border-color: #555556;
        }}
        QCheckBox::indicator:checked {{
            image: url({check_path});
            background-color: #0078D4;
            border-color: #0078D4;
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: #1085E0;
            border-color: #1085E0;
        }}
    """)
    
    main_layout = QHBoxLayout(page)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)
    
    # Horizontal Splitter for Settings Menu and Content Panel
    parent.settings_splitter = QSplitter(Qt.Horizontal)
    parent.settings_splitter.setStyleSheet("""
        QSplitter::handle {
            background-color: #2D2D2D;
            width: 4px;
        }
        QSplitter::handle:hover {
            background-color: #555555;
        }
    """)
    
    # 1. Left Tile Bar Menu
    left_menu = QFrame()
    left_menu.setObjectName("SettingsLeftMenu")
    left_menu.setMinimumWidth(180)
    left_menu.setMaximumWidth(300)
    left_menu.setStyleSheet("""
        QFrame#SettingsLeftMenu {
            background-color: #141414;
            border-right: 1px solid #2d2d2d;
            border-left: none;
            border-top: none;
            border-bottom: none;
            border-radius: 0px;
            padding: 15px 5px;
        }
        QLabel {
            color: #888888;
            font-family: 'Google Sans', sans-serif;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-left: 15px;
            margin-bottom: 8px;
            border: none;
            background: transparent;
        }
        QPushButton {
            background-color: transparent;
            border: none;
            border-left: 3px solid transparent;
            border-radius: 4px;
            color: #CCCCCC;
            padding: 10px 15px;
            font-family: 'Google Sans', sans-serif;
            font-weight: bold;
            font-size: 11px;
            text-align: left;
            margin: 2px 10px;
        }
        QPushButton:hover {
            background-color: #202020;
            color: #FFFFFF;
        }
        QPushButton[active="true"] {
            background-color: #2b2b2b;
            color: #FFFFFF;
            border-left: 3px solid #0078D4;
            border-top-left-radius: 0px;
            border-bottom-left-radius: 0px;
            padding-left: 12px;
        }
    """)
    
    menu_layout = QVBoxLayout(left_menu)
    menu_layout.setContentsMargins(0, 0, 0, 0)
    menu_layout.setSpacing(5)
    menu_layout.setAlignment(Qt.AlignTop)
    
    menu_title = QLabel("SETTINGS CATEGORY")
    menu_layout.addWidget(menu_title)
    
    parent.btn_settings_general = QPushButton("GENERAL")
    parent.btn_settings_general.setProperty("active", "true")
    menu_layout.addWidget(parent.btn_settings_general)
    
    parent.btn_settings_logger = QPushButton("TELEMETRY LOGGER")
    parent.btn_settings_logger.setProperty("active", "false")
    menu_layout.addWidget(parent.btn_settings_logger)
    
    parent.btn_settings_diagnostics = QPushButton("DATALINK DIAGNOSTICS")
    parent.btn_settings_diagnostics.setProperty("active", "false")
    menu_layout.addWidget(parent.btn_settings_diagnostics)
    
    menu_layout.addStretch()
    parent.settings_splitter.addWidget(left_menu)
    
    # 2. Right Content Container (With Breadcrumb at Top + Stacked Widget)
    right_container = QWidget()
    right_container.setObjectName("SettingsRightContainer")
    right_container.setStyleSheet("""
        QWidget#SettingsRightContainer {
            background-color: #1e1e1f;
        }
    """)
    right_container_layout = QVBoxLayout(right_container)
    right_container_layout.setContentsMargins(0, 0, 0, 0)
    right_container_layout.setSpacing(0)
    
    # Breadcrumb header
    parent.settings_breadcrumb = QLabel("SYSTEM SETTINGS > GENERAL")
    parent.settings_breadcrumb.setStyleSheet("""
        color: #FFFFFF;
        background-color: #161616;
        border-bottom: 1px solid #2d2d2d;
        font-family: 'Google Sans', sans-serif;
        font-size: 11px;
        font-weight: bold;
        padding: 15px 30px;
        letter-spacing: 0.5px;
    """)
    right_container_layout.addWidget(parent.settings_breadcrumb)
    
    # Stacked widget to display selected option
    parent.settings_stacked = QStackedWidget()
    right_container_layout.addWidget(parent.settings_stacked, 1)
    
    parent.settings_splitter.addWidget(right_container)
    parent.settings_splitter.setSizes([200, 800])
    main_layout.addWidget(parent.settings_splitter, 1)
    
    # --- Page 1: General Page ---
    general_page = QWidget()
    general_layout = QVBoxLayout(general_page)
    general_layout.setContentsMargins(30, 20, 30, 30)
    general_layout.setSpacing(12)
    general_layout.setAlignment(Qt.AlignTop)
    
    gen_title = QLabel("General System Settings")
    gen_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 10px; border: none; background: transparent;")
    general_layout.addWidget(gen_title)
    
    # Theme
    theme_card = QFrame()
    theme_card.setObjectName("SettingCard")
    theme_card_lay = QHBoxLayout(theme_card)
    theme_card_lay.setContentsMargins(16, 12, 16, 12)
    theme_card_lay.setSpacing(15)
    
    theme_info = QVBoxLayout()
    theme_info.setSpacing(2)
    theme_title = QLabel("System UI Theme")
    theme_title.setObjectName("SettingTitle")
    theme_desc = QLabel("Select the visual color scheme for the ground station interface")
    theme_desc.setObjectName("SettingDescription")
    theme_info.addWidget(theme_title)
    theme_info.addWidget(theme_desc)
    
    parent.combo_theme = QComboBox()
    parent.combo_theme.addItems(["COCKPIT Theme (Dark)", "OCEAN Theme (Blue)"])
    parent.combo_theme.setCurrentIndex(0 if parent.current_theme == "cockpit" else 1)
    parent.combo_theme.currentTextChanged.connect(parent.on_theme_changed)
    
    theme_card_lay.addLayout(theme_info, 1)
    theme_card_lay.addWidget(parent.combo_theme)
    general_layout.addWidget(theme_card)
    
    # Waypoint Reached Threshold
    wp_card = QFrame()
    wp_card.setObjectName("SettingCard")
    wp_card_lay = QHBoxLayout(wp_card)
    wp_card_lay.setContentsMargins(16, 12, 16, 12)
    wp_card_lay.setSpacing(15)
    
    wp_info = QVBoxLayout()
    wp_info.setSpacing(2)
    wp_title = QLabel("Waypoint Reached Threshold")
    wp_title.setObjectName("SettingTitle")
    wp_desc = QLabel("Set proximity radius threshold (in meters) to mark a waypoint as successfully reached.")
    wp_desc.setObjectName("SettingDescription")
    wp_info.addWidget(wp_title)
    wp_info.addWidget(wp_desc)
    
    wp_ctrl_layout = QHBoxLayout()
    wp_ctrl_layout.setSpacing(6)
    
    parent.spin_wp_threshold = QDoubleSpinBox()
    parent.spin_wp_threshold.setRange(0.5, 50.0)
    parent.spin_wp_threshold.setSingleStep(0.5)
    parent.spin_wp_threshold.setValue(getattr(parent, 'wp_reach_threshold', 5.0))
    parent.spin_wp_threshold.setSuffix(" m")
    parent.spin_wp_threshold.valueChanged.connect(parent.on_wp_threshold_changed)
    
    # Preset quick buttons (3m, 5m, 8m, 10m, 15m)
    for p_val, p_lbl in [(3.0, "3 m"), (5.0, "5 m"), (8.0, "8 m"), (10.0, "10 m"), (15.0, "15 m")]:
        p_btn = QPushButton(p_lbl)
        p_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A2733;
                border: 1px solid #2B4257;
                border-radius: 3px;
                color: #00E5FF;
                font-family: 'Google Sans', sans-serif;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #0078D4;
                border-color: #0078D4;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #106EBE;
            }
        """)
        p_btn.clicked.connect(lambda _, v=p_val: parent.spin_wp_threshold.setValue(v))
        wp_ctrl_layout.addWidget(p_btn)
        
    wp_ctrl_layout.addWidget(parent.spin_wp_threshold)
    
    wp_card_lay.addLayout(wp_info, 1)
    wp_card_lay.addLayout(wp_ctrl_layout)
    general_layout.addWidget(wp_card)
    
    # Vessel Icon Selection
    icon_card = QFrame()
    icon_card.setObjectName("SettingCard")
    icon_card_lay = QHBoxLayout(icon_card)
    icon_card_lay.setContentsMargins(16, 12, 16, 12)
    icon_card_lay.setSpacing(15)
    
    icon_info = QVBoxLayout()
    icon_info.setSpacing(2)
    icon_title = QLabel("Map Vessel Icon")
    icon_title.setObjectName("SettingTitle")
    icon_desc = QLabel("Choose the vehicle icon representation style on the Leaflet navigation maps.")
    icon_desc.setObjectName("SettingDescription")
    icon_info.addWidget(icon_title)
    icon_info.addWidget(icon_desc)
    
    parent.combo_vessel_icon = QComboBox()
    parent.combo_vessel_icon.addItems([
        "AUV Top View (auv_top.png)",
        "Surface Boat (boat.png)",
        "Missile / Glider (miss.png)",
        "Directional Arrow",
        "Subsea Node (Submarine)",
        "Pulse Dot (Default)"
    ])
    parent.combo_vessel_icon.setCurrentIndex(0)
    parent.combo_vessel_icon.currentTextChanged.connect(parent.on_vessel_icon_changed)
    
    icon_card_lay.addLayout(icon_info, 1)
    icon_card_lay.addWidget(parent.combo_vessel_icon)
    general_layout.addWidget(icon_card)
    
    # 4. Nose Icon / Heading Visual Offset Calibration Card
    heading_card = QFrame()
    heading_card.setObjectName("SettingCard")
    heading_card_lay = QHBoxLayout(heading_card)
    heading_card_lay.setContentsMargins(16, 12, 16, 12)
    heading_card_lay.setSpacing(15)
    
    heading_info = QVBoxLayout()
    heading_info.setSpacing(2)
    heading_title = QLabel("Nose Icon / Heading Visual Offset")
    heading_title.setObjectName("SettingTitle")
    heading_desc = QLabel("Calibrate visual heading orientation for the vessel nose icon, map marker, and compass dials (e.g. -90.0°).")
    heading_desc.setObjectName("SettingDescription")
    heading_info.addWidget(heading_title)
    heading_info.addWidget(heading_desc)
    
    heading_ctrl_layout = QHBoxLayout()
    heading_ctrl_layout.setSpacing(6)
    
    parent.spin_visual_heading_offset = QDoubleSpinBox()
    parent.spin_visual_heading_offset.setRange(-360.0, 360.0)
    parent.spin_visual_heading_offset.setSingleStep(1.0)
    parent.spin_visual_heading_offset.setDecimals(1)
    parent.spin_visual_heading_offset.setValue(getattr(parent, 'visual_heading_offset', -90.0))
    parent.spin_visual_heading_offset.setSuffix("°")
    parent.spin_visual_heading_offset.valueChanged.connect(parent.on_visual_heading_offset_changed)
    
    # Preset quick buttons (-90°, 0°, +90°, +180°)
    for p_val, p_lbl in [(-90.0, "-90°"), (0.0, "0°"), (90.0, "+90°"), (180.0, "+180°")]:
        p_btn = QPushButton(p_lbl)
        p_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A2733;
                border: 1px solid #2B4257;
                border-radius: 3px;
                color: #00E5FF;
                font-family: 'Google Sans', sans-serif;
                font-size: 10px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #0078D4;
                border-color: #0078D4;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #106EBE;
            }
        """)
        p_btn.clicked.connect(lambda _, v=p_val: parent.spin_visual_heading_offset.setValue(v))
        heading_ctrl_layout.addWidget(p_btn)
        
    heading_ctrl_layout.addWidget(parent.spin_visual_heading_offset)
    
    heading_card_lay.addLayout(heading_info, 1)
    heading_card_lay.addLayout(heading_ctrl_layout)
    general_layout.addWidget(heading_card)
    
    parent.settings_stacked.addWidget(general_page)
    
    # --- Page 2: Logger Page ---
    logger_page = QWidget()
    logger_layout = QVBoxLayout(logger_page)
    logger_layout.setContentsMargins(30, 20, 30, 30)
    logger_layout.setSpacing(12)
    logger_layout.setAlignment(Qt.AlignTop)
    
    logger_title = QLabel("Telemetry Logger Configuration")
    logger_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 10px; border: none; background: transparent;")
    logger_layout.addWidget(logger_title)
    
    # Enable logging card
    logging_card = QFrame()
    logging_card.setObjectName("SettingCard")
    logging_card_lay = QHBoxLayout(logging_card)
    logging_card_lay.setContentsMargins(16, 12, 16, 12)
    logging_card_lay.setSpacing(15)
    
    logging_info = QVBoxLayout()
    logging_info.setSpacing(2)
    logging_title_lbl = QLabel("Live CSV Telemetry Logging")
    logging_title_lbl.setObjectName("SettingTitle")
    logging_desc_lbl = QLabel("When enabled, incoming serial packets from the vehicle will be appended to the selected file in CSV format.")
    logging_desc_lbl.setObjectName("SettingDescription")
    logging_info.addWidget(logging_title_lbl)
    logging_info.addWidget(logging_desc_lbl)
    
    parent.chk_logging = QCheckBox()
    parent.chk_logging.setChecked(parent.logging_enabled)
    parent.chk_logging.stateChanged.connect(parent.toggle_logging_state)
    
    logging_card_lay.addLayout(logging_info, 1)
    logging_card_lay.addWidget(parent.chk_logging)
    logger_layout.addWidget(logging_card)
    
    # Log path card
    path_card = QFrame()
    path_card.setObjectName("SettingCard")
    path_card_lay = QHBoxLayout(path_card)
    path_card_lay.setContentsMargins(16, 12, 16, 12)
    path_card_lay.setSpacing(15)
    
    path_info = QVBoxLayout()
    path_info.setSpacing(2)
    path_title_lbl = QLabel("Logging Directory")
    path_title_lbl.setObjectName("SettingTitle")
    path_desc_lbl = QLabel("Configure the ground station data logging destination path.")
    path_desc_lbl.setObjectName("SettingDescription")
    path_info.addWidget(path_title_lbl)
    path_info.addWidget(path_desc_lbl)
    
    path_controls = QHBoxLayout()
    path_controls.setSpacing(8)
    
    parent.txt_log_path = QLineEdit()
    parent.txt_log_path.setObjectName("SettingLineEdit")
    parent.txt_log_path.setReadOnly(True)
    parent.txt_log_path.setText(parent.log_folder_path)
    parent.txt_log_path.setMinimumWidth(250)
    
    btn_browse = QPushButton("Browse")
    btn_browse.setObjectName("SettingButton")
    btn_browse.clicked.connect(parent.browse_log_file)
    
    path_controls.addWidget(parent.txt_log_path)
    path_controls.addWidget(btn_browse)
    
    path_card_lay.addLayout(path_info, 1)
    path_card_lay.addLayout(path_controls)
    logger_layout.addWidget(path_card)
    
    parent.settings_stacked.addWidget(logger_page)
    
    # --- Page 3: Diagnostics Page ---
    diagnostics_page = QWidget()
    diagnostics_layout = QVBoxLayout(diagnostics_page)
    diagnostics_layout.setContentsMargins(30, 20, 30, 30)
    diagnostics_layout.setSpacing(12)
    diagnostics_layout.setAlignment(Qt.AlignTop)
    
    diag_title = QLabel("Datalink Diagnostics Console")
    diag_title.setStyleSheet("color: #FFFFFF; font-size: 16px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 10px; border: none; background: transparent;")
    diagnostics_layout.addWidget(diag_title)
    
    diag_card = QFrame()
    diag_card.setObjectName("SettingCard")
    diag_lay = QVBoxLayout(diag_card)
    diag_lay.setContentsMargins(20, 20, 20, 20)
    diag_lay.setSpacing(15)
    
    diag_desc = QLabel("Transmit manual action packets (e.g. ARM, DISARM, START, STOP, RTH, WP,...) and observe raw subsea datagram frames in real-time.")
    diag_desc.setObjectName("SettingDescription")
    diag_desc.setWordWrap(True)
    diag_lay.addWidget(diag_desc)
    
    parent.txt_diagnostics_terminal = QTextEdit()
    parent.txt_diagnostics_terminal.setReadOnly(True)
    parent.txt_diagnostics_terminal.setMinimumHeight(240)
    parent.txt_diagnostics_terminal.setStyleSheet("""
        QTextEdit {
            background-color: #121212;
            border: 1px solid #323232;
            border-radius: 4px;
            color: #00FF66;
            font-family: 'Google Sans', monospace;
            font-size: 11px;
            padding: 10px;
        }
    """)
    diag_lay.addWidget(parent.txt_diagnostics_terminal)
    
    input_row = QHBoxLayout()
    input_row.setSpacing(10)
    
    parent.input_diagnostics_cmd = QLineEdit()
    parent.input_diagnostics_cmd.setPlaceholderText("Enter command (e.g. ARM, DISARM, RTH, WP,1,12.98,80.24)...")
    parent.input_diagnostics_cmd.setStyleSheet("""
        QLineEdit {
            background-color: #121212;
            border: 1px solid #323232;
            border-radius: 4px;
            color: #00FF66;
            font-family: 'Google Sans', monospace;
            font-size: 11px;
            padding: 8px;
        }
        QLineEdit:focus {
            border-color: #0078D4;
        }
    """)
    parent.input_diagnostics_cmd.returnPressed.connect(parent.send_diagnostics_command)
    
    btn_send_cmd = QPushButton("SEND")
    btn_send_cmd.setObjectName("SettingButton")
    btn_send_cmd.setStyleSheet("""
        QPushButton {
            background-color: #0078D4;
            border: 1px solid #0078D4;
            border-radius: 4px;
            color: #FFFFFF;
            font-weight: bold;
            padding: 8px 20px;
        }
        QPushButton:hover {
            background-color: #1085E0;
            border-color: #1085E0;
        }
    """)
    btn_send_cmd.clicked.connect(parent.send_diagnostics_command)
    
    btn_clear_cmd = QPushButton("CLEAR")
    btn_clear_cmd.setObjectName("SettingButton")
    btn_clear_cmd.clicked.connect(parent.clear_diagnostics_terminal)
    
    input_row.addWidget(parent.input_diagnostics_cmd, 1)
    input_row.addWidget(btn_send_cmd)
    input_row.addWidget(btn_clear_cmd)
    diag_lay.addLayout(input_row)
    
    diagnostics_layout.addWidget(diag_card)
    parent.settings_stacked.addWidget(diagnostics_page)
    
    # Connect menu selection click actions
    parent.btn_settings_general.clicked.connect(parent.select_general_settings)
    parent.btn_settings_logger.clicked.connect(parent.select_logger_settings)
    parent.btn_settings_diagnostics.clicked.connect(parent.select_diagnostics_settings)
    
    return page
