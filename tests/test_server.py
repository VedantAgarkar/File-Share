import unittest
import threading
import urllib.request
import urllib.error
import tempfile
import os
import shutil
import time

from src.core.server import ThreadedTCPServer, DownloadHandler

class DummyAppController:
    def __init__(self):
        self.mode = "send"
        self.shared_file_path = None
        self.shared_text = None
        self.share_pin = None
        self.receive_dest = None
        self.active_clients = set()
        self.completed = []

    def notify_client_connected(self, ip):
        self.active_clients.add(ip)

    def notify_client_disconnected(self, ip):
        self.active_clients.discard(ip)

    def on_download_complete(self, ip, fname, size):
        self.completed.append((ip, fname, size))

    def report_received(self, fname, size):
        self.completed.append((fname, size))

class TestServerConcurrency(unittest.TestCase):
    def setUp(self):
        self.app = DummyAppController()
        # Bind to port 8009 for tests
        self.port = 8009
        self.server = ThreadedTCPServer(("127.0.0.1", self.port), DownloadHandler)
        self.server.app_controller = self.app
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        # Create dummy file to share
        self.temp_dir = tempfile.mkdtemp()
        self.dummy_file = os.path.join(self.temp_dir, "testfile.dat")
        with open(self.dummy_file, "wb") as f:
            f.write(b"0123456789" * 10000)  # 100 KB
        self.app.shared_file_path = self.dummy_file

    def tearDown(self):
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_multi_client_concurrent_downloads(self):
        url = f"http://127.0.0.1:{self.port}/download"
        errors = []

        def client_job():
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = resp.read()
                    if len(data) != 100000:
                        errors.append(f"Bad length: {len(data)}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=client_job) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors occurred during concurrent downloads: {errors}")
        self.assertEqual(len(self.app.completed), 5)

    def test_text_sharing_portal(self):
        self.app.mode = "text"
        self.app.shared_text = "https://example.com/shared-link"
        url = f"http://127.0.0.1:{self.port}/"
        with urllib.request.urlopen(url, timeout=5) as resp:
            content = resp.read().decode("utf-8")
            self.assertIn("Shared Content", content)
            self.assertIn("https://example.com/shared-link", content)

if __name__ == "__main__":
    unittest.main()
