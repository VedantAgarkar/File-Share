# src/ui/app_ui.py
import tkinter as tk
from tkinter import filedialog, ttk
import threading
import os
import qrcode
from PIL import Image, ImageTk
import shutil

from src.config import (
    PORT, BG, CARD, CARD_BORDER, TEXT, SUBTEXT, ACCENT, ACCENT_HOVER,
    BTN, BTN_HOVER, SUCCESS, DANGER, DANGER_HOVER, WARN
)
from src.utils.helpers import format_size, format_time, open_folder
from src.utils.network import get_available_interfaces, get_local_ip
from src.core.logic import zip_folder_with_progress
from src.core.server import ThreadedTCPServer, DownloadHandler

class LocalDropUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LocalDrop — Cross-Device Direct Share")
        self.root.geometry("480x760")
        self.root.minsize(440, 700)
        self.root.configure(bg=BG)

        # Application state
        self.httpd = None
        self.server_thread = None
        self.mode = None  # 'send', 'receive', 'text'
        self.shared_file_path = None
        self.shared_text = None
        self.temp_dir = None
        self.share_pin = None
        self.pin_required = tk.BooleanVar(value=False)
        self.multi_client_mode = tk.BooleanVar(value=True)
        self.zip_cancelled = False
        self.receive_dest = os.path.expanduser("~/Downloads")

        # Network interface tracking
        self.interfaces = get_available_interfaces()
        self.selected_ip = tk.StringVar(value=self.interfaces[0][1] if self.interfaces else get_local_ip())

        # Transfer counters
        self.completed_transfers = 0
        self.active_clients = set()
        self.qr_img = None

        self.setup_styles()
        self.build_ui()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "Horizontal.TProgressbar",
            background=ACCENT,
            troughcolor=BTN,
            bordercolor=CARD,
            lightcolor=ACCENT,
            darkcolor=ACCENT
        )
        style.configure(
            "TCombobox",
            fieldbackground=CARD,
            background=BTN,
            foreground=TEXT,
            darkcolor=CARD_BORDER,
            lightcolor=CARD_BORDER,
            arrowcolor=TEXT
        )

    def build_ui(self):
        # Main wrapper with scroll or padding
        self.main_container = tk.Frame(self.root, bg=BG, padx=16, pady=16)
        self.main_container.pack(expand=True, fill="both")

        # Header bar
        header_frame = tk.Frame(self.main_container, bg=BG)
        header_frame.pack(fill="x", pady=(0, 14))

        title_lbl = tk.Label(
            header_frame, text="LocalDrop", font=("Segoe UI", 18, "bold"),
            bg=BG, fg=TEXT
        )
        title_lbl.pack(side="left")

        self.status_badge = tk.Label(
            header_frame, text="● IDLE", font=("Segoe UI", 10, "bold"),
            bg=BG, fg=SUBTEXT
        )
        self.status_badge.pack(side="right")

        # Network Interface Selector Card
        net_card = tk.Frame(self.main_container, bg=CARD, highlightbackground=CARD_BORDER, highlightthickness=1, padx=14, pady=10)
        net_card.pack(fill="x", pady=(0, 12))

        net_lbl = tk.Label(net_card, text="Network Adapter (Wi-Fi / LAN):", font=("Segoe UI", 9, "bold"), bg=CARD, fg=SUBTEXT)
        net_lbl.pack(anchor="w")

        iface_options = [f"{desc} — {ip}" for desc, ip in self.interfaces]
        self.iface_combo = ttk.Combobox(net_card, values=iface_options, state="readonly", font=("Segoe UI", 10))
        if iface_options:
            self.iface_combo.current(0)
        self.iface_combo.pack(fill="x", pady=(4, 0))
        self.iface_combo.bind("<<ComboboxSelected>>", self.on_interface_change)

        # Primary Actions Container (Cards)
        self.actions_frame = tk.Frame(self.main_container, bg=CARD, highlightbackground=CARD_BORDER, highlightthickness=1, padx=16, pady=16)
        self.actions_frame.pack(fill="x", pady=(0, 12))

        lbl_actions = tk.Label(self.actions_frame, text="Select Transfer Mode", font=("Segoe UI", 11, "bold"), bg=CARD, fg=TEXT)
        lbl_actions.pack(anchor="w", pady=(0, 10))

        # Action Buttons Grid
        btn_grid = tk.Frame(self.actions_frame, bg=CARD)
        btn_grid.pack(fill="x")

        self.btn_share_file = self.create_button(btn_grid, "📄 Share File", self.select_file, bg=BTN, fg=TEXT)
        self.btn_share_file.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=4)

        self.btn_share_folder = self.create_button(btn_grid, "📁 Share Folder", self.select_folder, bg=BTN, fg=TEXT)
        self.btn_share_folder.grid(row=0, column=1, sticky="ew", padx=(4, 0), pady=4)

        self.btn_share_text = self.create_button(btn_grid, "📋 Share Text", self.show_text_share_dialog, bg=BTN, fg=TEXT)
        self.btn_share_text.grid(row=1, column=0, sticky="ew", padx=(0, 4), pady=4)

        self.btn_receive = self.create_button(btn_grid, "📥 Receive Files", self.setup_receive_mode, bg=ACCENT, fg="#0b0f17", bold=True)
        self.btn_receive.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=4)

        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        # Options Card (PIN & Multi-device toggles)
        self.opts_card = tk.Frame(self.main_container, bg=CARD, highlightbackground=CARD_BORDER, highlightthickness=1, padx=14, pady=10)
        self.opts_card.pack(fill="x", pady=(0, 12))

        opts_row = tk.Frame(self.opts_card, bg=CARD)
        opts_row.pack(fill="x")

        self.chk_pin = tk.Checkbutton(
            opts_row, text="Require 4-digit PIN", variable=self.pin_required,
            bg=CARD, fg=TEXT, selectcolor=BG, activebackground=CARD,
            activeforeground=TEXT, font=("Segoe UI", 9), command=self.on_pin_toggle
        )
        self.chk_pin.pack(side="left")

        self.chk_multi = tk.Checkbutton(
            opts_row, text="Multi-device stream", variable=self.multi_client_mode,
            bg=CARD, fg=TEXT, selectcolor=BG, activebackground=CARD,
            activeforeground=TEXT, font=("Segoe UI", 9)
        )
        self.chk_multi.pack(side="right")

        # Dynamic PIN entry box (hidden unless checked)
        self.pin_box = tk.Frame(self.opts_card, bg=CARD)
        tk.Label(self.pin_box, text="PIN Code:", font=("Segoe UI", 9), bg=CARD, fg=SUBTEXT).pack(side="left", padx=(0, 6))
        self.pin_entry = tk.Entry(self.pin_box, width=8, font=("Segoe UI", 11, "bold"), bg=BG, fg=ACCENT, insertbackground=TEXT, justify="center")
        self.pin_entry.insert(0, "1234")
        self.pin_entry.pack(side="left")

        # Active Session Display Card
        self.session_card = tk.Frame(self.main_container, bg=CARD, highlightbackground=CARD_BORDER, highlightthickness=1, padx=16, pady=16)
        self.session_card.pack(expand=True, fill="both")

        self.info_title = tk.Label(self.session_card, text="Ready to Share", font=("Segoe UI", 12, "bold"), bg=CARD, fg=TEXT)
        self.info_title.pack(anchor="center")

        self.info_desc = tk.Label(
            self.session_card, text="Choose a file or folder above, or click Receive to accept uploads.",
            font=("Segoe UI", 9), bg=CARD, fg=SUBTEXT, wraplength=380, justify="center"
        )
        self.info_desc.pack(anchor="center", pady=(4, 10))

        # Progress elements
        self.progress_bar = ttk.Progressbar(self.session_card, orient="horizontal", mode="determinate")
        self.stats_lbl = tk.Label(self.session_card, text="", font=("Segoe UI", 9), bg=CARD, fg=SUBTEXT)

        # QR Code Display
        self.qr_label = tk.Label(self.session_card, bg=CARD)
        self.qr_label.pack(pady=4)

        # Server URL Link
        self.url_lbl = tk.Label(self.session_card, text="", font=("Segoe UI", 11, "bold"), bg=CARD, fg=ACCENT, cursor="hand2")
        self.url_lbl.pack(pady=2)

        # Clients / transfer activity status
        self.activity_lbl = tk.Label(self.session_card, text="", font=("Segoe UI", 9), bg=CARD, fg=SUCCESS)
        self.activity_lbl.pack(pady=2)

        # Session Bottom Controls
        self.session_ctrls = tk.Frame(self.session_card, bg=CARD)
        self.session_ctrls.pack(fill="x", side="bottom", pady=(10, 0))

        self.btn_stop = self.create_button(self.session_ctrls, "⏹ Stop Session", self.stop_session, bg=DANGER, fg=TEXT)
        self.btn_open_folder = self.create_button(self.session_ctrls, "📂 Open Downloads", self.open_download_dest, bg=BTN, fg=TEXT)

    def create_button(self, parent, text, cmd, bg=BTN, fg=TEXT, bold=False):
        font_style = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
        return tk.Button(
            parent, text=text, command=cmd, bg=bg, fg=fg,
            activebackground=ACCENT_HOVER, activeforeground=TEXT,
            relief="flat", bd=0, padx=12, pady=8, font=font_style, cursor="hand2"
        )

    def on_interface_change(self, event=None):
        idx = self.iface_combo.current()
        if 0 <= idx < len(self.interfaces):
            self.selected_ip.set(self.interfaces[idx][1])
            if self.httpd:
                # Refresh QR code with the newly selected network interface URL
                url = self.get_current_url()
                self.url_lbl.config(text=url)
                self.generate_qr(url)

    def on_pin_toggle(self):
        if self.pin_required.get():
            self.pin_box.pack(fill="x", pady=(8, 0))
        else:
            self.pin_box.pack_forget()

    def get_current_url(self):
        ip = self.selected_ip.get()
        return f"http://{ip}:{PORT}"

    # ==========================
    # WORKFLOW TRIGGERS
    # ==========================

    def select_file(self):
        path = filedialog.askopenfilename()
        if not path:
            return
        self.cleanup_session(keep_mode=True)
        self.mode = "send"
        self.shared_file_path = path
        self.shared_text = None

        fname = os.path.basename(path)
        fsize = format_size(os.path.getsize(path))
        self.info_title.config(text="Sharing File")
        self.info_desc.config(text=f"{fname} ({fsize})")
        self.start_server()

    def select_folder(self):
        path = filedialog.askdirectory()
        if not path:
            return
        if not any(os.scandir(path)):
            self.info_desc.config(text="The chosen folder is empty!")
            return

        self.cleanup_session(keep_mode=True)
        self.info_title.config(text="Compressing Folder...")
        self.info_desc.config(text=os.path.basename(path))

        self.progress_bar.pack(fill="x", padx=20, pady=(6, 2))
        self.stats_lbl.pack()

        def work():
            zp, td = zip_folder_with_progress(
                path,
                self.update_zip_progress,
                lambda: self.zip_cancelled
            )
            if zp:
                self.shared_file_path = zp
                self.temp_dir = td
                self.root.after(0, self.on_zip_finished, path, zp)

        threading.Thread(target=work, daemon=True).start()

    def update_zip_progress(self, done, percent, speed, remaining, total):
        self.root.after(0, lambda: (
            self.progress_bar.config(value=done, maximum=total),
            self.stats_lbl.config(text=f"{percent}% · {speed:.1f} MB/s · ETA {format_time(remaining)}")
        ))

    def on_zip_finished(self, orig_path, zip_path):
        self.progress_bar.pack_forget()
        self.stats_lbl.pack_forget()
        self.mode = "send"
        self.shared_text = None
        fname = os.path.basename(orig_path)
        fsize = format_size(os.path.getsize(zip_path))
        self.info_title.config(text="Sharing Folder (ZIP Archive)")
        self.info_desc.config(text=f"{fname}.zip ({fsize})")
        self.start_server()

    def show_text_share_dialog(self):
        # Quick modal to paste text or links
        dialog = tk.Toplevel(self.root)
        dialog.title("Share Text or Link")
        dialog.geometry("380x280")
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Paste Text / URL to share:", font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(16, 6))
        text_box = tk.Text(dialog, height=7, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        text_box.pack(fill="both", expand=True, padx=16, pady=4)
        text_box.focus_set()

        # Try auto-pasting clipboard if available
        try:
            cb = self.root.clipboard_get()
            if cb:
                text_box.insert("1.0", cb)
        except Exception:
            pass

        def on_confirm():
            content = text_box.get("1.0", "end-1c").strip()
            if content:
                dialog.destroy()
                self.cleanup_session(keep_mode=True)
                self.mode = "text"
                self.shared_text = content
                self.shared_file_path = None
                self.info_title.config(text="Sharing Text / Link")
                preview = content[:60] + ("..." if len(content) > 60 else "")
                self.info_desc.config(text=preview)
                self.start_server()

        btn_row = tk.Frame(dialog, bg=BG)
        btn_row.pack(fill="x", padx=16, pady=12)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy, bg=BTN, fg=TEXT, relief="flat", padx=12, pady=6).pack(side="left")
        tk.Button(btn_row, text="Start Sharing", command=on_confirm, bg=ACCENT, fg="#0b0f17", font=("Segoe UI", 9, "bold"), relief="flat", padx=14, pady=6).pack(side="right")

    def setup_receive_mode(self):
        dest = filedialog.askdirectory(title="Select Download Destination Folder", initialdir=self.receive_dest)
        if not dest:
            return
        self.cleanup_session(keep_mode=True)
        self.mode = "receive"
        self.receive_dest = dest
        self.shared_file_path = None
        self.shared_text = None
        self.info_title.config(text="Waiting for Uploads...")
        self.info_desc.config(text=f"Saving to: {os.path.basename(dest)}")
        self.start_server()

    # ==========================
    # SERVER LIFECYCLE
    # ==========================

    def start_server(self):
        if self.pin_required.get():
            pin = self.pin_entry.get().strip()
            self.share_pin = pin if pin else "1234"
        else:
            self.share_pin = None

        url = self.get_current_url()
        self.url_lbl.config(text=url)
        self.generate_qr(url)

        self.status_badge.config(text="● BROADCASTING", fg=SUCCESS)
        self.activity_lbl.config(text="Ready. Scan QR code or visit URL on any device.")

        # Show stop & destination buttons
        self.btn_stop.pack(side="left", expand=True, fill="x", padx=(0, 4))
        if self.mode == "receive":
            self.btn_open_folder.pack(side="right", expand=True, fill="x", padx=(4, 0))
        else:
            self.btn_open_folder.pack_forget()

        # Start multi-threaded server on 0.0.0.0
        try:
            self.httpd = ThreadedTCPServer(("0.0.0.0", PORT), DownloadHandler)
            self.httpd.app_controller = self
            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()
        except OSError as e:
            self.info_desc.config(text=f"Port {PORT} error: {e}. Check if another instance is running.")
            self.status_badge.config(text="● ERROR", fg=DANGER)

    def generate_qr(self, url):
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0b0f17", back_color="#f8fafc").resize((170, 170))
        self.qr_img = ImageTk.PhotoImage(img)
        self.qr_label.config(image=self.qr_img)

    def open_download_dest(self):
        if self.receive_dest and os.path.exists(self.receive_dest):
            open_folder(self.receive_dest)

    # Server callbacks
    def notify_client_connected(self, client_ip):
        self.active_clients.add(client_ip)
        self.root.after(0, lambda: self.activity_lbl.config(
            text=f"Active clients: {len(self.active_clients)} ({client_ip})"
        ))

    def notify_client_disconnected(self, client_ip):
        if client_ip in self.active_clients:
            self.active_clients.remove(client_ip)
        self.root.after(0, lambda: self.activity_lbl.config(
            text=f"Transfers completed: {self.completed_transfers} | Active: {len(self.active_clients)}"
        ))

    def on_download_complete(self, client_ip, filename, bytes_sent):
        self.completed_transfers += 1
        if client_ip in self.active_clients:
            self.active_clients.remove(client_ip)

        self.root.after(0, lambda: self.activity_lbl.config(
            text=f"✓ Download finished for {client_ip} ({format_size(bytes_sent)})"
        ))

        # Only shutdown if multi-client is explicitly disabled
        if not self.multi_client_mode.get():
            self.root.after(1000, self.stop_session)

    def report_received(self, filename, filesize):
        self.completed_transfers += 1
        self.root.after(0, lambda: (
            self.activity_lbl.config(text=f"✓ Received: {filename} ({format_size(filesize)})"),
            self.btn_open_folder.pack(side="right", expand=True, fill="x", padx=(4, 0))
        ))

    def stop_session(self):
        self.cleanup_session(keep_mode=False)
        self.status_badge.config(text="● IDLE", fg=SUBTEXT)
        self.info_title.config(text="Ready to Share")
        self.info_desc.config(text="Choose a file or folder above, or click Receive to accept uploads.")
        self.activity_lbl.config(text="")
        self.url_lbl.config(text="")
        self.qr_label.config(image="")

    def cleanup_session(self, keep_mode=False):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None

        self.active_clients.clear()
        self.completed_transfers = 0
        self.btn_stop.pack_forget()
        self.btn_open_folder.pack_forget()

        if not keep_mode:
            self.mode = None

        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass
            self.temp_dir = None
