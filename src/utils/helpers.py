# src/utils/helpers.py

def format_size(b):
    return f"{b / (1024 * 1024):.2f} MB"

def format_time(sec):
    if sec < 0:
        return "--"
    m, s = divmod(int(sec), 60)
    return f"{m}m {s}s"
