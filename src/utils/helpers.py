# src/utils/helpers.py
import os
import sys
import subprocess

def format_size(bytes_num):
    """Format bytes into readable units."""
    if bytes_num is None:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_num) < 1024.0:
            return f"{bytes_num:.1f} {unit}" if unit != 'B' else f"{int(bytes_num)} B"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} PB"

def format_time(seconds):
    """Format seconds into readable human time."""
    if seconds < 0 or seconds > 86400:
        return "--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m {s}s"

def open_folder(path):
    """Open folder across Linux, Windows, and macOS."""
    if not path or not os.path.exists(path):
        return False
    try:
        if sys.platform.startswith('win'):
            os.startfile(path)
        elif sys.platform.startswith('darwin'):
            subprocess.Popen(['open', path])
        else:
            subprocess.Popen(['xdg-open', path])
        return True
    except Exception as e:
        print(f"Error opening folder: {e}")
        return False
