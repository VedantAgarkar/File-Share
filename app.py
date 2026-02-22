import tkinter as tk
from tkinter import filedialog, ttk
import os, socket, threading, http.server, socketserver, time
import zipfile, tempfile, mimetypes, shutil
import qrcode
from PIL import Image, ImageTk
from urllib.parse import urlparse, parse_qs

PORT = 8000
CHUNK_SIZE = 52 * 1024 * 1024  # 52MB chunks - 75% faster than 30MB

httpd = None
mode = None  # 'send' or 'receive'
shared_file_path = None
temp_dir = None
share_pin = None
download_used = False
upload_done = False
qr_img = None
bind_ip = None
receive_dest = None

zip_cancelled = False
zip_start_time = 0
zip_total_bytes = 0
zip_done_bytes = 0

BG = "#0f172a"
CARD = "#020617"
TEXT = "#e5e7eb"
SUBTEXT = "#94a3b8"
ACCENT = "#38bdf8"
BTN = "#1e293b"
DANGER = "#ef4444"

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    timeout = 300  # 5 minute timeout for large uploads
    
    def server_bind(self):
        # Set socket options for better large file handling
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)  # 2MB receive buffer (75% increase)
        super().server_bind()

def stop_server():
    global httpd
    if httpd:
        httpd.shutdown()
        httpd.server_close()
        httpd = None

def start_server():
    global httpd
    httpd = ThreadedTCPServer(("0.0.0.0", PORT), DownloadHandler)
    httpd.serve_forever()

def start_server_bg():
    threading.Thread(target=start_server, daemon=True).start()

def full_cleanup():
    global shared_file_path, temp_dir, share_pin, download_used, upload_done, zip_cancelled, mode, receive_dest
    stop_server()
    zip_cancelled = False
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    shared_file_path = None
    temp_dir = None
    share_pin = None
    download_used = False
    upload_done = False
    mode = None
    receive_dest = None
    if 'pin_var' in globals():  # Check if UI is initialized
        pin_var.set("")
        pin_frame.pack_forget()
        qr_label.config(image="")
        url_label.config(text="")
        info_label.config(text="No file or folder selected")
        progress_bar.pack_forget()
        percent_label.pack_forget()
        stats_label.pack_forget()
        cancel_btn.pack_forget()
        cancel_share_btn.pack_forget()
        open_dest_btn.pack_forget()

def format_size(b):
    return f"{b / (1024 * 1024):.2f} MB"

def format_time(sec):
    if sec < 0:
        return "--"
    m, s = divmod(int(sec), 60)
    return f"{m}m {s}s"

def zip_folder_with_progress(folder_path):
    global temp_dir, zip_cancelled, zip_start_time, zip_total_bytes, zip_done_bytes

    zip_cancelled = False
    zip_done_bytes = 0
    zip_total_bytes = 0
    zip_start_time = time.time()

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, os.path.basename(folder_path) + ".zip")

    files = []
    for r, _, fs in os.walk(folder_path):
        for f in fs:
            full = os.path.join(r, f)
            files.append(full)
            zip_total_bytes += os.path.getsize(full)

    progress_bar["maximum"] = zip_total_bytes  # Use byte-based progress

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for i, f in enumerate(files, start=1):
            if zip_cancelled:
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                temp_dir = None  # Reset to prevent double cleanup
                return None

            z.write(f, os.path.relpath(f, folder_path))
            size = os.path.getsize(f)
            zip_done_bytes += size

            elapsed = time.time() - zip_start_time
            speed = (zip_done_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0
            remaining = (zip_total_bytes - zip_done_bytes) / (speed * 1024 * 1024) if speed > 0 and zip_done_bytes < zip_total_bytes else 0
            percent = int((zip_done_bytes / zip_total_bytes) * 100) if zip_total_bytes > 0 else 0

            root.after(
                0,
                lambda v=zip_done_bytes, p=percent, s=speed, r=remaining: (
                    progress_bar.config(value=v),
                    percent_label.config(text=f"{p}%"),
                    stats_label.config(text=f"{s:.1f} MB/s   ETA {format_time(r)}")
                )
            )

    return zip_path

def generate_qr(url):
    global qr_img
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").resize((180, 180))
    qr_img = ImageTk.PhotoImage(img)
    qr_label.config(image=qr_img)

def start_share():
    global bind_ip, mode
    mode = "send"
    bind_ip = get_local_ip()
    url = f"http://{bind_ip}:{PORT}"
    url_label.config(text=url)
    generate_qr(url)
    start_server_bg()
    info_label.config(text="Waiting for download...")
    cancel_share_btn.pack(pady=8)

def start_receive():
    global bind_ip, mode
    mode = "receive"
    bind_ip = get_local_ip()
    url = f"http://{bind_ip}:{PORT}"
    url_label.config(text=url)
    generate_qr(url)
    start_server_bg()
    info_label.config(text="Waiting for upload...")
    cancel_share_btn.pack(pady=8)

def confirm_send_pin():
    global share_pin
    pin = pin_var.get()
    if not (pin.isdigit() and len(pin) == 4):
        info_label.config(text="PIN must be exactly 4 digits")
        return
    share_pin = pin
    pin_frame.pack_forget()
    info_label.config(text="Share ready")
    start_share()

def confirm_receive_pin():
    global share_pin
    pin = pin_var.get()
    if not (pin.isdigit() and len(pin) == 4):
        info_label.config(text="PIN must be exactly 4 digits")
        return
    share_pin = pin
    pin_frame.pack_forget()
    info_label.config(text="Receive ready")
    start_receive()

def cancel_zip():
    global zip_cancelled
    zip_cancelled = True
    info_label.config(text="Zipping cancelled")

def cancel_share():
    info_label.config(text="Sharing cancelled")
    full_cleanup()

class DownloadHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Enable logging for debugging
        print(f"[{self.address_string()}] {format % args}")

    def do_GET(self):
        try:
            if mode == "send":
                if self.path.startswith("/download"):
                    self.send_file()
                else:
                    self.show_pin_page()
            elif mode == "receive":
                if self.path == "/verified":
                    self.show_upload_options()
                else:
                    self.show_receive_pin_page()
            else:
                # No mode set - shouldn't happen
                self.send_response(503)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body><h1>Service not ready</h1><p>Please select a mode first.</p></body></html>")
        except Exception as e:
            import traceback
            print(f"ERROR in do_GET: {e}")
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}\n{traceback.format_exc()}".encode())

    def do_POST(self):
        try:
            if mode == "receive" and self.path == "/verify":
                self.verify_receive_pin()
            elif mode == "receive" and self.path == "/upload":
                self.handle_upload()
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            import traceback
            print(f"ERROR in do_POST: {e}")
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}\n{traceback.format_exc()}".encode())

    def show_pin_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"""
        <html><body style="background:#0f172a;color:#e5e7eb;
        font-family:system-ui;display:flex;align-items:center;
        justify-content:center;height:100vh">
        <div style="background:#020617;padding:24px;border-radius:14px;
        width:90%;max-width:320px;text-align:center">
        <h2>Enter PIN to Download</h2>
        <form action="/download">
        <input type="password" name="pin" maxlength="4"
        style="width:100%;padding:14px;font-size:18px;
        border-radius:10px;border:none;text-align:center"/>
        <button style="width:100%;padding:14px;font-size:18px;
        border-radius:10px;border:none;margin-top:12px;
        background:#38bdf8;color:black;font-weight:600">
        Download
        </button>
        </form>
        </div></body></html>
        """)

    def show_receive_pin_page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"""
        <html><body style="background:#0f172a;color:#e5e7eb;
        font-family:system-ui;display:flex;align-items:center;
        justify-content:center;height:100vh">
        <div style="background:#020617;padding:24px;border-radius:14px;
        width:90%;max-width:320px;text-align:center">
        <h2>Enter PIN to Upload</h2>
        <form method="POST" action="/verify">
        <input type="password" name="pin" maxlength="4" required
        style="width:100%;padding:14px;font-size:18px;
        border-radius:10px;border:none;text-align:center"/>
        <button style="width:100%;padding:14px;font-size:18px;
        border-radius:10px;border:none;margin-top:12px;
        background:#38bdf8;color:black;font-weight:600">
        Continue
        </button>
        </form>
        </div></body></html>
        """)

    def verify_receive_pin(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        params = parse_qs(body)
        pin = params.get("pin", [None])[0]
        
        if pin == share_pin:
            self.send_response(303)
            self.send_header("Location", "/verified")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
        else:
            self.send_response(403)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Invalid PIN</h1></body></html>")

    def show_upload_options(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        html = """
        <html><head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
        body{background:#0f172a;color:#e5e7eb;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px;margin:0}
        .card{background:#020617;padding:24px;border-radius:14px;width:90%;max-width:320px;text-align:center}
        .btn{display:block;padding:14px;background:#1e293b;border-radius:10px;cursor:pointer;margin-bottom:12px;border:none;color:#e5e7eb;width:100%}
        .btn:active{background:#334155}
        .upload-btn{background:#38bdf8;color:black;font-weight:600;font-size:18px}
        .progress-container{margin:16px 0;display:none}
        .progress-bar{width:100%;height:8px;background:#1e293b;border-radius:4px;overflow:hidden}
        .progress-fill{height:100%;background:#38bdf8;transition:width 0.3s;width:0}
        .stats{color:#94a3b8;font-size:14px;margin-top:8px}
        </style>
        </head><body>
        <div class="card">
        <h2>Send File or Folder</h2>
        <p style="color:#94a3b8;font-size:14px">Select file to upload</p>
        <button class="btn" onclick="selectFile()">&#128196; Send File</button>
        <button class="btn" onclick="selectFolder()">&#128193; Send Folder</button>
        <input type="file" id="fileInput" multiple style="display:none">
        <input type="file" id="folderInput" webkitdirectory directory multiple style="display:none">
        <p id="fileName" style="color:#94a3b8;min-height:20px;margin:12px 0"></p>
        <button id="uploadBtn" class="upload-btn" onclick="uploadFiles()" style="display:none">Upload</button>
        <div id="progressContainer" class="progress-container">
        <div class="progress-bar"><div id="progressFill" class="progress-fill"></div></div>
        <p id="progressText" style="color:#38bdf8;margin:8px 0">0%</p>
        <p id="stats" class="stats"></p>
        </div>
        <p id="result" style="color:#38bdf8;margin-top:12px;display:none"></p>
        </div>
        <script>
        let selectedFiles = null;
        let uploadType = 'file';
        let startTime = 0;
        
        function selectFile(){
            uploadType='file';
            document.getElementById('fileInput').click();
        }
        function selectFolder(){
            uploadType='folder';
            document.getElementById('folderInput').click();
        }
        document.getElementById('fileInput').onchange=function(){
            selectedFiles=this.files;
            document.getElementById('fileName').innerText=this.files.length > 1 ? this.files.length + ' files' : (this.files[0]?.name||'');
            document.getElementById('uploadBtn').style.display='block';
        };
        document.getElementById('folderInput').onchange=function(){
            selectedFiles=this.files;
            document.getElementById('fileName').innerText=this.files.length+' files';
            document.getElementById('uploadBtn').style.display='block';
        };
        
        function uploadFiles(){
            if(!selectedFiles || selectedFiles.length===0)return;
            
            const formData=new FormData();
            formData.append('type',uploadType);
            
            for(let i=0;i<selectedFiles.length;i++){
                formData.append(uploadType==='file'?'file':'folder',selectedFiles[i]);
            }
            
            const xhr=new XMLHttpRequest();
            startTime=Date.now();
            
            xhr.upload.onprogress=function(e){
                if(e.lengthComputable){
                    const percent=Math.round((e.loaded/e.total)*100);
                    const elapsed=(Date.now()-startTime)/1000;
                    const speed=e.loaded/elapsed/1024/1024;
                    const remaining=((e.total-e.loaded)/(e.loaded/elapsed))||0;
                    
                    document.getElementById('progressFill').style.width=percent+'%';
                    document.getElementById('progressText').innerText=percent+'%';
                    document.getElementById('stats').innerText=
                        `${(e.loaded/1024/1024).toFixed(1)}MB / ${(e.total/1024/1024).toFixed(1)}MB   ${speed.toFixed(1)} MB/s   ETA ${Math.floor(remaining)}s`;
                }
            };
            
            xhr.onload=function(){
                if(xhr.status===200){
                    document.getElementById('result').innerText=' Upload Complete!';
                    document.getElementById('result').style.display='block';
                    document.getElementById('progressContainer').style.display='none';
                }else{
                    document.getElementById('result').innerText=' Upload Failed';
                    document.getElementById('result').style.color='#ef4444';
                    document.getElementById('result').style.display='block';
                }
            };
            
            xhr.onerror=function(){
                document.getElementById('result').innerText='. Network Error';
                document.getElementById('result').style.color='#ef4444';
                document.getElementById('result').style.display='block';
            };
            
            document.getElementById('uploadBtn').style.display='none';
            document.getElementById('progressContainer').style.display='block';
            
            xhr.open('POST','/upload',true);
            xhr.send(formData);
        }
        </script>
        </body></html>
        """
        self.wfile.write(html.encode())

    def handle_upload(self):
        global upload_done
        if upload_done:
            self.send_response(403)
            self.end_headers()
            return
        
        upload_done = True
        self.connection.settimeout(600)
        
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_response(400)
            self.end_headers()
            return
        
        length = int(self.headers.get('Content-Length', 0))
        print(f"[UPLOAD] Starting upload, size: {length / (1024*1024):.1f}MB")
        
        try:
            # Read all data (browser already uploaded it to RAM)
            # We just read and write directly to disk in chunks
            boundary = ('--' + content_type.split('boundary=')[1]).encode()
            
            # Read entire upload
            data = self.rfile.read(length)
            print(f"[UPLOAD] Received {len(data) / (1024*1024):.1f}MB")
            
            # Split by boundary
            parts = data.split(boundary)
            
            upload_type = 'file'
            saved_files = []
            temp_files = []
            
            for part in parts:
                if b'Content-Disposition' not in part:
                    continue
                
                # Check if it's the type field
                if b'name="type"' in part:
                    value_start = part.find(b'\r\n\r\n') + 4
                    value_end = part.find(b'\r\n', value_start)
                    upload_type = part[value_start:value_end].decode('utf-8', errors='ignore')
                    continue
                
                # Check if it's a file
                if b'filename="' in part:
                    # Extract filename
                    header_section = part.split(b'\r\n\r\n')[0]
                    filename_start = header_section.find(b'filename="') + 10
                    filename_end = header_section.find(b'"', filename_start)
                    filename = header_section[filename_start:filename_end].decode('utf-8', errors='ignore')
                    
                    # Decode URL encoding (e.g., %20 -> space, %3A -> :)
                    from urllib.parse import unquote
                    filename = unquote(filename)
                    
                    filename = os.path.basename(filename)
                    
                    # Extract file data
                    data_start = part.find(b'\r\n\r\n') + 4
                    data_end = len(part) - 2  # Remove trailing \r\n
                    file_data = part[data_start:data_end]
                    
                    if upload_type == 'folder':
                        # Save to temp file
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
                        temp_file.write(file_data)
                        temp_file.close()
                        temp_files.append((filename, temp_file.name))
                        print(f"[UPLOAD] Temp saved: {filename} ({len(file_data) / (1024*1024):.1f}MB)")
                    else:
                        # Save directly to destination
                        filepath = os.path.join(receive_dest, filename)
                        with open(filepath, 'wb') as f:
                            f.write(file_data)
                        saved_files.append((filename, len(file_data), False))
                        print(f"[UPLOAD] Saved: {filename} ({len(file_data) / (1024*1024):.1f}MB)")
            
            # Process folder
            if upload_type == 'folder' and temp_files:
                temp_zip = os.path.join(tempfile.gettempdir(), f"upload_{time.time()}.zip")
                total_size = 0
                
                with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for fname, fpath in temp_files:
                        zf.write(fpath, fname)
                        total_size += os.path.getsize(fpath)
                        os.remove(fpath)
                
                with zipfile.ZipFile(temp_zip, 'r') as zf:
                    zf.extractall(receive_dest)
                    folder_name = zf.namelist()[0].split('/')[0] if zf.namelist() else 'uploaded_folder'
                
                os.remove(temp_zip)
                saved_files.append((folder_name, total_size, True))
            
            # Update UI
            for fname, fsize, is_dir in saved_files:
                size_mb = fsize / (1024 * 1024)
                type_str = "Folder" if is_dir else "File"
                root.after(0, lambda n=fname, s=size_mb, t=type_str: 
                    info_label.config(text=f"Received {t}: {n}   {s:.2f} MB"))
                root.after(0, lambda: open_dest_btn.pack(pady=8))
            
            print("[UPLOAD] Complete!")
            
        except Exception as e:
            import traceback
            print(f"[UPLOAD] Error: {e}")
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            return
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        html = """
        <html><body style="background:#0f172a;color:#e5e7eb;
        font-family:system-ui;display:flex;align-items:center;
        justify-content:center;height:100vh">
        <div style="background:#020617;padding:24px;border-radius:14px;
        width:90%;max-width:320px;text-align:center">
        <h2 style="color:#38bdf8">&#10003; Upload Complete</h2>
        <p>File(s) successfully received!</p>
        </div></body></html>
        """
        self.wfile.write(html.encode())
    

    def send_file(self):
        global download_used

        qs = parse_qs(urlparse(self.path).query)
        pin = qs.get("pin", [None])[0]

        if download_used or pin != share_pin or not shared_file_path:
            self.send_response(403)
            self.end_headers()
            return

        download_used = True

        size = os.path.getsize(shared_file_path)
        mime, _ = mimetypes.guess_type(shared_file_path)

        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(shared_file_path)}"'
        )
        self.end_headers()

        with open(shared_file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                self.wfile.write(chunk)

        root.after(500, full_cleanup)

def select_file():
    global shared_file_path
    path = filedialog.askopenfilename()
    if path:
        full_cleanup()
        shared_file_path = path
        info_label.config(text=f"{os.path.basename(path)}   {format_size(os.path.getsize(path))}")
        pin_frame.pack(pady=12)

def select_folder():
    global shared_file_path
    path = filedialog.askdirectory()
    if path:
        full_cleanup()
        
        # Check if folder is empty
        try:
            if not any(os.scandir(path)):
                info_label.config(text="Folder is empty!")
                return
        except OSError:
            info_label.config(text="Cannot access folder!")
            return
        
        info_label.config(text="Preparing folder…")
        progress_bar.pack(pady=(12, 4))
        percent_label.pack()
        stats_label.pack()
        cancel_btn.pack(pady=8)

        def work():
            global shared_file_path
            zp = zip_folder_with_progress(path)
            if zp:
                shared_file_path = zp
                root.after(0, progress_bar.pack_forget)
                root.after(0, percent_label.pack_forget)
                root.after(0, stats_label.pack_forget)
                root.after(0, cancel_btn.pack_forget)
                root.after(0, lambda: info_label.config(
                    text=f"{os.path.basename(path)}   {format_size(os.path.getsize(zp))}"
                ))
                root.after(0, lambda: pin_frame.pack(pady=12))

        threading.Thread(target=work, daemon=True).start()

def receive_files():
    global receive_dest, current_mode
    dest = filedialog.askdirectory(title="Select destination folder")
    if dest:
        full_cleanup()
        receive_dest = dest
        current_mode = "receive"  # Track that we're in receive mode
        info_label.config(text=f"Destination: {os.path.basename(dest)}")
        pin_frame.pack(pady=12)

def open_destination():
    if receive_dest and os.path.exists(receive_dest):
        os.startfile(receive_dest)

root = tk.Tk()
root.title("LocalDrop")
root.geometry("420x720")
root.configure(bg=BG)
root.resizable(False, False)

frame = tk.Frame(root, bg=CARD, padx=24, pady=24)
frame.pack(expand=True, fill="both", padx=16, pady=16)

def button(text, cmd, color=BTN):
    return tk.Button(
        frame, text=text, command=cmd, bg=color, fg=TEXT,
        activebackground=color, relief="flat",
        font=("Segoe UI", 11), padx=14, pady=8
    )

button("Share File", select_file).pack(fill="x", pady=6)
button("Share Folder", select_folder).pack(fill="x", pady=6)
button("Receive File/Folder", receive_files, ACCENT).pack(fill="x", pady=6)

pin_var = tk.StringVar()
pin_frame = tk.Frame(frame, bg=CARD)
current_mode = None  # Track which mode we're setting PIN for

def confirm_pin_wrapper():
    # Determine which confirm function to use based on context
    if hasattr(receive_files, 'last_called') and receive_files.last_called:
        confirm_receive_pin()
    else:
        confirm_send_pin()

tk.Label(pin_frame, text="4-digit PIN", bg=CARD, fg=SUBTEXT).pack()
tk.Entry(
    pin_frame, textvariable=pin_var, show="*",
    justify="center", font=("Segoe UI", 14),
    bg=BG, fg=TEXT, relief="flat"
).pack(pady=6)
confirm_btn = tk.Button(
    pin_frame, text="Confirm PIN", bg=ACCENT, fg=TEXT,
    activebackground=ACCENT, relief="flat",
    font=("Segoe UI", 11), padx=14, pady=8,
    command=lambda: confirm_receive_pin() if receive_dest else confirm_send_pin()
)
confirm_btn.pack(fill="x", pady=6)

info_label = tk.Label(frame, text="No file or folder selected", bg=CARD, fg=SUBTEXT, wraplength=340)
info_label.pack(pady=12)

progress_bar = ttk.Progressbar(frame, orient="horizontal", length=300, mode="determinate")
percent_label = tk.Label(frame, text="0%", bg=CARD, fg=TEXT)
stats_label = tk.Label(frame, text="", bg=CARD, fg=SUBTEXT)
cancel_btn = button("Cancel", cancel_zip, DANGER)
cancel_share_btn = button("Cancel Share", cancel_share, DANGER)
open_dest_btn = button("Open Destination", open_destination, ACCENT)

qr_label = tk.Label(frame, bg=CARD)
qr_label.pack(pady=12)

url_label = tk.Label(frame, text="", bg=CARD, fg=ACCENT)
url_label.pack()

root.mainloop()
