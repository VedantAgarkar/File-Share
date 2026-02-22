---
phase: 2
plan: 3
wave: 3
---

# Plan 2.3: UI Modularization and Assembly

## Objective
Migrate the Tkinter UI into a class-based module and create the main entry point to run the application.

## Context
- .gsd/SPEC.md
- app.py
- src/core/server.py
- src/core/logic.py

## Tasks

<task type="auto">
  <name>Create UI Module and Main Entry</name>
  <files>src/ui/app_ui.py, main.py</files>
  <action>
    - Refactor the Tkinter UI code in `app.py` into a `LocalDropUI` class in `src/ui/app_ui.py`.
    - Create `main.py` as the entry point.
    - Initialize the UI and link it with the Server logic.
    - Ensure all previous functionality (PIN, Share, Receive, Multi-file) works through the new assembly.
  </action>
  <verify>Run `python main.py` and verify UI loads and functions.</verify>
  <done>Application runs from `main.py` with full previous functionality.</done>
</task>

<task type="auto">
  <name>Cleanup and Validation</name>
  <files>app.py</files>
  <action>
    - Once `main.py` is verified, rename old `app.py` to `app.py.bak` or archive it.
    - Ensure `requirements.txt` is updated (or created) with `qrcode` and `Pillow`.
  </action>
  <verify>Check for existence of `main.py` and modular `src/` directory.</verify>
  <done>Codebase is clean and modular.</done>
</task>

## Success Criteria
- [ ] Application starts successfully from `main.py`.
- [ ] Code is organized into logical modules.
- [ ] Functional parity with the original monolithic `app.py`.
