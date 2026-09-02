# Ocean Theme Stylesheet for Marine Ground Station

# Theme Color Palette Reference:
# Deep Ocean Abyss: #050B14
# Ocean Dark Blue: #0A1625
# Card Background: #0F223C
# Card Hover BG:   #152F53
# Border Base:      #1C3B65
# Glow Cyan Accent: #00E5FF
# Text Primary:     #E2F1FF
# Text Secondary:   #8EB7E6
# Connect Standby:  #007A99
# Connected Active: #00E676

OCEAN_STYLESHEET = """
QMainWindow {
    background-color: #050B14;
}

/* ScrollBars */
QScrollBar:vertical {
    border: none;
    background: #0A1625;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #1C3B65;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #00E5FF;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    border: none;
    background: none;
}

QScrollBar:horizontal {
    border: none;
    background: #0A1625;
    height: 8px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #1C3B65;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #00E5FF;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    border: none;
    background: none;
}

/* Top Bar Frame */
#TopBarFrame {
    background-color: #0A1625;
    border-bottom: 2px solid #1C3B65;
    min-height: 42px;
    max-height: 42px;
}

/* Clock and Logo */
#ClockLabel {
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Google Sans', sans-serif;
    letter-spacing: 0.5px;
    padding-left: 10px;
}

#TopBarGpsLabel {
    color: #8EB7E6;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Google Sans', sans-serif;
    border-left: 1px solid #1C3B65;
    padding-left: 10px;
    margin-left: 10px;
}

#TopBarBatteryLabel {
    color: #8EB7E6;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Google Sans', sans-serif;
    border-left: 1px solid #1C3B65;
    padding-left: 10px;
    margin-left: 10px;
}

#TopBarTempLabel {
    color: #8EB7E6;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Google Sans', sans-serif;
    border-left: 1px solid #1C3B65;
    padding-left: 10px;
    margin-left: 10px;
}


#LogoLabel {
    color: #E2F1FF;
    font-size: 14px;
    font-weight: 800;
    font-family: 'Google Sans', sans-serif;
    letter-spacing: 1.5px;
    padding-left: 10px;
}

/* Top Bar Controls */
QLabel.TopBarControlLabel {
    color: #8EB7E6;
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
}

QComboBox {
    background-color: #0F223C;
    border: 1px solid #1C3B65;
    border-radius: 4px;
    padding: 4px 8px;
    color: #E2F1FF;
    font-weight: 500;
    font-size: 11px;
    min-width: 95px;
}

QComboBox:hover {
    border-color: #00E5FF;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border-left: 1px solid #1C3B65;
}

QComboBox::down-arrow {
    image: url(src/down_arrow.png);
    width: 10px;
    height: 10px;
}

QComboBox QAbstractItemView {
    background-color: #0A1625;
    border: 1px solid #1C3B65;
    selection-background-color: #152F53;
    selection-color: #00E5FF;
    color: #E2F1FF;
    outline: 0px;
    padding: 4px;
}

/* Buttons */
QPushButton {
    background-color: #0F223C;
    border: 1px solid #1C3B65;
    border-radius: 4px;
    padding: 4px 12px;
    color: #E2F1FF;
    font-weight: bold;
    font-size: 11px;
}

QPushButton:hover {
    background-color: #152F53;
    border-color: #00E5FF;
    color: #00E5FF;
}

QPushButton:pressed {
    background-color: #0A1625;
}

/* Connect / Disconnect specific styling */
QPushButton#ConnectButton {
    background-color: #004D61;
    border: 1px solid #007A99;
    color: #FFFFFF;
}

QPushButton#ConnectButton:hover {
    background-color: #007A99;
    border-color: #00E5FF;
}

QPushButton#ConnectButton[status="disconnected"] {
    background-color: #004D61;
    border: 1px solid #007A99;
    color: #FFFFFF;
}

QPushButton#ConnectButton[status="connecting"] {
    background-color: #3E2723;
    border: 1px solid #FFC107;
    color: #FFC107;
}

QPushButton#ConnectButton[status="connecting"]:hover {
    background-color: #4E342E;
    border-color: #FFD54F;
}

QPushButton#ConnectButton[status="connected"] {
    background-color: #1B5E20;
    border: 1px solid #00E676;
    color: #FFFFFF;
}

QPushButton#ConnectButton[status="connected"]:hover {
    background-color: #2E7D32;
    border-color: #00E676;
}

/* Telemetry Cards */
QFrame#TelemetryCard {
    background-color: #0F223C;
    border: 1px solid #1C3B65;
    border-radius: 10px;
}

QFrame#TelemetryCard:hover {
    border-color: #00E5FF;
    background-color: #122846;
}

QFrame#TelemetryCard[status="connected"] {
    border-color: #00B5CC;
}

QFrame#TelemetryCard[status="connecting"] {
    border-color: #FFC107;
}


QLabel#CardTitle {
    color: #8EB7E6;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}

QLabel#CardValue {
    color: #FFFFFF;
    font-size: 28px;
    font-weight: 800;
    font-family: 'Google Sans', sans-serif;
}

QLabel#CardUnit {
    color: #00E5FF;
    font-size: 11px;
    font-weight: 600;
}

/* Connection Status Ribbon/Indicator */
#StatusPanel {
    background-color: #0F223C;
    border-radius: 4px;
    border: 1px solid #1C3B65;
}

#StatusLED {
    background-color: #FF1744; /* Default offline red */
    border-radius: 4px;
    min-width: 8px;
    max-width: 8px;
    min-height: 8px;
    max-height: 8px;
}

#StatusLED[status="disconnected"] {
    background-color: #FF1744;
}

#StatusLED[status="connecting"] {
    background-color: #FFC107;
}

#StatusLED[status="connected"] {
    background-color: #00E676;
}

#StatusLabel {
    color: #FF1744;
    font-weight: bold;
    font-size: 10px;
    text-transform: uppercase;
}

#StatusLabel[status="disconnected"] {
    color: #FF1744;
}

#StatusLabel[status="connecting"] {
    color: #FFC107;
}

#StatusLabel[status="connected"] {
    color: #00E676;
}

/* Sidebar Styling */
#SidebarFrame {
    background-color: #0A1625;
    border-right: 1px solid #1C3B65;
    min-width: 50px;
    max-width: 50px;
}

QPushButton#SidebarButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    min-height: 40px;
    max-height: 40px;
    min-width: 40px;
    max-width: 40px;
    margin: 5px;
    padding: 0px;
}

QPushButton#SidebarButton:hover {
    background-color: #122846;
}

QPushButton#SidebarButton:checked {
    background-color: #1C3B65;
}

/* Inner Labels */
QLabel#SidebarBtnIcon {
    font-family: 'Google Sans', 'Segoe UI Symbol', 'Segoe UI Emoji', sans-serif;
    font-size: 18px;
    color: #6A89B0; /* Dim light blue on standby */
}

QPushButton#SidebarButton:hover QLabel#SidebarBtnIcon {
    color: #00E5FF;
}

QPushButton#SidebarButton:checked QLabel#SidebarBtnIcon {
    color: #FFFFFF; /* Bright white on selected */
}

/* Cockpit Telemetry Cards Override styling */
QFrame#TelemetryCard[theme="cockpit"] {
    background-color: #1A1A1A;
    border: 1px solid #333333;
    border-radius: 6px;
}

QFrame#TelemetryCard[theme="cockpit"]:hover {
    border-color: #FF9100;
    background-color: #242424;
}

QFrame#TelemetryCard[theme="cockpit"] QLabel#CardTitle {
    color: #A0A0A0;
}

QFrame#TelemetryCard[theme="cockpit"] QLabel#CardValue {
    color: #FFFFFF;
}

QFrame#TelemetryCard[theme="cockpit"] QLabel#CardUnit {
    color: #FF9100;
}

QPushButton#MultiMonButton {
    background-color: #2E1A47;
    border: 1px solid #512DA8;
    color: #E0E0E0;
    font-weight: bold;
    padding: 2px 10px;
    border-radius: 4px;
}

QPushButton#MultiMonButton:hover {
    background-color: #512DA8;
    border-color: #7E57C2;
    color: #FFFFFF;
}
"""

