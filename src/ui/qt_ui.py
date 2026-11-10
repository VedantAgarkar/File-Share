# src/ui/qt_ui.py
import os
import sys
import threading
import socket
import qrcode
from PIL import Image

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QFrame, QFileDialog, QLineEdit,
    QProgressBar, QCheckBox, QComboBox, QTextEdit, QMessageBox,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QPixmap, QImage, QDragEnterEvent, QDropEvent, QFont

from src.config import DEFAULT_PORT, QSS_DARK, QSS_LIGHT, APP_NAME, VERSION
from src.utils.helpers import format_size, format_time, open_folder
from src.utils.network import get_available_interfaces, get_local_ip, find_free_port
from src.utils.crypto import generate_self_signed_cert, create_ssl_context
from src.utils.discovery import PeerDiscovery
from src.core.logic import zip_folder_with_progress
from src.core.server import ThreadedTCPServer, DownloadHandler

class ServerSignals(QObject):
    client_connected = pyqtSignal(str)
    client_disconnected = pyqtSignal(str)
    download_complete = pyqtSignal(str, str, int)
    upload_complete = pyqtSignal(str, int)
    zip_progress = pyqtSignal(int, int, float, float, int)
    zip_finished = pyqtSignal(str, str)
    peer_found = pyqtSignal(dict)
    peer_lost = pyqtSignal(dict)

class LocalDropQtUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{VERSION} — Local Drop & Share")
        self.resize(520, 780)
        self.setMinimumSize(460, 680)

        # Set Window Icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Theme state
        self.is_dark_mode = True

        # App State
        self.httpd = None
        self.mode = None
        self.shared_file_path = None
        self.shared_text = None
        self.temp_dir = None
        self.share_pin = None
        self.zip_cancelled = False
        self.receive_dest = os.path.expanduser("~/Downloads")
        self.active_clients = set()
        self.completed_transfers = 0
        self.cert_file = None
        self.key_file = None
        self.port = DEFAULT_PORT

        # Signals bridge
        self.signals = ServerSignals()
        self.signals.client_connected.connect(self.on_client_connected)
        self.signals.client_disconnected.connect(self.on_client_disconnected)
        self.signals.download_complete.connect(self.on_download_finished)
        self.signals.upload_complete.connect(self.on_file_received)
        self.signals.zip_progress.connect(self.on_zip_progress_update)
        self.signals.zip_finished.connect(self.on_zip_done)
        self.signals.peer_found.connect(self.on_peer_discovered)
        self.signals.peer_lost.connect(self.on_peer_removed)

        # Peer Discovery
        self.discovery = PeerDiscovery(
            on_peer_found=lambda p: self.signals.peer_found.emit(p),
            on_peer_lost=lambda p: self.signals.peer_lost.emit(p)
        )
        self.discovery.start_browsing()

        # Network interface detection
        self.interfaces = get_available_interfaces()
        self.current_ip = self.interfaces[0][1] if self.interfaces else get_local_ip()

        self.init_ui()
        self.setAcceptDrops(True)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(10)

        # --- Top Header Bar ---
        header = QHBoxLayout()
        title_lbl = QLabel(f"⚡ {APP_NAME}")
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #58a6ff;")

        self.status_pill = QLabel("● IDLE")
        self.status_pill.setStyleSheet("color: #8b949e; font-weight: bold; font-size: 11px;")

        # Header utility buttons (Theme Toggle + Refresh Session)
        self.btn_theme = QPushButton("☀️ Light")
        self.btn_theme.setProperty("class", "icon-btn")
        self.btn_theme.setToolTip("Switch between Dark and Light mode")
        self.btn_theme.clicked.connect(self.toggle_theme)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setProperty("class", "icon-btn")
        self.btn_refresh.setToolTip("Refresh network interfaces, re-announce mDNS, and clear idle connections")
        self.btn_refresh.clicked.connect(self.refresh_session)

        header.addWidget(title_lbl)
        header.addStretch()
        header.addWidget(self.btn_theme)
        header.addWidget(self.btn_refresh)
        header.addWidget(self.status_pill)
        main_layout.addLayout(header)

        # --- Network Interface Selector Card ---
        net_frame = QFrame()
        net_frame.setProperty("class", "card")
        net_layout = QHBoxLayout(net_frame)
        net_layout.setContentsMargins(12, 8, 12, 8)

        net_icon = QLabel("📡")
        net_lbl = QLabel("Interface:")
        net_lbl.setStyleSheet("font-weight: bold;")

        self.combo_iface = QComboBox()
        self.populate_interfaces()
        self.combo_iface.currentIndexChanged.connect(self.on_interface_selected)

        net_layout.addWidget(net_icon)
        net_layout.addWidget(net_lbl)
        net_layout.addWidget(self.combo_iface, 1)
        main_layout.addWidget(net_frame)

        # --- Main Tabs (Share, Receive, Text, Peers) ---
        self.tabs = QTabWidget()

        # Tab 1: Share Files / Folders
        self.tab_share = self.create_share_tab()
        self.tabs.addTab(self.tab_share, "📤 Share Files")

        # Tab 2: Receive Files
        self.tab_receive = self.create_receive_tab()
        self.tabs.addTab(self.tab_receive, "📥 Receive")

        # Tab 3: Quick Text
        self.tab_text = self.create_text_tab()
        self.tabs.addTab(self.tab_text, "📋 Quick Text")

        # Tab 4: Nearby Devices
        self.tab_peers = self.create_peers_tab()
        self.tabs.addTab(self.tab_peers, "🔍 Nearby Devices")

        main_layout.addWidget(self.tabs, 1)

        # --- Active Broadcast Session Card ---
        self.session_box = QFrame()
        self.session_box.setProperty("class", "card")
        session_layout = QVBoxLayout(self.session_box)
        session_layout.setContentsMargins(16, 14, 16, 14)
        session_layout.setSpacing(8)

        self.session_info_title = QLabel("Ready to Stream")
        self.session_info_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.session_info_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.session_info_desc = QLabel("Drag & drop a file anywhere or pick a tab to start sharing.")
        self.session_info_desc.setStyleSheet("color: #8b949e; font-size: 12px;")
        self.session_info_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.session_info_desc.setWordWrap(True)

        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.url_label = QLabel("")
        self.url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.url_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.url_label.setStyleSheet("color: #58a6ff;")
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.activity_label = QLabel("")
        self.activity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activity_label.setStyleSheet("color: #3fb950; font-weight: 500;")

        # Progress elements
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.stats_lbl = QLabel("")
        self.stats_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.stats_lbl.setVisible(False)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.btn_stop = QPushButton("⏹ Stop Session")
        self.btn_stop.setProperty("class", "danger")
        self.btn_stop.clicked.connect(self.stop_server)
        self.btn_stop.setVisible(False)

        self.btn_open_folder = QPushButton("📂 Open Folder")
        self.btn_open_folder.clicked.connect(lambda: open_folder(self.receive_dest))
        self.btn_open_folder.setVisible(False)

        ctrl_layout.addWidget(self.btn_stop)
        ctrl_layout.addWidget(self.btn_open_folder)

        session_layout.addWidget(self.session_info_title)
        session_layout.addWidget(self.session_info_desc)
        session_layout.addWidget(self.progress_bar)
        session_layout.addWidget(self.stats_lbl)
        session_layout.addWidget(self.qr_label)
        session_layout.addWidget(self.url_label)
        session_layout.addWidget(self.activity_label)
        session_layout.addLayout(ctrl_layout)

        main_layout.addWidget(self.session_box)

    def populate_interfaces(self):
        self.combo_iface.blockSignals(True)
        self.combo_iface.clear()
        self.interfaces = get_available_interfaces()
        for desc, ip in self.interfaces:
            self.combo_iface.addItem(f"{desc} ({ip})", ip)
        self.combo_iface.blockSignals(False)

    # --- Theme Switching (Light & Dark Mode) ---
    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        app = QApplication.instance()
        if self.is_dark_mode:
            app.setStyleSheet(QSS_DARK)
            self.btn_theme.setText("☀️ Light")
        else:
            app.setStyleSheet(QSS_LIGHT)
            self.btn_theme.setText("🌙 Dark")
        
        # Redraw QR code if active to adapt contrast
        if self.httpd:
            self.update_qr_and_url()

    # --- Session Refresh Button ---
    def refresh_session(self):
        """Rescans network interfaces, updates QR/URL, and re-announces on mDNS."""
        self.populate_interfaces()
        idx = self.combo_iface.currentIndex()
        if idx >= 0:
            self.current_ip = self.combo_iface.itemData(idx)

        # Clear dead active clients
        self.active_clients.clear()

        if self.httpd:
            # Re-announce service on Zeroconf
            use_tls = self.chk_tls.isChecked() and bool(self.httpd.ssl_context)
            self.discovery.start_advertising(socket.gethostname(), self.current_ip, self.port, use_tls=use_tls)
            self.update_qr_and_url()
            self.activity_label.setText(f"Session refreshed on {self.current_ip}:{self.port}")
        else:
            self.session_info_desc.setText(f"Network interfaces rescanned. Active IP: {self.current_ip}")

    # --- Tab Builders ---
    def create_share_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(12)

        # Drag and Drop Box
        self.drop_zone = QFrame()
        self.drop_zone.setProperty("class", "drop-zone")
        dz_layout = QVBoxLayout(self.drop_zone)
        dz_layout.setContentsMargins(20, 24, 20, 24)

        dz_icon = QLabel("📁 ⬇️")
        dz_icon.setFont(QFont("Segoe UI", 24))
        dz_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        dz_text = QLabel("Drag & Drop File / Folder Here\nor use the buttons below")
        dz_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dz_text.setStyleSheet("color: #8b949e; font-size: 13px; font-weight: 500;")

        dz_layout.addWidget(dz_icon)
        dz_layout.addWidget(dz_text)
        l.addWidget(self.drop_zone)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_file = QPushButton("📄 Choose File...")
        btn_file.clicked.connect(self.choose_file)
        btn_folder = QPushButton("📁 Choose Folder...")
        btn_folder.clicked.connect(self.choose_folder)
        btn_layout.addWidget(btn_file)
        btn_layout.addWidget(btn_folder)
        l.addLayout(btn_layout)

        # Security Options
        sec_layout = QHBoxLayout()
        self.chk_tls = QCheckBox("Enable TLS Encryption (HTTPS)")
        self.chk_tls.setChecked(True)

        self.chk_pin = QCheckBox("Require PIN")
        self.chk_pin.toggled.connect(lambda checked: self.pin_input.setEnabled(checked))

        self.pin_input = QLineEdit("1234")
        self.pin_input.setMaximumWidth(70)
        self.pin_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_input.setEnabled(False)

        sec_layout.addWidget(self.chk_tls)
        sec_layout.addStretch()
        sec_layout.addWidget(self.chk_pin)
        sec_layout.addWidget(self.pin_input)
        l.addLayout(sec_layout)

        return w

    def create_receive_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(12)

        card = QFrame()
        card.setProperty("class", "card")
        cl = QVBoxLayout(card)

        info = QLabel("Accept uploads directly from phones, tablets, or other computers on your Wi-Fi.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #8b949e;")

        dest_row = QHBoxLayout()
        self.dest_lbl = QLabel(f"Saving to: {os.path.basename(self.receive_dest)}")
        self.dest_lbl.setStyleSheet("font-weight: 600;")
        btn_change_dest = QPushButton("Change Folder...")
        btn_change_dest.clicked.connect(self.choose_receive_folder)
        dest_row.addWidget(self.dest_lbl, 1)
        dest_row.addWidget(btn_change_dest)

        self.chk_prompt_receive = QCheckBox("Prompt to accept incoming transfers")
        self.chk_prompt_receive.setChecked(True)

        cl.addWidget(info)
        cl.addLayout(dest_row)
        cl.addWidget(self.chk_prompt_receive)
        l.addWidget(card)

        btn_start_rx = QPushButton("📥 Start Receiving Mode")
        btn_start_rx.setProperty("class", "success")
        btn_start_rx.clicked.connect(self.start_receive_mode)
        l.addWidget(btn_start_rx)
        l.addStretch()
        return w

    def create_text_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)

        lbl = QLabel("Paste text or a URL to beam directly to nearby devices:")
        lbl.setStyleSheet("color: #8b949e;")
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Type or paste links, passwords, notes here...")

        btn_row = QHBoxLayout()
        btn_paste = QPushButton("📋 Paste Clipboard")
        btn_paste.clicked.connect(self.paste_from_clipboard)
        btn_share_t = QPushButton("⚡ Broadcast Text")
        btn_share_t.setProperty("class", "primary")
        btn_share_t.clicked.connect(self.start_text_share)

        btn_row.addWidget(btn_paste)
        btn_row.addWidget(btn_share_t)

        l.addWidget(lbl)
        l.addWidget(self.text_editor)
        l.addLayout(btn_row)
        return w

    def create_peers_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setSpacing(10)

        lbl = QLabel("Discovered LocalDrop peers on this Wi-Fi network (mDNS):")
        lbl.setStyleSheet("color: #8b949e;")

        self.peers_list = QListWidget()
        self.peers_list.itemDoubleClicked.connect(self.on_peer_double_clicked)

        l.addWidget(lbl)
        l.addWidget(self.peers_list)
        return w

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.process_folder(path)
            elif os.path.isfile(path):
                self.process_file(path)

    # --- Actions ---
    def on_interface_selected(self, index):
        if index >= 0:
            self.current_ip = self.combo_iface.itemData(index)
            if self.httpd:
                self.update_qr_and_url()

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Share")
        if path:
            self.process_file(path)

    def process_file(self, path):
        self.stop_server()
        self.mode = "send"
        self.shared_file_path = path
        self.shared_text = None

        fname = os.path.basename(path)
        fsize = format_size(os.path.getsize(path))
        self.session_info_title.setText("Sharing File")
        self.session_info_desc.setText(f"{fname} ({fsize})")
        self.start_server()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder to Share")
        if path:
            self.process_folder(path)

    def process_folder(self, path):
        if not any(os.scandir(path)):
            QMessageBox.warning(self, "Empty Folder", "The selected folder contains no files.")
            return

        self.stop_server()
        self.session_info_title.setText("Compressing Folder...")
        self.session_info_desc.setText(os.path.basename(path))
        self.progress_bar.setVisible(True)
        self.stats_lbl.setVisible(True)

        def work():
            zp, td = zip_folder_with_progress(
                path,
                lambda d, p, s, r, t: self.signals.zip_progress.emit(d, p, s, r, t),
                lambda: self.zip_cancelled
            )
            if zp:
                self.shared_file_path = zp
                self.temp_dir = td
                self.signals.zip_finished.emit(path, zp)

        threading.Thread(target=work, daemon=True).start()

    def on_zip_progress_update(self, done, percent, speed, remaining, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
        self.stats_lbl.setText(f"{percent}% · {speed:.1f} MB/s · ETA {format_time(remaining)}")

    def on_zip_done(self, orig_path, zip_path):
        self.progress_bar.setVisible(False)
        self.stats_lbl.setVisible(False)
        self.mode = "send"
        self.shared_text = None
        fname = os.path.basename(orig_path)
        fsize = format_size(os.path.getsize(zip_path))
        self.session_info_title.setText("Sharing Folder (Archive)")
        self.session_info_desc.setText(f"{fname}.zip ({fsize})")
        self.start_server()

    def choose_receive_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Destination Folder", self.receive_dest)
        if path:
            self.receive_dest = path
            self.dest_lbl.setText(f"Saving to: {os.path.basename(path)}")

    def start_receive_mode(self):
        self.stop_server()
        self.mode = "receive"
        self.shared_file_path = None
        self.shared_text = None
        self.session_info_title.setText("Receive Mode Active")
        self.session_info_desc.setText(f"Accepting uploads to: {os.path.basename(self.receive_dest)}")
        self.start_server()

    def paste_from_clipboard(self):
        cb = QApplication.clipboard()
        self.text_editor.setPlainText(cb.text())

    def start_text_share(self):
        text = self.text_editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "No Text", "Please enter or paste text to share.")
            return
        self.stop_server()
        self.mode = "text"
        self.shared_text = text
        self.shared_file_path = None
        self.session_info_title.setText("Quick Text Beam Active")
        preview = text[:40] + ("..." if len(text) > 40 else "")
        self.session_info_desc.setText(f"Sharing: \"{preview}\"")
        self.start_server()

    # --- Server Execution ---
    def start_server(self):
        self.port = find_free_port(DEFAULT_PORT)

        # PIN config
        if self.chk_pin.isChecked():
            self.share_pin = self.pin_input.text().strip() or "1234"
        else:
            self.share_pin = None

        # TLS SSL Context
        ssl_ctx = None
        use_tls = self.chk_tls.isChecked()
        if use_tls:
            cert, key = generate_self_signed_cert(self.current_ip)
            if cert and key:
                self.cert_file = cert
                self.key_file = key
                ssl_ctx = create_ssl_context(cert, key)

        try:
            self.httpd = ThreadedTCPServer(("0.0.0.0", self.port), DownloadHandler, ssl_context=ssl_ctx)
            self.httpd.app_controller = self
            t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            t.start()
        except Exception as e:
            QMessageBox.critical(self, "Server Error", f"Failed to start server on port {self.port}: {e}")
            return

        # Start Zeroconf mDNS advertisement
        self.discovery.start_advertising(socket.gethostname(), self.current_ip, self.port, use_tls=bool(ssl_ctx))

        self.update_qr_and_url()
        self.status_pill.setText("● BROADCASTING")
        self.status_pill.setStyleSheet("color: #3fb950; font-weight: bold;")
        self.activity_label.setText("Ready. Scan QR or visit the URL from any device.")
        self.btn_stop.setVisible(True)
        if self.mode == "receive":
            self.btn_open_folder.setVisible(True)

    def get_server_url(self):
        scheme = "https" if self.chk_tls.isChecked() else "http"
        return f"{scheme}://{self.current_ip}:{self.port}"

    def update_qr_and_url(self):
        url = self.get_server_url()
        self.url_label.setText(url)

        # Generate QR adapting to light/dark
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        fg_col = "#0d1117"
        bg_col = "#ffffff"
        pil_img = qr.make_image(fill_color=fg_col, back_color=bg_col).convert("RGBA")

        # Convert to QPixmap
        data = pil_img.tobytes("raw", "RGBA")
        qim = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format.Format_RGBA8888)
        self.qr_label.setPixmap(QPixmap.fromImage(qim))

    def stop_server(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None

        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
            self.temp_dir = None

        self.status_pill.setText("● IDLE")
        self.status_pill.setStyleSheet("color: #8b949e; font-weight: bold;")
        self.session_info_title.setText("Ready to Stream")
        self.session_info_desc.setText("Drag & drop a file anywhere or pick a tab to start sharing.")
        self.qr_label.clear()
        self.url_label.setText("")
        self.activity_label.setText("")
        self.btn_stop.setVisible(False)
        self.btn_open_folder.setVisible(False)
        self.progress_bar.setVisible(False)
        self.stats_lbl.setVisible(False)

    # --- Callbacks ---
    def notify_client_connected(self, ip):
        self.signals.client_connected.emit(ip)

    def notify_client_disconnected(self, ip):
        self.signals.client_disconnected.emit(ip)

    def on_download_complete(self, ip, fname, size):
        self.signals.download_complete.emit(ip, fname, size)

    def report_received(self, fname, size):
        self.signals.upload_complete.emit(fname, size)

    def prompt_incoming_transfer(self, device_name, client_ip, count, total_size):
        if not self.chk_prompt_receive.isChecked():
            return True

        res_container = [False]
        evt = threading.Event()

        def ask():
            msg = (
                f"Device '{device_name}' ({client_ip}) wants to send "
                f"{count} file(s) ({format_size(total_size)}).\n\n"
                f"Do you accept?"
            )
            reply = QMessageBox.question(
                self, "Incoming File Transfer", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            res_container[0] = (reply == QMessageBox.StandardButton.Yes)
            evt.set()

        QTimer.singleShot(0, ask)
        evt.wait(timeout=25)
        return res_container[0]

    def on_client_connected(self, ip):
        self.active_clients.add(ip)
        self.activity_label.setText(f"Active clients: {len(self.active_clients)} ({ip})")

    def on_client_disconnected(self, ip):
        self.active_clients.discard(ip)
        self.activity_label.setText(f"Transfers: {self.completed_transfers} completed | Active: {len(self.active_clients)}")

    def on_download_finished(self, ip, fname, size):
        self.completed_transfers += 1
        self.active_clients.discard(ip)
        self.activity_label.setText(f"✓ Downloaded by {ip} ({format_size(size)})")

    def on_file_received(self, fname, size):
        self.completed_transfers += 1
        self.activity_label.setText(f"✓ Received: {fname} ({format_size(size)})")
        self.btn_open_folder.setVisible(True)

    def on_peer_discovered(self, peer):
        text = f"📱 {peer['name']} — {peer['ip']}:{peer['port']} ({'TLS' if peer['tls'] else 'HTTP'})"
        for i in range(self.peers_list.count()):
            item = self.peers_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == peer['key']:
                item.setText(text)
                return
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, peer['key'])
        self.peers_list.addItem(item)

    def on_peer_removed(self, peer):
        for i in range(self.peers_list.count()):
            item = self.peers_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == peer['key']:
                self.peers_list.takeItem(i)
                break

    def on_peer_double_clicked(self, item):
        import webbrowser
        key = item.data(Qt.ItemDataRole.UserRole)
        peer = self.discovery.peers.get(key)
        if peer:
            scheme = "https" if peer["tls"] else "http"
            url = f"{scheme}://{peer['ip']}:{peer['port']}"
            webbrowser.open(url)

    def closeEvent(self, event):
        self.stop_server()
        self.discovery.stop()
        event.accept()
