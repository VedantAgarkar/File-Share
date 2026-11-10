# main.py
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.ui.qt_ui import LocalDropQtUI
from src.config import QSS_THEME

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS_THEME)

    window = LocalDropQtUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
