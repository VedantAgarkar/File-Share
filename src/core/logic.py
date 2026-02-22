# src/core/logic.py
import os
import time
import zipfile
import tempfile
import shutil
from src.utils.helpers import format_time

def zip_folder_with_progress(folder_path, progress_callback, cancel_check_callback):
    """
    Zips a folder and reports progress via callbacks.
    progress_callback: func(done_bytes, percent, speed, remaining)
    cancel_check_callback: func() -> bool
    """
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

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if cancel_check_callback():
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                return None, None

            z.write(f, os.path.relpath(f, folder_path))
            size = os.path.getsize(f)
            zip_done_bytes += size

            elapsed = time.time() - zip_start_time
            speed = (zip_done_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0
            remaining = (zip_total_bytes - zip_done_bytes) / (speed * 1024 * 1024) if speed > 0 and zip_done_bytes < zip_total_bytes else 0
            percent = int((zip_done_bytes / zip_total_bytes) * 100) if zip_total_bytes > 0 else 0

            progress_callback(zip_done_bytes, percent, speed, remaining, zip_total_bytes)

    return zip_path, temp_dir
