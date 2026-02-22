# src/core/server.py
import http.server
import socketserver
import socket
import os
import mimetypes
import time
import zipfile
import tempfile
from urllib.parse import urlparse, parse_qs, unquote
from src.config import CHUNK_SIZE

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    timeout = 300
    
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        super().server_bind()

class DownloadHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

    @property
    def app(self):
        # The server instance will have a reference to the main app controller
        return self.server.app_controller

    def do_GET(self):
        try:
            if self.app.mode == "send":
                if self.path.startswith("/download"):
                    self.send_file()
                else:
                    self.show_pin_page()
            elif self.app.mode == "receive":
                if self.path == "/verified":
                    self.show_upload_options()
                else:
                    self.show_receive_pin_page()
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"Service not ready")
        except Exception as e:
            print(f"ERROR in do_GET: {e}")
            self.send_response(500)
            self.end_headers()

    def do_POST(self):
        try:
            if self.app.mode == "receive" and self.path == "/verify":
                self.verify_receive_pin()
            elif self.app.mode == "receive" and self.path == "/upload":
                self.handle_upload()
            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            print(f"ERROR in do_POST: {e}")
            self.send_response(500)
            self.end_headers()

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
        
        if pin == self.app.share_pin:
            self.send_response(303)
            self.send_header("Location", "/verified")
            self.end_headers()
        else:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid PIN")

    def show_upload_options(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
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
        if self.app.upload_done:
            self.send_response(403)
            self.end_headers()
            return
        
        self.app.upload_done = True
        self.connection.settimeout(600)
        
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_response(400)
            self.end_headers()
            return
        
        length = int(self.headers.get('Content-Length', 0))
        boundary = ('--' + content_type.split('boundary=')[1]).encode()
        data = self.rfile.read(length)
        parts = data.split(boundary)
        
        upload_type = 'file'
        saved_files = []
        temp_files = []
        
        for part in parts:
            if b'Content-Disposition' not in part:
                continue
            
            if b'name="type"' in part:
                value_start = part.find(b'\r\n\r\n') + 4
                value_end = part.find(b'\r\n', value_start)
                upload_type = part[value_start:value_end].decode('utf-8', errors='ignore')
                continue
            
            if b'filename="' in part:
                header_section = part.split(b'\r\n\r\n')[0]
                filename_start = header_section.find(b'filename="') + 10
                filename_end = header_section.find(b'"', filename_start)
                filename = unquote(header_section[filename_start:filename_end].decode('utf-8', errors='ignore'))
                filename = os.path.basename(filename)
                
                data_start = part.find(b'\r\n\r\n') + 4
                data_end = len(part) - 2
                file_data = part[data_start:data_end]
                
                if upload_type == 'folder':
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
                    temp_file.write(file_data)
                    temp_file.close()
                    temp_files.append((filename, temp_file.name))
                else:
                    filepath = os.path.join(self.app.receive_dest, filename)
                    with open(filepath, 'wb') as f:
                        f.write(file_data)
                    saved_files.append((filename, len(file_data), False))
        
        if upload_type == 'folder' and temp_files:
            temp_zip = os.path.join(tempfile.gettempdir(), f"upload_{time.time()}.zip")
            total_size = 0
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for fname, fpath in temp_files:
                    zf.write(fpath, fname)
                    total_size += os.path.getsize(fpath)
                    os.remove(fpath)
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                zf.extractall(self.app.receive_dest)
                folder_name = zf.namelist()[0].split('/')[0] if zf.namelist() else 'uploaded_folder'
            os.remove(temp_zip)
            saved_files.append((folder_name, total_size, True))
        
        for fname, fsize, is_dir in saved_files:
            self.app.report_received(fname, fsize, is_dir)
            
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Upload Complete")

    def send_file(self):
        qs = parse_qs(urlparse(self.path).query)
        pin = qs.get("pin", [None])[0]

        if self.app.download_used or pin != self.app.share_pin or not self.app.shared_file_path:
            self.send_response(403)
            self.end_headers()
            return

        self.app.download_used = True
        size = os.path.getsize(self.app.shared_file_path)
        mime, _ = mimetypes.guess_type(self.app.shared_file_path)

        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(self.app.shared_file_path)}"')
        self.end_headers()

        with open(self.app.shared_file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                self.wfile.write(chunk)

        self.app.on_transfer_complete()
