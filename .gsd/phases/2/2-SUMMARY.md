# Summary - Plan 2.2

## Objective
Migrate the HTTP server and handler logic into a dedicated module.

## Changes
- Created `src/core/server.py`.
- Migrated `ThreadedTCPServer` and `DownloadHandler`.
- Refactored `DownloadHandler` to interact with a controller object (`self.server.app_controller`) instead of global variables.
- Removed direct references to UI and globals, using property accessors instead.

## Verification Results
- `src/core/server.py` is syntactically correct.
- Handler logic is now agnostic of UI implementation details.
