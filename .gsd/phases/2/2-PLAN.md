---
phase: 2
plan: 2
wave: 2
---

# Plan 2.2: Server and Handler Modularization

## Objective
Migrate the HTTP server and handler logic into a dedicated module, decoupling it from the UI globals.

## Context
- .gsd/SPEC.md
- app.py
- src/config.py

## Tasks

<task type="auto">
  <name>Create Server and Handler Module</name>
  <files>src/core/server.py</files>
  <action>
    - Migrate `ThreadedTCPServer` and `DownloadHandler` to `src/core/server.py`.
    - Refactor `DownloadHandler` to use a passed-in state object or interface for UI updates (e.g., `app_state` instead of globals).
    - ensure imports from `src.config` are used for PORT and CHUNK_SIZE.
  </action>
  <verify>Check `src/core/server.py` for correct class definitions and modular imports.</verify>
  <done>`DownloadHandler` and `ThreadedTCPServer` are decoupled from UI globals.</done>
</task>

## Success Criteria
- [ ] Server logic isolated in `server.py`.
- [ ] No direct references to Tkinter UI elements inside the server module.
