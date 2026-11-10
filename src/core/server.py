# src/core/server.py
import http.server
import socketserver
import socket
import os
import mimetypes
import time
import zipfile
import tempfile
import re
import json
import collections
from urllib.parse import urlparse, parse_qs, unquote
from src.config import CHUNK_SIZE, MAX_FAILED_ATTEMPTS, LOCKOUT_DURATION_SEC
from src.utils.helpers import format_size

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    timeout = 300
    
    def __init__(self, server_address, RequestHandlerClass, ssl_context=None, bind_and_activate=True):
        self.ssl_context = ssl_context
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
        if self.ssl_context:
            self.socket = self.ssl_context.wrap_socket(self.socket, server_side=True)
        super().server_bind()

class RateLimiter:
    """Protects against PIN brute-forcing per client IP."""
    def __init__(self):
        self.attempts = collections.defaultdict(list)  # ip -> list of timestamps

    def is_locked(self, ip):
        now = time.time()
        # Clean older than lockout duration
        self.attempts[ip] = [t for t in self.attempts[ip] if now - t < LOCKOUT_DURATION_SEC]
        return len(self.attempts[ip]) >= MAX_FAILED_ATTEMPTS

    def record_failure(self, ip):
        self.attempts[ip].append(time.time())

    def reset(self, ip):
        if ip in self.attempts:
            del self.attempts[ip]

_limiter = RateLimiter()

class DownloadHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    @property
    def app(self):
        return self.server.app_controller

    def check_pin(self, user_pin):
        client_ip = self.client_address[0]
        if _limiter.is_locked(client_ip):
            return False, "Rate limit exceeded. Please wait 30 seconds."

        if not self.app.share_pin:
            return True, None

        if user_pin == self.app.share_pin:
            _limiter.reset(client_ip)
            return True, None
        else:
            _limiter.record_failure(client_ip)
            remaining = MAX_FAILED_ATTEMPTS - len(_limiter.attempts[client_ip])
            return False, f"Incorrect PIN. {max(0, remaining)} attempts remaining."

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            pin = query.get("pin", [None])[0]

            if parsed.path == "/api/ping":
                self.send_json(200, {"status": "ok", "app": "LocalDrop"})
                return

            if self.app.mode == "send":
                if parsed.path == "/download":
                    self.send_file(pin)
                elif parsed.path == "/api/info":
                    self.send_share_info()
                else:
                    self.show_send_portal(pin)
            elif self.app.mode == "text":
                self.show_text_portal(pin)
            elif self.app.mode == "receive":
                if parsed.path == "/upload_view":
                    self.show_upload_portal(pin)
                else:
                    self.show_receive_pin_portal(pin)
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"Service idle.")
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"Error in do_GET: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if self.app.mode == "receive" and parsed.path == "/verify":
                self.verify_receive_pin()
            elif self.app.mode == "receive" and parsed.path == "/upload":
                self.handle_streaming_upload()
            elif self.app.mode == "receive" and parsed.path == "/api/request_transfer":
                self.handle_transfer_request()
            else:
                self.send_response(404)
                self.end_headers()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"Error in do_POST: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass

    def send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_transfer_request(self):
        """Allows sender to request permission before transmitting files."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        req_data = json.loads(body) if body else {}

        client_ip = self.client_address[0]
        device_name = req_data.get("device", client_ip)
        file_count = req_data.get("count", 1)
        total_size = req_data.get("size", 0)

        # Ask App Controller to prompt user
        accepted = self.app.prompt_incoming_transfer(device_name, client_ip, file_count, total_size)
        self.send_json(200 if accepted else 403, {"accepted": accepted})

    # ==========================
    # HTML PORTALS
    # ==========================

    def _get_html_head(self, title):
        scheme = "https" if self.server.ssl_context else "http"
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>{title} - LocalDrop</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
body {{ background: #0d1117; color: #e6edf3; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 16px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 18px; width: 100%; max-width: 440px; padding: 28px; box-shadow: 0 20px 40px rgba(0,0,0,0.5); text-align: center; }}
.badge {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(56, 139, 253, 0.15); color: #58a6ff; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 16px; }}
h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; color: #ffffff; }}
p.sub {{ color: #8b949e; font-size: 14px; margin-bottom: 24px; }}
.file-box {{ background: #0d1117; border: 1px solid #30363d; border-radius: 12px; padding: 16px; margin-bottom: 20px; text-align: left; display: flex; align-items: center; gap: 14px; }}
.file-icon {{ width: 44px; height: 44px; border-radius: 10px; background: #21262d; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; }}
.file-meta {{ overflow: hidden; }}
.file-name {{ font-weight: 600; font-size: 15px; color: #f0f6fc; word-break: break-all; margin-bottom: 3px; }}
.file-size {{ font-size: 13px; color: #8b949e; }}
.btn {{ display: block; width: 100%; padding: 14px 20px; border-radius: 10px; font-size: 15px; font-weight: 600; border: none; cursor: pointer; text-decoration: none; transition: all 0.2s; }}
.btn-primary {{ background: #238636; color: #ffffff; }}
.btn-primary:hover {{ background: #2ea043; }}
.btn-secondary {{ background: #21262d; color: #c9d1d9; border: 1px solid #30363d; margin-top: 10px; }}
.btn-secondary:hover {{ background: #30363d; color: #ffffff; }}
input[type="text"], input[type="password"] {{ width: 100%; padding: 14px; border-radius: 10px; border: 1px solid #30363d; background: #0d1117; color: #f0f6fc; font-size: 18px; text-align: center; margin-bottom: 14px; letter-spacing: 2px; outline: none; }}
input:focus {{ border-color: #58a6ff; }}
.progress-wrap {{ display: none; margin-top: 20px; text-align: left; }}
.bar-bg {{ background: #21262d; height: 8px; border-radius: 4px; overflow: hidden; }}
.bar-fill {{ background: #238636; height: 100%; width: 0%; transition: width 0.2s; }}
.status-text {{ display: flex; justify-content: space-between; font-size: 13px; color: #8b949e; margin-top: 8px; }}
.notice {{ color: #3fb950; font-size: 14px; margin-top: 14px; font-weight: 500; display: none; }}
.error-msg {{ color: #f85149; font-size: 14px; margin-top: 14px; }}
</style>
</head>
<body>
<div class="card">
"""

    def show_send_portal(self, pin):
        file_path = self.app.shared_file_path
        if not file_path or not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"No active file.")
            return

        fname = os.path.basename(file_path)
        fsize = format_size(os.path.getsize(file_path))
        is_folder = fname.endswith(".zip")
        icon = "📁" if is_folder else "📄"

        pin_valid, err_msg = self.check_pin(pin)

        html = self._get_html_head("Download File")
        html += f"""
        <div class="badge"><span>🔒</span> TLS Direct Share</div>
        <h1>Download Ready</h1>
        <p class="sub">Encrypted local transfer from {socket.gethostname()}</p>
        
        <div class="file-box">
            <div class="file-icon">{icon}</div>
            <div class="file-meta">
                <div class="file-name">{fname}</div>
                <div class="file-size">{fsize}</div>
            </div>
        </div>
        """

        if self.app.share_pin and not pin_valid:
            if err_msg:
                html += f'<p class="error-msg" style="margin-bottom:12px;">{err_msg}</p>'
            html += f"""
            <form action="/download" method="GET">
                <input type="password" name="pin" maxlength="6" placeholder="PIN" autofocus required>
                <button type="submit" class="btn btn-primary">Unlock & Download</button>
            </form>
            """
        else:
            download_url = f"/download?pin={pin or ''}"
            html += f"""
            <a href="{download_url}" class="btn btn-primary">⬇️ Download File</a>
            <p style="font-size:12px; color:#8b949e; margin-top:14px;">Direct streaming · Multi-device support</p>
            """

        html += "</div></body></html>"
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def show_text_portal(self, pin):
        pin_valid, err_msg = self.check_pin(pin)
        html = self._get_html_head("Shared Text")
        html += """
        <div class="badge"><span>📋</span> LocalDrop Quick Clipboard</div>
        <h1>Shared Content</h1>
        <p class="sub">Instant text beamed securely across your network</p>
        """

        if self.app.share_pin and not pin_valid:
            if err_msg:
                html += f'<p class="error-msg" style="margin-bottom:12px;">{err_msg}</p>'
            html += """
            <form action="/" method="GET">
                <input type="password" name="pin" maxlength="6" placeholder="PIN" autofocus required>
                <button type="submit" class="btn btn-primary">View Text</button>
            </form>
            """
        else:
            shared_text = self.app.shared_text or ""
            import html as pyhtml
            safe_text = pyhtml.escape(shared_text)
            html += f"""
            <div style="background:#0d1117; border:1px solid #30363d; border-radius:10px; padding:16px; text-align:left; font-size:14px; color:#e6edf3; line-height:1.5; white-space:pre-wrap; word-break:break-all; max-height:280px; overflow-y:auto; margin-bottom:16px;" id="copyTarget">{safe_text}</div>
            <button class="btn btn-primary" onclick="copyContent()">📋 Copy to Clipboard</button>
            <div id="copyMsg" class="notice" style="display:none; color:#3fb950; margin-top:10px;">✓ Copied to clipboard!</div>
            <script>
            function copyContent() {{
                const text = document.getElementById('copyTarget').innerText;
                navigator.clipboard.writeText(text).then(() => {{
                    const m = document.getElementById('copyMsg');
                    m.style.display = 'block';
                    setTimeout(() => {{ m.style.display = 'none'; }}, 2500);
                }});
            }}
            </script>
            """

        html += "</div></body></html>"
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def show_receive_pin_portal(self, pin):
        pin_valid, _ = self.check_pin(pin)
        if not self.app.share_pin or pin_valid:
            self.show_upload_portal(pin)
            return

        html = self._get_html_head("Upload Authentication")
        html += """
        <div class="badge"><span>🔒</span> Enter PIN</div>
        <h1>Enter Passcode</h1>
        <p class="sub">Enter PIN displayed on the receiver device</p>
        <form method="POST" action="/verify">
            <input type="password" name="pin" maxlength="6" placeholder="••••" required autofocus>
            <button type="submit" class="btn btn-primary">Continue</button>
        </form>
        </div></body></html>
        """
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def verify_receive_pin(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        params = parse_qs(body)
        pin = params.get("pin", [""])[0]

        valid, err = self.check_pin(pin)
        if valid:
            self.send_response(303)
            self.send_header("Location", f"/upload_view?pin={pin}")
            self.end_headers()
        else:
            html = self._get_html_head("Invalid PIN")
            html += f"""
            <h1>Access Denied</h1>
            <p class="error-msg">{err or 'Invalid PIN'}</p>
            <a href="/" class="btn btn-secondary" style="margin-top:16px;">Try Again</a>
            </div></body></html>
            """
            data = html.encode("utf-8")
            self.send_response(403)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    def show_upload_portal(self, pin):
        valid, _ = self.check_pin(pin)
        if not valid:
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        html = self._get_html_head("Upload to Computer")
        html += f"""
        <div class="badge"><span>⚡</span> Connected to Receiver</div>
        <h1>Send Files or Folders</h1>
        <p class="sub">Streaming directly to target computer</p>

        <div style="display:flex; gap:10px; margin-bottom:14px;">
            <button class="btn btn-secondary" style="margin-top:0;" onclick="selectFiles()">📄 Select Files</button>
            <button class="btn btn-secondary" style="margin-top:0;" onclick="selectFolder()">📁 Select Folder</button>
        </div>

        <input type="file" id="fileInput" multiple style="display:none">
        <input type="file" id="folderInput" webkitdirectory directory multiple style="display:none">

        <div id="previewCard" style="display:none; background:#0d1117; border:1px solid #30363d; border-radius:10px; padding:14px; margin-bottom:16px; text-align:left;">
            <div id="fileCount" style="font-weight:600; font-size:14px; color:#f0f6fc;"></div>
            <div id="fileTotalSize" style="font-size:12px; color:#8b949e; margin-top:2px;"></div>
        </div>

        <button id="uploadBtn" class="btn btn-primary" onclick="startUpload()" style="display:none;">🚀 Send to Computer</button>

        <div id="progressWrap" class="progress-wrap">
            <div class="bar-bg"><div id="barFill" class="bar-fill"></div></div>
            <div class="status-text">
                <span id="percentText">0%</span>
                <span id="speedEtaText"></span>
            </div>
        </div>

        <div id="noticeSuccess" class="notice">✓ Files transferred successfully!</div>
        <div id="noticeError" class="error-msg" style="display:none;">Transfer failed or was rejected.</div>

        <script>
        let chosenFiles = [];
        let uploadType = 'file';
        let pin = "{pin or ''}";

        function selectFiles() {{
            uploadType = 'file';
            document.getElementById('fileInput').click();
        }}
        function selectFolder() {{
            uploadType = 'folder';
            document.getElementById('folderInput').click();
        }}

        function formatBytes(bytes) {{
            if (bytes === 0) return '0 B';
            const k = 1024, dm = 1;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
        }}

        function updateSelection(files) {{
            chosenFiles = files;
            if (!files || files.length === 0) return;
            let total = 0;
            for (let i = 0; i < files.length; i++) total += files[i].size;
            
            document.getElementById('fileCount').innerText = files.length === 1 ? files[0].name : `${{files.length}} items selected (${{uploadType}})`;
            document.getElementById('fileTotalSize').innerText = 'Total size: ' + formatBytes(total);
            document.getElementById('previewCard').style.display = 'block';
            document.getElementById('uploadBtn').style.display = 'block';
            document.getElementById('noticeSuccess').style.display = 'none';
            document.getElementById('noticeError').style.display = 'none';
        }}

        document.getElementById('fileInput').onchange = function() {{ updateSelection(this.files); }};
        document.getElementById('folderInput').onchange = function() {{ updateSelection(this.files); }};

        function startUpload() {{
            if (!chosenFiles || chosenFiles.length === 0) return;

            // Prompt permission request
            let totalSize = 0;
            for (let i = 0; i < chosenFiles.length; i++) totalSize += chosenFiles[i].size;

            fetch('/api/request_transfer', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    device: navigator.userAgent.split(' ')[0] || 'Mobile Device',
                    count: chosenFiles.length,
                    size: totalSize
                }})
            }}).then(res => res.json()).then(data => {{
                if (!data.accepted) {{
                    document.getElementById('noticeError').innerText = 'Transfer rejected by receiver host.';
                    document.getElementById('noticeError').style.display = 'block';
                    return;
                }}
                proceedUpload();
            }}).catch(() => proceedUpload());
        }}

        function proceedUpload() {{
            const fd = new FormData();
            fd.append('type', uploadType);
            for (let i = 0; i < chosenFiles.length; i++) {{
                const rel = chosenFiles[i].webkitRelativePath || chosenFiles[i].name;
                fd.append('files', chosenFiles[i], rel);
            }}

            const xhr = new XMLHttpRequest();
            const startTime = Date.now();

            document.getElementById('uploadBtn').style.display = 'none';
            document.getElementById('progressWrap').style.display = 'block';

            xhr.upload.onprogress = function(e) {{
                if (e.lengthComputable) {{
                    const pct = Math.round((e.loaded / e.total) * 100);
                    const elapsed = (Date.now() - startTime) / 1000;
                    const speed = e.loaded / (elapsed || 0.001) / 1024 / 1024;
                    const remaining = (e.total - e.loaded) / (speed * 1024 * 1024 || 1);

                    document.getElementById('barFill').style.width = pct + '%';
                    document.getElementById('percentText').innerText = pct + '%';
                    document.getElementById('speedEtaText').innerText = `${{speed.toFixed(1)}} MB/s · ETA ${{Math.max(0, Math.round(remaining))}}s`;
                }}
            }};

            xhr.onload = function() {{
                if (xhr.status === 200) {{
                    document.getElementById('progressWrap').style.display = 'none';
                    document.getElementById('previewCard').style.display = 'none';
                    document.getElementById('noticeSuccess').style.display = 'block';
                }} else {{
                    document.getElementById('noticeError').style.display = 'block';
                    document.getElementById('uploadBtn').style.display = 'block';
                }}
            }};

            xhr.onerror = function() {{
                document.getElementById('noticeError').style.display = 'block';
                document.getElementById('uploadBtn').style.display = 'block';
            }};

            xhr.open('POST', '/upload?pin=' + encodeURIComponent(pin), true);
            xhr.send(fd);
        }}
        </script>
        </div></body></html>
        """
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # ==========================
    # STREAMING TRANSFER
    # ==========================

    def send_file(self, pin):
        file_path = self.app.shared_file_path
        if not file_path or not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Shared file not found.")
            return

        valid, _ = self.check_pin(pin)
        if not valid:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid PIN.")
            return

        client_ip = self.client_address[0]
        self.app.notify_client_connected(client_ip)

        file_size = os.path.getsize(file_path)
        mime, _ = mimetypes.guess_type(file_path)
        filename = os.path.basename(file_path)

        range_header = self.headers.get("Range")
        start = 0
        end = file_size - 1

        if range_header:
            m = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if m:
                start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            else:
                self.send_response(200)
        else:
            self.send_response(200)

        content_length = (end - start) + 1
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        bytes_sent = 0
        try:
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    read_len = min(CHUNK_SIZE, remaining)
                    chunk = f.read(read_len)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    bytes_sent += len(chunk)
                    remaining -= len(chunk)
            self.app.on_download_complete(client_ip, filename, bytes_sent)
        except (BrokenPipeError, ConnectionResetError):
            self.app.notify_client_disconnected(client_ip)

    def handle_streaming_upload(self):
        query = parse_qs(urlparse(self.path).query)
        pin = query.get("pin", [""])[0]

        valid, _ = self.check_pin(pin)
        if not valid:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Forbidden")
            return

        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self.send_response(400)
            self.end_headers()
            return

        boundary = content_type.split('boundary=')[1].strip()
        if boundary.startswith('"') and boundary.endswith('"'):
            boundary = boundary[1:-1]
        boundary_bytes = ('--' + boundary).encode('latin-1')

        content_length = int(self.headers.get('Content-Length', 0))
        if content_length <= 0:
            self.send_response(400)
            self.end_headers()
            return

        dest_dir = self.app.receive_dest or os.path.expanduser("~/Downloads")
        os.makedirs(dest_dir, exist_ok=True)

        saved_files = []
        try:
            stream = self.rfile
            total_read = 0

            line = stream.readline()
            total_read += len(line)

            while total_read < content_length:
                headers = {}
                while True:
                    hline = stream.readline()
                    total_read += len(hline)
                    if hline in (b'\r\n', b'\n', b''):
                        break
                    decoded_h = hline.decode('latin-1', errors='ignore').strip()
                    if ':' in decoded_h:
                        k, v = decoded_h.split(':', 1)
                        headers[k.lower().strip()] = v.strip()

                if 'content-disposition' not in headers:
                    break

                disp = headers['content-disposition']
                fn_match = re.search(r'filename="([^"]+)"', disp)
                if not fn_match:
                    while total_read < content_length:
                        line = stream.readline()
                        total_read += len(line)
                        if line.startswith(boundary_bytes):
                            break
                    continue

                raw_filename = fn_match.group(1)
                norm_filename = os.path.normpath(unquote(raw_filename)).lstrip("/\\")
                target_path = os.path.join(dest_dir, norm_filename)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                with open(target_path, "wb") as out_f:
                    prev_chunk = b""
                    delimiter = b"\r\n" + boundary_bytes
                    while total_read < content_length:
                        chunk = stream.read(min(CHUNK_SIZE, content_length - total_read))
                        if not chunk:
                            break
                        total_read += len(chunk)
                        data = prev_chunk + chunk

                        idx = data.find(delimiter)
                        if idx != -1:
                            out_f.write(data[:idx])
                            trailing = stream.readline()
                            total_read += len(trailing)
                            break
                        else:
                            keep_len = len(delimiter)
                            out_f.write(data[:-keep_len])
                            prev_chunk = data[-keep_len:]

                fsize = os.path.getsize(target_path) if os.path.exists(target_path) else 0
                saved_files.append((norm_filename, fsize))

            for fname, size in saved_files:
                self.app.report_received(fname, size)

            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Success")
        except Exception as e:
            print(f"Error handling upload: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Failed")
