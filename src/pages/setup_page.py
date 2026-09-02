import os
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, 
                               QPushButton, QStackedWidget, QScrollArea, QComboBox, 
                               QCheckBox, QGridLayout, QLineEdit, QProgressBar)
from PySide6.QtCore import Qt, QTimer

def select_joystick_setup(parent):
    parent.btn_menu_joystick.setProperty("active", "true")
    parent.btn_menu_joystick.style().unpolish(parent.btn_menu_joystick)
    parent.btn_menu_joystick.style().polish(parent.btn_menu_joystick)
    
    parent.btn_menu_light.setProperty("active", "false")
    parent.btn_menu_light.style().unpolish(parent.btn_menu_light)
    parent.btn_menu_light.style().polish(parent.btn_menu_light)

    if hasattr(parent, 'btn_menu_pid'):
        parent.btn_menu_pid.setProperty("active", "false")
        parent.btn_menu_pid.style().unpolish(parent.btn_menu_pid)
        parent.btn_menu_pid.style().polish(parent.btn_menu_pid)
    
    parent.setup_stacked.setCurrentIndex(0)
    parent.setup_breadcrumb.setText("HARDWARE CONFIGURATION > JOYSTICK")

def select_light_setup(parent):
    parent.btn_menu_joystick.setProperty("active", "false")
    parent.btn_menu_joystick.style().unpolish(parent.btn_menu_joystick)
    parent.btn_menu_joystick.style().polish(parent.btn_menu_joystick)
    
    parent.btn_menu_light.setProperty("active", "true")
    parent.btn_menu_light.style().unpolish(parent.btn_menu_light)
    parent.btn_menu_light.style().polish(parent.btn_menu_light)

    if hasattr(parent, 'btn_menu_pid'):
        parent.btn_menu_pid.setProperty("active", "false")
        parent.btn_menu_pid.style().unpolish(parent.btn_menu_pid)
        parent.btn_menu_pid.style().polish(parent.btn_menu_pid)
    
    parent.setup_stacked.setCurrentIndex(1)
    parent.setup_breadcrumb.setText("HARDWARE CONFIGURATION > LIGHT")

def select_pid_setup(parent):
    parent.btn_menu_joystick.setProperty("active", "false")
    parent.btn_menu_joystick.style().unpolish(parent.btn_menu_joystick)
    parent.btn_menu_joystick.style().polish(parent.btn_menu_joystick)
    
    parent.btn_menu_light.setProperty("active", "false")
    parent.btn_menu_light.style().unpolish(parent.btn_menu_light)
    parent.btn_menu_light.style().polish(parent.btn_menu_light)

    if hasattr(parent, 'btn_menu_pid'):
        parent.btn_menu_pid.setProperty("active", "true")
        parent.btn_menu_pid.style().unpolish(parent.btn_menu_pid)
        parent.btn_menu_pid.style().polish(parent.btn_menu_pid)
    
    parent.setup_stacked.setCurrentIndex(2)
    parent.setup_breadcrumb.setText("HARDWARE CONFIGURATION > PID & AHRS CONFIGURATION")
    if hasattr(parent, 'lbl_pid_preview'):
        parent.lbl_pid_preview.setText(parent.build_command_payload() if hasattr(parent, 'build_command_payload') else "")
    if hasattr(parent, 'lbl_config_mode_status') and not getattr(parent, 'is_configuration_mode', False):
        prev_mode_str = "0 (Manual)" if getattr(parent, 'btn_manual', None) and parent.btn_manual.isChecked() else "1 (Automatic)"
        parent.lbl_config_mode_status.setText(f"○ Inactive (Mode {prev_mode_str})")

def toggle_config_mode(parent, state=None):
    if state is None:
        state = parent.btn_config_mode_toggle.isChecked()
    else:
        parent.btn_config_mode_toggle.setChecked(state)
        
    parent.is_configuration_mode = state
    
    if state:
        # Configuration ON (Mode 2)
        parent.btn_config_mode_toggle.setText("CONFIGURATION: ON (MODE 2)")
        parent.btn_config_mode_toggle.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                border: 1px solid #2B88D8;
                border-radius: 3px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
        """)
        parent.lbl_config_mode_status.setStyleSheet("color: #00E5FF; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        parent.lbl_config_mode_status.setText("● Active (Mode 2 - Tuning Enabled)")
        parent.btn_send_pid.setEnabled(True)
        parent.btn_send_pid.setStyleSheet("""
            QPushButton {
                background-color: #8BC34A;
                border: none;
                border-radius: 3px;
                color: #000000;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 25px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #9CCC65;
            }
        """)
        parent.lbl_pid_feedback.setStyleSheet("color: #00E5FF; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        parent.lbl_pid_feedback.setText("Mode 2 active. You can now tune and send PID parameters & AHRS offset.")
        # Transmit packet with mode 2
        parent.send_command_packet()
    else:
        # Configuration OFF (Mode 0 or 1)
        parent.btn_config_mode_toggle.setText("CONFIGURATION: OFF")
        parent.btn_config_mode_toggle.setStyleSheet("""
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
        prev_mode_str = "0 (Manual)" if getattr(parent, 'btn_manual', None) and parent.btn_manual.isChecked() else "1 (Automatic)"
        parent.lbl_config_mode_status.setStyleSheet("color: #888888; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        parent.lbl_config_mode_status.setText(f"○ Inactive (Mode {prev_mode_str})")
        parent.btn_send_pid.setEnabled(False)
        parent.btn_send_pid.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: none;
                border-radius: 3px;
                color: #777777;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 25px;
                min-width: 100px;
            }
        """)
        parent.lbl_pid_feedback.setStyleSheet("color: #888888; font-family: 'Google Sans', sans-serif; font-size: 11px; font-style: italic; border: none; background: transparent;")
        parent.lbl_pid_feedback.setText("Configuration mode is OFF. Turn ON configuration to send parameters.")
        # Transmit packet with mode 0 or 1
        parent.send_command_packet()

def exit_config_mode(parent):
    toggle_config_mode(parent, False)

def send_pid_config(parent):
    if not getattr(parent, 'is_configuration_mode', False):
        parent.lbl_pid_feedback.setStyleSheet("color: #FF1744; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        parent.lbl_pid_feedback.setText("Cannot send: Turn ON Configuration Mode first!")
        return

    try:
        lin_kp = float(parent.input_linear_kp.text().strip())
        lin_ki = float(parent.input_linear_ki.text().strip())
        lin_kd = float(parent.input_linear_kd.text().strip())
        
        ang_kp = float(parent.input_angular_kp.text().strip())
        ang_ki = float(parent.input_angular_ki.text().strip())
        ang_kd = float(parent.input_angular_kd.text().strip())
        
        ahrs_offset = float(parent.input_ahrs_offset.text().strip()) if hasattr(parent, 'input_ahrs_offset') and parent.input_ahrs_offset else 0.0
        
        parent.linear_kp = lin_kp
        parent.linear_ki = lin_ki
        parent.linear_kd = lin_kd
        
        parent.angular_kp = ang_kp
        parent.angular_ki = ang_ki
        parent.angular_kd = ang_kd
        
        parent.ahrs_offset = ahrs_offset
        
        # Save to persistent storage
        if hasattr(parent, 'save_pid_config'):
            parent.save_pid_config()
            
        # Transmit telemetry packet
        payload = parent.build_command_payload()
        if parent.telemetry_thread and parent.telemetry_thread.isRunning():
            parent.telemetry_thread.write_data(payload)
            print(f"[PID/AHRS Config] Transmitted control packet: {payload}")
            parent.lbl_pid_feedback.setStyleSheet("color: #8BC34A; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            parent.lbl_pid_feedback.setText(f"✓ Config Sent (Mode 2)")
        else:
            print(f"[PID/AHRS Config Offline] Payload prepared: {payload}")
            parent.lbl_pid_feedback.setStyleSheet("color: #FFC107; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            parent.lbl_pid_feedback.setText(f"Saved (Offline Mode 2)")
            
        if hasattr(parent, 'lbl_pid_preview'):
            parent.lbl_pid_preview.setText(payload)
            
    except ValueError:
        parent.lbl_pid_feedback.setStyleSheet("color: #FF1744; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        parent.lbl_pid_feedback.setText("Invalid floating-point gain/offset entered.")

def set_thruster_limits(parent):
    try:
        min_val = int(parent.input_thruster_min.text().strip())
        max_val = int(parent.input_thruster_max.text().strip())
        
        # Enforce hardware safety boundaries
        if min_val < 1000 or min_val > 1500 or max_val < 1500 or max_val > 2000:
            parent.lbl_thruster_feedback.setStyleSheet("color: #FF1744; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
            parent.lbl_thruster_feedback.setText("Limits must satisfy 1000 <= min <= 1500 <= max <= 2000")
            return
            
        parent.thruster_min_limit = min_val
        parent.thruster_max_limit = max_val
        
        # Save limits to configuration
        parent.save_joystick_config()
        
        # Transmit speed limits to backend
        if parent.telemetry_thread and parent.telemetry_thread.isRunning():
            payload = f"$LIMIT,{min_val},{max_val}"
            parent.telemetry_thread.write_data(payload)
            print(f"[Mission Control] Sent speed limits to backend: {payload}")
            
        parent.lbl_thruster_feedback.setStyleSheet("color: #8BC34A; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        parent.lbl_thruster_feedback.setText("Limits applied and saved successfully!")
        QTimer.singleShot(3000, lambda: parent.lbl_thruster_feedback.setText(""))
    except ValueError:
        parent.lbl_thruster_feedback.setStyleSheet("color: #FF1744; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        parent.lbl_thruster_feedback.setText("Invalid integers entered.")

def flash_warning_banner(parent):
    parent.warning_flash_state = not parent.warning_flash_state
    has_critical = (getattr(parent, 'batt_state', 'normal') == 'critical' or getattr(parent, 'temp_state', 'normal') == 'critical')
    
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
        
    if parent.warning_flash_state:
        parent.warning_banner_frame.setStyleSheet(f"""
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
        parent.warning_banner_frame.setStyleSheet(f"""
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

def create_setup_page(parent):
    from PySide6.QtWidgets import QProgressBar, QStackedWidget, QLineEdit, QSplitter
    
    # Bind helper callbacks to parent dynamically so other components can access them
    parent.select_joystick_setup = lambda: select_joystick_setup(parent)
    parent.select_light_setup = lambda: select_light_setup(parent)
    parent.select_pid_setup = lambda: select_pid_setup(parent)
    parent.send_pid_config = lambda: send_pid_config(parent)
    parent.toggle_config_mode = lambda state=None: toggle_config_mode(parent, state)
    parent.exit_config_mode = lambda: exit_config_mode(parent)
    parent.set_thruster_limits = lambda: set_thruster_limits(parent)
    parent.flash_warning_banner = lambda: flash_warning_banner(parent)
    
    # Resolve absolute paths for setup page assets
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    down_arrow_path = os.path.join(src_dir, "down_arrow.png").replace("\\", "/")
    check_path = os.path.join(src_dir, "check.png").replace("\\", "/")
    
    page = QWidget()
    layout = QHBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    
    # Horizontal Splitter for Setup Menu and Content Panel
    parent.setup_splitter = QSplitter(Qt.Horizontal)
    parent.setup_splitter.setStyleSheet("""
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
    left_menu.setObjectName("SetupLeftMenu")
    left_menu.setMinimumWidth(180)
    left_menu.setMaximumWidth(300)
    left_menu.setStyleSheet("""
        QFrame#SetupLeftMenu {
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
            background: transparent;
            border: none;
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
    
    menu_title = QLabel("HARDWARE MENU")
    menu_layout.addWidget(menu_title)
    
    # Joystick menu option button
    parent.btn_menu_joystick = QPushButton("JOYSTICK")
    parent.btn_menu_joystick.setProperty("active", "true")
    menu_layout.addWidget(parent.btn_menu_joystick)
    
    # Light menu option button
    parent.btn_menu_light = QPushButton("LIGHT")
    parent.btn_menu_light.setProperty("active", "false")
    menu_layout.addWidget(parent.btn_menu_light)
    
    # PID & AHRS menu option button
    parent.btn_menu_pid = QPushButton("PID & AHRS CONFIG")
    parent.btn_menu_pid.setProperty("active", "false")
    menu_layout.addWidget(parent.btn_menu_pid)
    
    menu_layout.addStretch()
    parent.setup_splitter.addWidget(left_menu)
    
    # 2. Right Content Container (With Breadcrumb at Top + Stacked Widget)
    right_container = QWidget()
    right_container.setObjectName("SetupRightContainer")
    right_container.setStyleSheet("""
        QWidget#SetupRightContainer {
            background-color: #1e1e1f;
        }
    """)
    right_container_layout = QVBoxLayout(right_container)
    right_container_layout.setContentsMargins(0, 0, 0, 0)
    right_container_layout.setSpacing(0)
    
    # Breadcrumb header
    parent.setup_breadcrumb = QLabel("HARDWARE CONFIGURATION > JOYSTICK")
    parent.setup_breadcrumb.setStyleSheet("""
        color: #FFFFFF;
        background-color: #161616;
        border-bottom: 1px solid #2d2d2d;
        font-family: 'Google Sans', sans-serif;
        font-size: 11px;
        font-weight: bold;
        padding: 15px 30px;
        letter-spacing: 0.5px;
    """)
    right_container_layout.addWidget(parent.setup_breadcrumb)
    
    # Stacked widget to display selected option
    parent.setup_stacked = QStackedWidget()
    right_container_layout.addWidget(parent.setup_stacked, 1)
    
    parent.setup_splitter.addWidget(right_container)
    parent.setup_splitter.setSizes([180, 800])
    layout.addWidget(parent.setup_splitter, 1)
        
    # Create Joystick Page
    joystick_page = QWidget()
    joystick_layout = QVBoxLayout(joystick_page)
    joystick_layout.setContentsMargins(15, 15, 15, 15)
    joystick_layout.setSpacing(10)
    
    # Scroll Area Setup
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
    
    scroll_content = QWidget()
    scroll_content.setStyleSheet("background-color: transparent;")
    scroll_layout = QVBoxLayout(scroll_content)
    scroll_layout.setContentsMargins(5, 5, 5, 5)
    scroll_layout.setSpacing(15)
    
    # Top Row: Joystick Label | ComboBox | Enable Btn | Save Btn | Loaded Config Label
    top_row = QHBoxLayout()
    top_row.setSpacing(10)
    
    lbl_joy_title = QLabel("Joystick")
    lbl_joy_title.setStyleSheet("color: #FFFFFF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 13px;")
    
    parent.combo_joystick = QComboBox()
    parent.combo_joystick.setMinimumWidth(180)
    parent.combo_joystick.setStyleSheet(f"""
        QComboBox {{
            background-color: #2d2d2d;
            border: 1px solid #404040;
            border-bottom: 1px solid #5a5a5a;
            border-radius: 4px;
            color: #FFFFFF;
            padding: 4px 25px 4px 8px;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
        }}
        QComboBox:hover {{
            background-color: #323232;
            border-color: #555555;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border: none;
        }}
        QComboBox::down-arrow {{
            image: url({down_arrow_path});
            width: 8px;
            height: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: #2d2d2d;
            border: 1px solid #404040;
            color: #FFFFFF;
            selection-background-color: #353535;
            selection-color: #FFFFFF;
            outline: 0px;
        }}
    """)
    
    parent.btn_joystick_enable = QCheckBox("Enable")
    parent.btn_joystick_enable.setStyleSheet(f"""
        QCheckBox {{
            color: #FFFFFF;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
            font-weight: bold;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid #404040;
            background-color: #2d2d2d;
            border-radius: 3px;
        }}
        QCheckBox::indicator:unchecked:hover {{
            background-color: #323232;
            border-color: #555555;
        }}
        QCheckBox::indicator:checked {{
            background-color: #0078D4;
            border-color: #0078D4;
            image: url({check_path});
        }}
    """)
    parent.btn_joystick_enable.clicked.connect(parent.toggle_joystick_state)
    
    parent.btn_joystick_save = QPushButton("Save")
    parent.btn_joystick_save.setStyleSheet("""
        QPushButton {
            background-color: #8BC34A;
            border: none;
            border-radius: 2px;
            color: #000000;
            font-weight: bold;
            font-size: 11px;
            padding: 5px 15px;
        }
        QPushButton:hover {
            background-color: #9CCC65;
        }
    """)
    parent.btn_joystick_save.clicked.connect(parent.save_joystick_config)
    
    parent.lbl_config_status = QLabel("Loaded Config for ArduSub")
    parent.lbl_config_status.setStyleSheet("color: #FFFFFF; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; margin-left: 10px;")
    
    top_row.addWidget(lbl_joy_title)
    top_row.addWidget(parent.combo_joystick)
    top_row.addWidget(parent.btn_joystick_enable)
    top_row.addWidget(parent.btn_joystick_save)
    top_row.addWidget(parent.lbl_config_status)
    top_row.addStretch()
    
    scroll_layout.addLayout(top_row)
    
    # Grid Configuration Panel
    grid_widget = QWidget()
    grid_widget.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 10px;")
    grid_layout = QGridLayout(grid_widget)
    grid_layout.setSpacing(8)
    grid_layout.setContentsMargins(10, 10, 10, 10)
    
    # Grid Column Headers
    grid_layout.addWidget(QLabel(""), 0, 0) # Top-left empty label
    
    lbl_col_axis = QLabel("Controller Axis")
    lbl_col_axis.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 11px;")
    grid_layout.addWidget(lbl_col_axis, 0, 1, 1, 2)
    
    lbl_col_out = QLabel("Output")
    lbl_col_out.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 11px;")
    grid_layout.addWidget(lbl_col_out, 0, 3)
    
    lbl_col_rev = QLabel("Reverse")
    lbl_col_rev.setStyleSheet("color: #AAAAAA; font-weight: bold; font-size: 11px;")
    grid_layout.addWidget(lbl_col_rev, 0, 4, Qt.AlignCenter)
    
    # Common Styles for Elements
    combo_style = f"""
        QComboBox {{
            background-color: #2d2d2d;
            border: 1px solid #404040;
            border-bottom: 1px solid #5a5a5a;
            border-radius: 4px;
            color: #FFFFFF;
            padding: 4px 25px 4px 8px;
            font-family: 'Google Sans', sans-serif;
            font-size: 11px;
            min-width: 95px;
        }}
        QComboBox:hover {{
            background-color: #323232;
            border-color: #555555;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 20px;
            border: none;
        }}
        QComboBox::down-arrow {{
            image: url({down_arrow_path});
            width: 8px;
            height: 8px;
        }}
        QComboBox QAbstractItemView {{
            background-color: #2d2d2d;
            border: 1px solid #404040;
            color: #FFFFFF;
            selection-background-color: #353535;
            selection-color: #FFFFFF;
            outline: 0px;
        }}
    """
    
    btn_detect_style = """
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
        QPushButton:disabled {
            background-color: #555555;
            color: #888888;
        }
    """
    
    output_style = """
        QLabel {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            color: #000000;
            font-family: Courier, monospace;
            font-size: 11px;
            font-weight: bold;
            padding: 4px;
            border-radius: 2px;
            min-width: 60px;
            max-width: 80px;
        }
    """
    
    chk_style = f"""
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid #404040;
            background-color: #2d2d2d;
            border-radius: 3px;
        }}
        QCheckBox::indicator:unchecked:hover {{
            background-color: #323232;
            border-color: #555555;
        }}
        QCheckBox::indicator:checked {{
            background-color: #0078D4;
            border-color: #0078D4;
            image: url({check_path});
        }}
    """
    
    # Populate RC 1 to RC 3 Axes
    parent.rc_axis_combos = {}
    parent.rc_auto_detect_btns = {}
    parent.rc_output_fields = {}
    parent.rc_reverse_chks = {}
    
    for i in range(1, 4):
        row_idx = i
        rc_key = f"rc{i}"
        
        lbl_rc = QLabel(f"RC {i}")
        lbl_rc.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 11px;")
        grid_layout.addWidget(lbl_rc, row_idx, 0)
        
        combo = QComboBox()
        combo.setStyleSheet(combo_style)
        combo.addItem("None", None)
        for axis_id in range(8):
            combo.addItem(f"Axis {axis_id}", axis_id)
        grid_layout.addWidget(combo, row_idx, 1)
        parent.rc_axis_combos[rc_key] = combo
        
        btn_detect = QPushButton("Auto Detect")
        btn_detect.setStyleSheet(btn_detect_style)
        btn_detect.clicked.connect(lambda checked=False, r=rc_key: parent.start_auto_detect_axis(r))
        grid_layout.addWidget(btn_detect, row_idx, 2)
        parent.rc_auto_detect_btns[rc_key] = btn_detect
        
        lbl_output = QLabel("1500")
        lbl_output.setAlignment(Qt.AlignCenter)
        lbl_output.setStyleSheet(output_style)
        grid_layout.addWidget(lbl_output, row_idx, 3)
        parent.rc_output_fields[rc_key] = lbl_output
        
        chk_rev = QCheckBox()
        chk_rev.setStyleSheet(chk_style)
        grid_layout.addWidget(chk_rev, row_idx, 4, Qt.AlignCenter)
        parent.rc_reverse_chks[rc_key] = chk_rev
        
    # Populate Buttons Mappings (ARM, DISARM, START, STOP, RTH)
    parent.btn_mapping_combos = {}
    parent.btn_auto_detect_btns = {}
    parent.btn_output_fields = {}
    
    btn_labels = {
        "arm": "ARM VEHICLE",
        "disarm": "DISARM",
        "start": "START ROUTE",
        "stop": "STOP ROUTE",
        "rth": "RETURN TO HOME",
        "light": "TOGGLE LIGHT",
        "camera": "TOGGLE CAMERA"
    }
    
    button_names = list(btn_labels.keys())
    for idx, btn_key in enumerate(button_names):
        row_idx = 4 + idx
        
        lbl_btn = QLabel(btn_labels[btn_key])
        lbl_btn.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 11px;")
        grid_layout.addWidget(lbl_btn, row_idx, 0)
        
        combo = QComboBox()
        combo.setStyleSheet(combo_style)
        combo.addItem("None", None)
        for btn_id in range(16):
            combo.addItem(f"Button {btn_id}", btn_id)
        grid_layout.addWidget(combo, row_idx, 1)
        parent.btn_mapping_combos[btn_key] = combo
        
        btn_detect = QPushButton("Auto Detect")
        btn_detect.setStyleSheet(btn_detect_style)
        btn_detect.clicked.connect(lambda checked=False, b=btn_key: parent.start_auto_detect_button(b))
        grid_layout.addWidget(btn_detect, row_idx, 2)
        parent.btn_auto_detect_btns[btn_key] = btn_detect
        
        lbl_output = QLabel("0")
        lbl_output.setAlignment(Qt.AlignCenter)
        lbl_output.setStyleSheet(output_style)
        grid_layout.addWidget(lbl_output, row_idx, 3)
        parent.btn_output_fields[btn_key] = lbl_output
        
    scroll_layout.addWidget(grid_widget)
    
    # Add Thruster limits panel directly inside Joystick Scroll Area
    thruster_widget = QWidget()
    thruster_widget.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 15px;")
    thruster_grid = QGridLayout(thruster_widget)
    thruster_grid.setSpacing(12)
    thruster_grid.setContentsMargins(10, 10, 10, 10)
    
    lbl_thruster_title = QLabel("THRUSTER SPEEDS & PWM LIMITS CONFIGURATION")
    lbl_thruster_title.setStyleSheet("color: #FFFFFF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 11px; border: none; background: transparent;")
    thruster_grid.addWidget(lbl_thruster_title, 0, 0, 1, 2)
    
    lbl_thruster_desc = QLabel("Configure the maximum and minimum speed limits (PWM pulse width in microseconds) for manual control mode. This scales joystick axis outputs to limit maximum speed and reverse thrust.")
    lbl_thruster_desc.setStyleSheet("color: #888888; font-size: 10px; border: none; background: transparent;")
    lbl_thruster_desc.setWordWrap(True)
    thruster_grid.addWidget(lbl_thruster_desc, 1, 0, 1, 2)
    
    lbl_min = QLabel("Minimum PWM Speed Limit (us):")
    lbl_min.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: bold; border: none; background: transparent;")
    parent.input_thruster_min = QLineEdit(str(parent.thruster_min_limit))
    parent.input_thruster_min.setStyleSheet("QLineEdit { background-color: #121212; border: 1px solid #333333; border-radius: 2px; color: #FFFFFF; padding: 5px; font-family: 'Google Sans', sans-serif; font-size: 11px; }")
    
    thruster_grid.addWidget(lbl_min, 2, 0)
    thruster_grid.addWidget(parent.input_thruster_min, 2, 1)
    
    lbl_max = QLabel("Maximum PWM Speed Limit (us):")
    lbl_max.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: bold; border: none; background: transparent;")
    parent.input_thruster_max = QLineEdit(str(parent.thruster_max_limit))
    parent.input_thruster_max.setStyleSheet("QLineEdit { background-color: #121212; border: 1px solid #333333; border-radius: 2px; color: #FFFFFF; padding: 5px; font-family: 'Google Sans', sans-serif; font-size: 11px; }")
    
    thruster_grid.addWidget(lbl_max, 3, 0)
    thruster_grid.addWidget(parent.input_thruster_max, 3, 1)
    
    parent.btn_thruster_set = QPushButton("Set Limits")
    parent.btn_thruster_set.setStyleSheet("""
        QPushButton {
            background-color: #8BC34A;
            border: none;
            border-radius: 2px;
            color: #000000;
            font-weight: bold;
            font-size: 11px;
            padding: 6px 15px;
        }
        QPushButton:hover {
            background-color: #9CCC65;
        }
    """)
    parent.btn_thruster_set.clicked.connect(parent.set_thruster_limits)
    thruster_grid.addWidget(parent.btn_thruster_set, 4, 1, Qt.AlignRight)
    
    parent.lbl_thruster_feedback = QLabel("")
    parent.lbl_thruster_feedback.setStyleSheet("color: #8BC34A; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
    thruster_grid.addWidget(parent.lbl_thruster_feedback, 4, 0)
    
    scroll_layout.addWidget(thruster_widget)
    
    scroll_layout.addStretch()
    
    scroll.setWidget(scroll_content)
    joystick_layout.addWidget(scroll)
    
    # Create Light Page
    light_page = QWidget()
    light_page_layout = QVBoxLayout(light_page)
    light_page_layout.setContentsMargins(15, 15, 15, 15)
    light_page_layout.setSpacing(15)
    
    # Equipment Controls Panel (LIGHT & CAMERA toggles)
    payload_widget = QWidget()
    payload_widget.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 15px;")
    payload_layout = QVBoxLayout(payload_widget)
    payload_layout.setSpacing(10)
    
    lbl_payload_title = QLabel("Equipment Control")
    lbl_payload_title.setStyleSheet("color: #00E5FF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 11px; border: none; background: transparent; text-transform: uppercase;")
    payload_layout.addWidget(lbl_payload_title)
    
    buttons_row = QHBoxLayout()
    buttons_row.setSpacing(15)
    
    parent.btn_light_toggle = QPushButton("LIGHT: OFF")
    parent.btn_light_toggle.setStyleSheet(parent.blue_btn_style)
    parent.btn_light_toggle.setCheckable(True)
    parent.btn_light_toggle.clicked.connect(parent.toggle_light)
    buttons_row.addWidget(parent.btn_light_toggle)
    
    parent.btn_camera_toggle = QPushButton("CAMERA: OFF")
    parent.btn_camera_toggle.setStyleSheet(parent.blue_btn_style)
    parent.btn_camera_toggle.setCheckable(True)
    parent.btn_camera_toggle.clicked.connect(parent.toggle_camera)
    buttons_row.addWidget(parent.btn_camera_toggle)
    buttons_row.addStretch()
    
    payload_layout.addLayout(buttons_row)
    light_page_layout.addWidget(payload_widget)
    light_page_layout.addStretch()

    # Create PID Page
    pid_page = QWidget()
    pid_page_layout = QVBoxLayout(pid_page)
    pid_page_layout.setContentsMargins(15, 15, 15, 15)
    pid_page_layout.setSpacing(15)
    
    pid_scroll = QScrollArea()
    pid_scroll.setWidgetResizable(True)
    pid_scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
    
    pid_content = QWidget()
    pid_content.setStyleSheet("background-color: transparent;")
    pid_content_layout = QVBoxLayout(pid_content)
    pid_content_layout.setContentsMargins(5, 5, 5, 5)
    pid_content_layout.setSpacing(15)
    
    line_edit_style = "QLineEdit { background-color: #121212; border: 1px solid #333333; border-radius: 3px; color: #FFFFFF; padding: 6px 10px; font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; min-width: 120px; } QLineEdit:focus { border-color: #0078D4; }"
    label_style = "color: #FFFFFF; font-size: 11px; font-weight: bold; border: none; background: transparent; font-family: 'Google Sans', sans-serif;"
    
    # 0. Configuration Mode Header Panel
    cfg_panel = QWidget()
    cfg_panel.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 15px;")
    cfg_layout = QVBoxLayout(cfg_panel)
    cfg_layout.setSpacing(12)
    
    lbl_cfg_title = QLabel("PID CONFIGURATION MODE")
    lbl_cfg_title.setStyleSheet("color: #00E5FF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 11px; border: none; background: transparent; letter-spacing: 0.5px;")
    cfg_layout.addWidget(lbl_cfg_title)
    
    lbl_cfg_desc = QLabel("Turn ON configuration mode (Mode 2) to unlock and transmit PID parameters to the vessel. When done, click Exit Configuration to return to navigation mode.")
    lbl_cfg_desc.setStyleSheet("color: #888888; font-size: 10px; border: none; background: transparent; font-family: 'Google Sans', sans-serif;")
    lbl_cfg_desc.setWordWrap(True)
    cfg_layout.addWidget(lbl_cfg_desc)
    
    cfg_btns_row = QHBoxLayout()
    cfg_btns_row.setSpacing(15)
    
    is_cfg_init = getattr(parent, 'is_configuration_mode', False)
    parent.btn_config_mode_toggle = QPushButton("CONFIGURATION: ON (MODE 2)" if is_cfg_init else "CONFIGURATION: OFF")
    parent.btn_config_mode_toggle.setCheckable(True)
    parent.btn_config_mode_toggle.setChecked(is_cfg_init)
    if is_cfg_init:
        parent.btn_config_mode_toggle.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                border: 1px solid #2B88D8;
                border-radius: 3px;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 18px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
        """)
    else:
        parent.btn_config_mode_toggle.setStyleSheet("""
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
    parent.btn_config_mode_toggle.clicked.connect(lambda: toggle_config_mode(parent))
    cfg_btns_row.addWidget(parent.btn_config_mode_toggle)
    
    parent.btn_exit_config_mode = QPushButton("EXIT CONFIGURATION")
    parent.btn_exit_config_mode.setStyleSheet("""
        QPushButton {
            background-color: #C62828;
            border: none;
            border-radius: 3px;
            color: #FFFFFF;
            font-weight: bold;
            font-size: 11px;
            padding: 8px 18px;
        }
        QPushButton:hover {
            background-color: #D32F2F;
        }
    """)
    parent.btn_exit_config_mode.clicked.connect(lambda: exit_config_mode(parent))
    cfg_btns_row.addWidget(parent.btn_exit_config_mode)
    
    prev_mode_str = "0 (Manual)" if getattr(parent, 'btn_manual', None) and parent.btn_manual.isChecked() else "1 (Automatic)"
    parent.lbl_config_mode_status = QLabel("● Active (Mode 2 - Tuning Enabled)" if is_cfg_init else f"○ Inactive (Mode {prev_mode_str})")
    parent.lbl_config_mode_status.setStyleSheet("color: #00E5FF;" if is_cfg_init else "color: #888888;" + " font-family: 'Google Sans', sans-serif; font-size: 11px; font-weight: bold; border: none; background: transparent;")
    cfg_btns_row.addWidget(parent.lbl_config_mode_status)
    cfg_btns_row.addStretch()
    
    cfg_layout.addLayout(cfg_btns_row)
    pid_content_layout.addWidget(cfg_panel)
    
    # 1. Linear PID Panel
    lin_widget = QWidget()
    lin_widget.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 15px;")
    lin_layout = QVBoxLayout(lin_widget)
    lin_layout.setSpacing(12)
    
    lbl_lin_title = QLabel("LINEAR PID TUNING (POSITION / VELOCITY)")
    lbl_lin_title.setStyleSheet("color: #00E5FF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 11px; border: none; background: transparent; letter-spacing: 0.5px;")
    lin_layout.addWidget(lbl_lin_title)
    
    lbl_lin_desc = QLabel("Configure the Proportional (Kp), Integral (Ki), and Derivative (Kd) gains for vessel linear translation and distance error tracking.")
    lbl_lin_desc.setStyleSheet("color: #888888; font-size: 10px; border: none; background: transparent; font-family: 'Google Sans', sans-serif;")
    lbl_lin_desc.setWordWrap(True)
    lin_layout.addWidget(lbl_lin_desc)
    
    lin_grid = QGridLayout()
    lin_grid.setSpacing(10)
    lin_grid.setContentsMargins(5, 5, 5, 5)
    
    lbl_lkp = QLabel("Linear Kp (Proportional):")
    lbl_lkp.setStyleSheet(label_style)
    parent.input_linear_kp = QLineEdit(str(getattr(parent, 'linear_kp', 0.0)))
    parent.input_linear_kp.setStyleSheet(line_edit_style)
    lin_grid.addWidget(lbl_lkp, 0, 0)
    lin_grid.addWidget(parent.input_linear_kp, 0, 1)
    
    lbl_lki = QLabel("Linear Ki (Integral):")
    lbl_lki.setStyleSheet(label_style)
    parent.input_linear_ki = QLineEdit(str(getattr(parent, 'linear_ki', 0.0)))
    parent.input_linear_ki.setStyleSheet(line_edit_style)
    lin_grid.addWidget(lbl_lki, 1, 0)
    lin_grid.addWidget(parent.input_linear_ki, 1, 1)
    
    lbl_lkd = QLabel("Linear Kd (Derivative):")
    lbl_lkd.setStyleSheet(label_style)
    parent.input_linear_kd = QLineEdit(str(getattr(parent, 'linear_kd', 0.0)))
    parent.input_linear_kd.setStyleSheet(line_edit_style)
    lin_grid.addWidget(lbl_lkd, 2, 0)
    lin_grid.addWidget(parent.input_linear_kd, 2, 1)
    
    lin_layout.addLayout(lin_grid)
    pid_content_layout.addWidget(lin_widget)
    
    # 2. Angular PID Panel
    ang_widget = QWidget()
    ang_widget.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 15px;")
    ang_layout = QVBoxLayout(ang_widget)
    ang_layout.setSpacing(12)
    
    lbl_ang_title = QLabel("ANGULAR PID TUNING (HEADING / YAW)")
    lbl_ang_title.setStyleSheet("color: #00E5FF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 11px; border: none; background: transparent; letter-spacing: 0.5px;")
    ang_layout.addWidget(lbl_ang_title)
    
    lbl_ang_desc = QLabel("Configure the Proportional (Kp), Integral (Ki), and Derivative (Kd) gains for vessel yaw orientation and heading correction.")
    lbl_ang_desc.setStyleSheet("color: #888888; font-size: 10px; border: none; background: transparent; font-family: 'Google Sans', sans-serif;")
    lbl_ang_desc.setWordWrap(True)
    ang_layout.addWidget(lbl_ang_desc)
    
    ang_grid = QGridLayout()
    ang_grid.setSpacing(10)
    ang_grid.setContentsMargins(5, 5, 5, 5)
    
    lbl_akp = QLabel("Angular Kp (Proportional):")
    lbl_akp.setStyleSheet(label_style)
    parent.input_angular_kp = QLineEdit(str(getattr(parent, 'angular_kp', 0.0)))
    parent.input_angular_kp.setStyleSheet(line_edit_style)
    ang_grid.addWidget(lbl_akp, 0, 0)
    ang_grid.addWidget(parent.input_angular_kp, 0, 1)
    
    lbl_aki = QLabel("Angular Ki (Integral):")
    lbl_aki.setStyleSheet(label_style)
    parent.input_angular_ki = QLineEdit(str(getattr(parent, 'angular_ki', 0.0)))
    parent.input_angular_ki.setStyleSheet(line_edit_style)
    ang_grid.addWidget(lbl_aki, 1, 0)
    ang_grid.addWidget(parent.input_angular_ki, 1, 1)
    
    lbl_akd = QLabel("Angular Kd (Derivative):")
    lbl_akd.setStyleSheet(label_style)
    parent.input_angular_kd = QLineEdit(str(getattr(parent, 'angular_kd', 0.0)))
    parent.input_angular_kd.setStyleSheet(line_edit_style)
    ang_grid.addWidget(lbl_akd, 2, 0)
    ang_grid.addWidget(parent.input_angular_kd, 2, 1)
    
    ang_layout.addLayout(ang_grid)
    pid_content_layout.addWidget(ang_widget)
    
    # 3. AHRS Offset Configuration Panel
    ahrs_widget = QWidget()
    ahrs_widget.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 15px;")
    ahrs_layout = QVBoxLayout(ahrs_widget)
    ahrs_layout.setSpacing(12)
    
    lbl_ahrs_title = QLabel("AHRS OFFSET & HEADING CALIBRATION")
    lbl_ahrs_title.setStyleSheet("color: #00E5FF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 11px; border: none; background: transparent; letter-spacing: 0.5px;")
    ahrs_layout.addWidget(lbl_ahrs_title)
    
    lbl_ahrs_desc = QLabel("Configure the AHRS yaw/heading offset value (in degrees) to fix sensor heading orientation, eliminate mounting bias, and calibrate true north reference.")
    lbl_ahrs_desc.setStyleSheet("color: #888888; font-size: 10px; border: none; background: transparent; font-family: 'Google Sans', sans-serif;")
    lbl_ahrs_desc.setWordWrap(True)
    ahrs_layout.addWidget(lbl_ahrs_desc)
    
    ahrs_row = QHBoxLayout()
    ahrs_row.setSpacing(10)
    
    lbl_aoff = QLabel("AHRS Offset (° / deg):")
    lbl_aoff.setStyleSheet(label_style)
    ahrs_row.addWidget(lbl_aoff)
    
    parent.input_ahrs_offset = QLineEdit(str(getattr(parent, 'ahrs_offset', 0.0)))
    parent.input_ahrs_offset.setStyleSheet(line_edit_style)
    ahrs_row.addWidget(parent.input_ahrs_offset)
    
    btn_fix_current_yaw = QPushButton("FIX CURRENT HEADING")
    btn_fix_current_yaw.setStyleSheet("""
        QPushButton {
            background-color: #0078D4;
            border: none;
            border-radius: 3px;
            color: #FFFFFF;
            font-weight: bold;
            font-size: 10px;
            padding: 6px 14px;
        }
        QPushButton:hover {
            background-color: #106EBE;
        }
    """)
    def fix_current_heading():
        curr_yaw = getattr(parent, 'last_yaw', 0.0)
        parent.input_ahrs_offset.setText(f"{curr_yaw:.2f}")
    btn_fix_current_yaw.clicked.connect(fix_current_heading)
    ahrs_row.addWidget(btn_fix_current_yaw)
    
    btn_zero_offset = QPushButton("ZERO (0.0°)")
    btn_zero_offset.setStyleSheet("""
        QPushButton {
            background-color: #2D2D2D;
            border: 1px solid #444444;
            border-radius: 3px;
            color: #CCCCCC;
            font-weight: bold;
            font-size: 10px;
            padding: 6px 14px;
        }
        QPushButton:hover {
            background-color: #383838;
            color: #FFFFFF;
        }
    """)
    btn_zero_offset.clicked.connect(lambda: parent.input_ahrs_offset.setText("0.0"))
    ahrs_row.addWidget(btn_zero_offset)
    
    ahrs_row.addStretch()
    ahrs_layout.addLayout(ahrs_row)
    pid_content_layout.addWidget(ahrs_widget)
    
    # 4. Actions and Feedback Panel
    action_widget = QWidget()
    action_widget.setStyleSheet("background-color: #1A1A1A; border: 1px solid #333333; border-radius: 4px; padding: 15px;")
    action_layout = QVBoxLayout(action_widget)
    action_layout.setSpacing(12)
    
    lbl_tx_title = QLabel("TELEMETRY TRANSMISSION & LIVE PACKET")
    lbl_tx_title.setStyleSheet("color: #00E5FF; font-weight: bold; font-family: 'Google Sans', sans-serif; font-size: 11px; border: none; background: transparent; letter-spacing: 0.5px;")
    action_layout.addWidget(lbl_tx_title)
    
    action_row = QHBoxLayout()
    action_row.setSpacing(15)
    
    parent.btn_send_pid = QPushButton("SEND")
    parent.btn_send_pid.setEnabled(is_cfg_init)
    if is_cfg_init:
        parent.btn_send_pid.setStyleSheet("""
            QPushButton {
                background-color: #8BC34A;
                border: none;
                border-radius: 3px;
                color: #000000;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 25px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #9CCC65;
            }
        """)
    else:
        parent.btn_send_pid.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: none;
                border-radius: 3px;
                color: #777777;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 25px;
                min-width: 100px;
            }
        """)
    parent.btn_send_pid.clicked.connect(lambda: send_pid_config(parent))
    action_row.addWidget(parent.btn_send_pid)
    
    parent.lbl_pid_feedback = QLabel("" if is_cfg_init else "Configuration mode is OFF. Turn ON configuration to send parameters.")
    parent.lbl_pid_feedback.setStyleSheet("color: #888888; font-family: 'Google Sans', sans-serif; font-size: 11px; font-style: italic; border: none; background: transparent;")
    action_row.addWidget(parent.lbl_pid_feedback, 1)
    
    action_layout.addLayout(action_row)
    
    lbl_fmt_desc = QLabel("Transmitted Telemetry Format:\n[manual(0)orauto(1)orconfig(2), stop(0)orstart(1), no.of waypoints, [waypoints], [linearkp,ki,kd], [angularkp,ki,kd], pwm1, pwm2, pwm3, lightstatus(0 or 1), camera_status(0 or 1), ahrs_offset]")
    lbl_fmt_desc.setStyleSheet("color: #777777; font-family: 'Google Sans', monospace; font-size: 9.5px; border: none; background: transparent;")
    lbl_fmt_desc.setWordWrap(True)
    action_layout.addWidget(lbl_fmt_desc)
    
    init_preview = parent.build_command_payload() if hasattr(parent, 'build_command_payload') else ""
    parent.lbl_pid_preview = QLabel(init_preview)
    parent.lbl_pid_preview.setStyleSheet("color: #8BC34A; background-color: #121212; border: 1px solid #282828; border-radius: 3px; font-family: 'Google Sans', monospace; font-size: 10px; padding: 6px;")
    parent.lbl_pid_preview.setWordWrap(True)
    action_layout.addWidget(parent.lbl_pid_preview)
    
    # Real-time preview update as user inputs changes
    def update_live_preview():
        try:
            parent.linear_kp = float(parent.input_linear_kp.text().strip())
            parent.linear_ki = float(parent.input_linear_ki.text().strip())
            parent.linear_kd = float(parent.input_linear_kd.text().strip())
            parent.angular_kp = float(parent.input_angular_kp.text().strip())
            parent.angular_ki = float(parent.input_angular_ki.text().strip())
            parent.angular_kd = float(parent.input_angular_kd.text().strip())
            parent.ahrs_offset = float(parent.input_ahrs_offset.text().strip())
            if hasattr(parent, 'lbl_pid_preview'):
                parent.lbl_pid_preview.setText(parent.build_command_payload())
        except (ValueError, TypeError):
            pass

    parent.input_linear_kp.textChanged.connect(update_live_preview)
    parent.input_linear_ki.textChanged.connect(update_live_preview)
    parent.input_linear_kd.textChanged.connect(update_live_preview)
    parent.input_angular_kp.textChanged.connect(update_live_preview)
    parent.input_angular_ki.textChanged.connect(update_live_preview)
    parent.input_angular_kd.textChanged.connect(update_live_preview)
    parent.input_ahrs_offset.textChanged.connect(update_live_preview)
    
    pid_content_layout.addWidget(action_widget)
    pid_content_layout.addStretch()
    
    pid_scroll.setWidget(pid_content)
    pid_page_layout.addWidget(pid_scroll)

    # Instantiate original members as hidden so other logic works
    parent.bar_throttle = QProgressBar()
    parent.bar_steering = QProgressBar()
    parent.bar_pitch = QProgressBar()
    
    parent.load_joystick_config()
    
    # Add pages to stacked widget
    parent.setup_stacked.addWidget(joystick_page)
    parent.setup_stacked.addWidget(light_page)
    parent.setup_stacked.addWidget(pid_page)
    parent.setup_stacked.setCurrentIndex(0)
    
    # Connect menu click slots
    parent.btn_menu_joystick.clicked.connect(parent.select_joystick_setup)
    parent.btn_menu_light.clicked.connect(parent.select_light_setup)
    parent.btn_menu_pid.clicked.connect(parent.select_pid_setup)
    
    return page
