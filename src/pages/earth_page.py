import os
from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QFrame, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from src.widgets import MarineHorizon, MarineCompass

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

def create_earth_page(parent):
    page = QWidget()
    
    # Grid layout allowing multiple widgets to occupy the same cell (0, 0)
    grid_layout = QGridLayout(page)
    grid_layout.setContentsMargins(0, 0, 0, 0)
    
    # 1. Fullscreen Web View Map
    parent.web_view = QWebEngineView()
    parent.web_page = ConsoleWebEnginePage(parent.web_view)
    parent.web_view.setPage(parent.web_page)
    
    # Read HTML content and set
    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "map.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        parent.web_view.setHtml(html_content)
        parent.web_view.loadFinished.connect(
            lambda ok: parent.web_view.page().runJavaScript(f"setVesselIcon('{parent.vessel_icon_type}');") if ok else None
        )
    except Exception as e:
        print(f"Error loading map.html: {e}")
        
    grid_layout.addWidget(parent.web_view, 0, 0)
    
    # 2. Top-Left Overlay Panel for Map Tools (Clear Trail)
    tools_panel = QFrame()
    tools_panel.setStyleSheet("""
        QFrame {
            background: transparent;
            border: none;
            padding: 0px;
            margin: 20px;
        }
    """)
    tools_layout = QHBoxLayout(tools_panel)
    tools_layout.setContentsMargins(0, 0, 0, 0)
    tools_layout.setSpacing(10)
    
    def clear_earth_trail():
        if hasattr(parent, 'web_view') and parent.web_view:
            parent.web_view.page().runJavaScript("clearTrack();")
            print("[Earth Map] Vessel navigation trail cleared.")
            if hasattr(parent, 'show_toast_alert'):
                parent.show_toast_alert("Vessel navigation trail cleared", is_critical=False)

    parent.btn_earth_clear_trail = QPushButton("CLEAR TRAIL")
    parent.btn_earth_clear_trail.setStyleSheet("""
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
    parent.btn_earth_clear_trail.clicked.connect(clear_earth_trail)
    tools_layout.addWidget(parent.btn_earth_clear_trail)
    
    grid_layout.addWidget(tools_panel, 0, 0, Qt.AlignTop | Qt.AlignLeft)
    
    # 3. Overlay Panel for circular instruments (Horizon + Compass)
    overlay_panel = QFrame()
    overlay_panel.setStyleSheet("""
        QFrame {
            background: transparent;
            border: none;
            padding: 0px;
            margin: 20px; /* Offset from top-right window borders */
        }
    """)
    
    overlay_layout = QVBoxLayout(overlay_panel)
    overlay_layout.setContentsMargins(0, 0, 0, 0)
    overlay_layout.setSpacing(15)
    
    # Horizon Indicator (Enlarged to 190x190 for ~5cm diameter)
    parent.map_horizon = MarineHorizon(theme="cockpit")
    parent.map_horizon.setFixedSize(190, 190)
    
    # Compass Indicator (Enlarged to 190x190 for ~5cm diameter)
    parent.map_compass = MarineCompass(theme="cockpit")
    parent.map_compass.setFixedSize(190, 190)
    
    overlay_layout.addWidget(parent.map_horizon)
    overlay_layout.addWidget(parent.map_compass)
    
    # Align overlay panel to the Top Right corner of the map grid cell
    grid_layout.addWidget(overlay_panel, 0, 0, Qt.AlignTop | Qt.AlignRight)
    
    return page
