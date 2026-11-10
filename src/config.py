# src/config.py

DEFAULT_PORT = 8000
CHUNK_SIZE = 256 * 1024  # 256 KB streaming buffer
MDNS_SERVICE_TYPE = "_localdrop._tcp.local."
APP_NAME = "LocalDrop"
VERSION = "3.1.0"

# Rate limiting
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SEC = 30

# Modern Dark Theme Stylesheet (Qt6 QSS)
QSS_DARK = """
QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #21262d;
    background-color: #161b22;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background: #0d1117;
    color: #8b949e;
    padding: 10px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #161b22;
    color: #58a6ff;
    border-bottom: 2px solid #58a6ff;
}

QTabBar::tab:hover:!selected {
    color: #c9d1d9;
    background: #161b22;
}

QFrame.card {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 14px;
}

QFrame.drop-zone {
    background-color: #161b22;
    border: 2px dashed #30363d;
    border-radius: 12px;
}

QFrame.drop-zone:hover {
    border-color: #58a6ff;
    background-color: #1a222d;
}

QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 9px 15px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #8b949e;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #161b22;
}

QPushButton.primary {
    background-color: #1f6feb;
    border: 1px solid #388bfd;
    color: #ffffff;
}

QPushButton.primary:hover {
    background-color: #388bfd;
}

QPushButton.success {
    background-color: #238636;
    border: 1px solid #2ea043;
    color: #ffffff;
}

QPushButton.success:hover {
    background-color: #2ea043;
}

QPushButton.danger {
    background-color: #da3633;
    border: 1px solid #f85149;
    color: #ffffff;
}

QPushButton.danger:hover {
    background-color: #b62324;
}

QPushButton.icon-btn {
    background-color: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}

QPushButton.icon-btn:hover {
    background-color: #30363d;
}

QLineEdit, QTextEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e6edf3;
    selection-background-color: #1f6feb;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #58a6ff;
}

QComboBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e6edf3;
}

QComboBox:drop-down {
    border: 0px;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    color: #e6edf3;
    selection-background-color: #1f6feb;
    border: 1px solid #30363d;
}

QProgressBar {
    border: 1px solid #30363d;
    border-radius: 6px;
    text-align: center;
    background-color: #0d1117;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #238636;
    border-radius: 5px;
}

QCheckBox {
    color: #c9d1d9;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #30363d;
    border-radius: 4px;
    background-color: #0d1117;
}

QCheckBox::indicator:checked {
    background-color: #1f6feb;
    border-color: #58a6ff;
}

QListWidget {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 6px;
}

QListWidget::item {
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 4px;
    background-color: #0d1117;
}

QListWidget::item:hover {
    background-color: #21262d;
}

QListWidget::item:selected {
    background-color: #1f6feb;
    color: #ffffff;
}

QScrollBar:vertical {
    border: none;
    background: #0d1117;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #30363d;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #8b949e;
}
"""

# Modern Light Theme Stylesheet (Qt6 QSS)
QSS_LIGHT = """
QWidget {
    background-color: #f6f8fa;
    color: #1f2328;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #d0d7de;
    background-color: #ffffff;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background: #f6f8fa;
    color: #656d76;
    padding: 10px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #0969da;
    border-bottom: 2px solid #0969da;
}

QTabBar::tab:hover:!selected {
    color: #1f2328;
    background: #ffffff;
}

QFrame.card {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 12px;
    padding: 14px;
}

QFrame.drop-zone {
    background-color: #ffffff;
    border: 2px dashed #d0d7de;
    border-radius: 12px;
}

QFrame.drop-zone:hover {
    border-color: #0969da;
    background-color: #f0f6fc;
}

QPushButton {
    background-color: #f6f8fa;
    color: #24292f;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 9px 15px;
    font-weight: 600;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #eaeef2;
    border-color: #afb8c1;
    color: #1f2328;
}

QPushButton:pressed {
    background-color: #d0d7de;
}

QPushButton.primary {
    background-color: #0969da;
    border: 1px solid #0550ae;
    color: #ffffff;
}

QPushButton.primary:hover {
    background-color: #0550ae;
}

QPushButton.success {
    background-color: #1a7f37;
    border: 1px solid #116329;
    color: #ffffff;
}

QPushButton.success:hover {
    background-color: #116329;
}

QPushButton.danger {
    background-color: #cf222e;
    border: 1px solid #a40e26;
    color: #ffffff;
}

QPushButton.danger:hover {
    background-color: #a40e26;
}

QPushButton.icon-btn {
    background-color: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}

QPushButton.icon-btn:hover {
    background-color: #eaeef2;
}

QLineEdit, QTextEdit {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 8px 12px;
    color: #1f2328;
    selection-background-color: #0969da;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #0969da;
}

QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 12px;
    color: #1f2328;
}

QComboBox:drop-down {
    border: 0px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1f2328;
    selection-background-color: #0969da;
    selection-color: #ffffff;
    border: 1px solid #d0d7de;
}

QProgressBar {
    border: 1px solid #d0d7de;
    border-radius: 6px;
    text-align: center;
    background-color: #eaeef2;
    color: #1f2328;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #1a7f37;
    border-radius: 5px;
}

QCheckBox {
    color: #1f2328;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1px solid #d0d7de;
    border-radius: 4px;
    background-color: #ffffff;
}

QCheckBox::indicator:checked {
    background-color: #0969da;
    border-color: #0550ae;
}

QListWidget {
    background-color: #ffffff;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 6px;
}

QListWidget::item {
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 4px;
    background-color: #f6f8fa;
    color: #1f2328;
}

QListWidget::item:hover {
    background-color: #eaeef2;
}

QListWidget::item:selected {
    background-color: #0969da;
    color: #ffffff;
}

QScrollBar:vertical {
    border: none;
    background: #f6f8fa;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #d0d7de;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #afb8c1;
}
"""

QSS_THEME = QSS_DARK
