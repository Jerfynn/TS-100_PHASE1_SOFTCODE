import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon
from src.app import MarineGroundStation

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion') # Use clean Fusion style as baseline for our custom theme
    app.setFont(QFont("Google Sans", 9))
    
    # Resolve icon path whether in dev or PyInstaller bundle
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, "app_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(base_dir, "src", "app_icon.png")
        
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
    
    window = MarineGroundStation()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.setWindowTitle("Trinetra Marine GCS - Ground Control Station")
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()