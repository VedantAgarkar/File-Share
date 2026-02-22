---
phase: 4
plan: 1
wave: 1
---

# Plan 4.1: Standalone Executable Build

## Objective
Convert the modular Python application into a standalone Windows executable.

## Context
- .gsd/SPEC.md
- main.py
- LocalDrop.spec

## Tasks

<task type="auto">
  <name>Update PyInstaller Spec</name>
  <files>LocalDrop.spec</files>
  <action>
    - Update `Analysis` to use `main.py` instead of `app.py`.
    - Ensure `pathex` includes the current directory to resolve `src` imports correctly.
    - Confirm the name is `LocalDrop`.
  </action>
  <verify>Verify `LocalDrop.spec` content.</verify>
  <done>`LocalDrop.spec` points to `main.py` and has correct pathing.</done>
</task>

<task type="auto">
  <name>Build Executable</name>
  <files>dist/LocalDrop.exe</files>
  <action>
    - Run PyInstaller using the updated `.spec` file.
    - Verify that the `dist` directory is created and contains the `.exe`.
  </action>
  <verify>Check for existence of `dist/LocalDrop.exe`.</verify>
  <done>Executable build completes successfully.</done>
</task>

## Success Criteria
- [ ] `LocalDrop.exe` is generated in the `dist` folder.
- [ ] The app starts without a terminal window.
