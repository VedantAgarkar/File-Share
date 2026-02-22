# Research: Phase 2 Refactoring Strategy

## Global Variables Mapping
The current `app.py` relies heavily on global variables:
- `httpd`: Server instance
- `mode`: 'send' or 'receive'
- `shared_file_path`: Current file/folder being shared
- `temp_dir`: Temporary ZIP path
- `share_pin`: 4-digit PIN
- `download_used`: Transfer lock
- `upload_done`: Transfer lock
- `qr_img`: UI image reference
- `bind_ip`: Local IP
- `receive_dest`: Dest dir for receive mode
- `zip_cancelled`, `zip_start_time`, etc.: ZIP progress state

## Dependencies
- `DownloadHandler` needs access to `shared_file_path`, `share_pin`, `mode`, `receive_dest`, and `root.after` for UI updates.
- `zip_folder_with_progress` needs access to `root.after` and several global zip state vars.

## Proposed Class-Based Approach
Create a `LocalDropApp` class to hold state, and a `TransferServer` class to handle the HTTP logic.
Pass the UI instance or a callback to the server for status updates.

## Decision: Module Layout
1. `config.py`: Constants (PORT, COLORS, CHUNK_SIZE).
2. `utils.py`: `get_local_ip`, `format_size`, `format_time`.
3. `logic.py`: ZIP logic (requires threading context).
4. `server.py`: `DownloadHandler` and `ThreadedTCPServer`.
5. `ui.py`: `LocalDropUI` (Tkinter class).
6. `main.py`: Runner.

## Risk Analysis
- **Circular Imports**: Server needs UI for updates, UI needs Server to start. Use callbacks or a SharedState object.
- **Tkinter Thread Safety**: Ensure all UI updates happen via `root.after`.
