# src/ui/app_ui.py
import tkinter as tk
from tkinter import filedialog, ttk
import threading
import os
import qrcode
from PIL import Image, ImageTk
import shutil

from src.config import *
from src.utils.helpers import format_size, format_time
from src.utils.network import get_local_ip
from src.core.logic import zip_folder_with_progress
from src.core.server import ThreadedTCPServer, DownloadHandler

class LocalDropUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LocalDrop")
        self.root.geometry("420x720")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        # State vars
        self.httpd = None
        self.mode = None
        self.shared_file_path = None
        self.temp_dir = None
        self.share_pin = None
        self.download_used = False
        self.upload_done = False
        self.qr_img = None
        self.bind_ip = None
        self.receive_dest = None
        self.zip_cancelled = False

        self.setup_ui()

    def setup_ui(self):
        self.frame = tk.Frame(self.root, bg=CARD, padx=24, pady=24)
        self.frame.pack(expand=True, fill="both", padx=16, pady=16)

        self.btn_share_file = self.button("Share File", self.select_file)
        self.btn_share_file.pack(fill="x", pady=6)

        self.btn_share_folder = self.button("Share Folder", self.select_folder)
        self.btn_share_folder.pack(fill="x", pady=6)

        self.btn_receive = self.button("Receive File/Folder", self.receive_files, ACCENT)
        self.btn_receive.pack(fill="x", pady=6)

        self.pin_var = tk.StringVar()
        self.pin_frame = tk.Frame(self.frame, bg=CARD)
        tk.Label(self.pin_frame, text="4-digit PIN", bg=CARD, fg=SUBTEXT).pack()
        self.pin_entry = tk.Entry(
            self.pin_frame, textvariable=self.pin_var, show="*",
            justify="center", font=("Segoe UI", 14),
            bg=BG, fg=TEXT, relief="flat"
        )
        self.pin_entry.pack(pady=6)
        
        self.confirm_btn = tk.Button(
            self.pin_frame, text="Confirm PIN", bg=ACCENT, fg=TEXT,
            activebackground=ACCENT, relief="flat",
            font=("Segoe UI", 11), padx=14, pady=8,
            command=self.confirm_pin
        )
        self.confirm_btn.pack(fill="x", pady=6)

        self.info_label = tk.Label(self.frame, text="No file or folder selected", bg=CARD, fg=SUBTEXT, wraplength=340)
        self.info_label.pack(pady=12)

        self.progress_bar = ttk.Progressbar(self.frame, orient="horizontal", length=300, mode="determinate")
        self.percent_label = tk.Label(self.frame, text="0%", bg=CARD, fg=TEXT)
        self.stats_label = tk.Label(self.frame, text="", bg=CARD, fg=SUBTEXT)
        
        self.cancel_zip_btn = self.button("Cancel", self.cancel_zip, DANGER)
        self.cancel_share_btn = self.button("Cancel Share", self.cancel_share, DANGER)
        self.open_dest_btn = self.button("Open Destination", self.open_destination, ACCENT)

        self.qr_label = tk.Label(self.frame, bg=CARD)
        self.qr_label.pack(pady=12)

        self.url_label = tk.Label(self.frame, text="", bg=CARD, fg=ACCENT)
        self.url_label.pack()

    def button(self, text, cmd, color=BTN):
        return tk.Button(
            self.frame, text=text, command=cmd, bg=color, fg=TEXT,
            activebackground=color, relief="flat",
            font=("Segoe UI", 11), padx=14, pady=8
        )

    # Core Action Logic
    def select_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.full_cleanup()
            self.shared_file_path = path
            self.info_label.config(text=f"{os.path.basename(path)}   {format_size(os.path.getsize(path))}")
            self.pin_frame.pack(pady=12)

    def select_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.full_cleanup()
            if not any(os.scandir(path)):
                self.info_label.config(text="Folder is empty!")
                return
            
            self.info_label.config(text="Preparing folder…")
            self.progress_bar.pack(pady=(12, 4))
            self.percent_label.pack()
            self.stats_label.pack()
            self.cancel_zip_btn.pack(pady=8)

            def work():
                zp, td = zip_folder_with_progress(
                    path, 
                    self.update_zip_progress,
                    lambda: self.zip_cancelled
                )
                if zp:
                    self.shared_file_path = zp
                    self.temp_dir = td
                    self.root.after(0, self.on_zip_done, path, zp)

            threading.Thread(target=work, daemon=True).start()

    def update_zip_progress(self, done, percent, speed, remaining, total):
        self.root.after(0, lambda: (
            self.progress_bar.config(value=done, maximum=total),
            self.percent_label.config(text=f"{percent}%"),
            self.stats_label.config(text=f"{speed:.1f} MB/s   ETA {format_time(remaining)}")
        ))

    def on_zip_done(self, orig_path, zip_path):
        self.progress_bar.pack_forget()
        self.percent_label.pack_forget()
        self.stats_label.pack_forget()
        self.cancel_zip_btn.pack_forget()
        self.info_label.config(text=f"{os.path.basename(orig_path)}   {format_size(os.path.getsize(zip_path))}")
        self.pin_frame.pack(pady=12)

    def receive_files(self):
        dest = filedialog.askdirectory(title="Select destination folder")
        if dest:
            self.full_cleanup()
            self.receive_dest = dest
            self.mode = "receive"
            self.info_label.config(text=f"Destination: {os.path.basename(dest)}")
            self.pin_frame.pack(pady=12)

    def confirm_pin(self):
        pin = self.pin_var.get()
        if not (pin.isdigit() and len(pin) == 4):
            self.info_label.config(text="PIN must be 4 digits")
            return
        self.share_pin = pin
        self.pin_frame.pack_forget()
        
        if self.mode == "receive":
            self.info_label.config(text="Receive ready")
            self.start_server_flow()
        else:
            self.mode = "send"
            self.info_label.config(text="Share ready")
            self.start_server_flow()

    def start_server_flow(self):
        self.bind_ip = get_local_ip()
        url = f"http://{self.bind_ip}:{PORT}"
        self.url_label.config(text=url)
        self.generate_qr(url)
        
        self.httpd = ThreadedTCPServer(("0.0.0.0", PORT), DownloadHandler)
        self.httpd.app_controller = self
        
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.info_label.config(text="Waiting for transfer...")
        self.cancel_share_btn.pack(pady=8)

    def generate_qr(self, url):
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").resize((180, 180))
        self.qr_img = ImageTk.PhotoImage(img)
        self.qr_label.config(image=self.qr_img)

    def cancel_zip(self):
        self.zip_cancelled = True
        self.info_label.config(text="Zipping cancelled")

    def cancel_share(self):
        self.info_label.config(text="Sharing cancelled")
        self.full_cleanup()

    def open_destination(self):
        if self.receive_dest and os.path.exists(self.receive_dest):
            os.startfile(self.receive_dest)

    def report_received(self, fname, fsize, is_dir):
        size_mb = fsize / (1024 * 1024)
        t_str = "Folder" if is_dir else "File"
        self.root.after(0, lambda: self.info_label.config(text=f"Received {t_str}: {fname}   {size_mb:.2f} MB"))
        self.root.after(0, lambda: self.open_dest_btn.pack(pady=8))

    def on_transfer_complete(self):
        self.root.after(500, self.full_cleanup)

    def full_cleanup(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        
        self.zip_cancelled = False
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        self.shared_file_path = None
        self.temp_dir = None
        self.share_pin = None
        self.download_used = False
        self.upload_done = False
        self.mode = None
        self.receive_dest = None
        
        self.pin_var.set("")
        self.pin_frame.pack_forget()
        self.qr_label.config(image="")
        self.url_label.config(text="")
        self.info_label.config(text="No file or folder selected")
        self.progress_bar.pack_forget()
        self.percent_label.pack_forget()
        self.stats_label.pack_forget()
        self.cancel_zip_btn.pack_forget()
        self.cancel_share_btn.pack_forget()
        self.open_dest_btn.pack_forget()
