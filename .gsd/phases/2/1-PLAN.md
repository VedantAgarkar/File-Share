---
phase: 2
plan: 1
wave: 1
---

# Plan 2.1: Foundation and Utility Migration

## Objective
Establish the new directory structure and migrate non-UI logic (constants, helpers, networking) out of `app.py`.

## Context
- .gsd/SPEC.md
- .gsd/phases/2/RESEARCH.md
- app.py

## Tasks

<task type="auto">
  <name>Setup directory structure and constants</name>
  <files>src/config.py, src/utils/helpers.py</files>
  <action>
    - Create `src/` directory.
    - Create `src/config.py` and migrate all color constants (BG, CARD, etc.), PORT, and CHUNK_SIZE.
    - Create `src/utils/helpers.py` and migrate `format_size` and `format_time`.
  </action>
  <verify>Check files exist and contain the migrated constants/functions.</verify>
  <done>`src/config.py` and `src/utils/helpers.py` are populated.</done>
</task>

<task type="auto">
  <name>Migrate Networking and Zip logic</name>
  <files>src/utils/network.py, src/core/logic.py</files>
  <action>
    - Create `src/utils/network.py` and migrate `get_local_ip`.
    - Create `src/core/logic.py` and migrate `zip_folder_with_progress`. 
    - Note: `zip_folder_with_progress` will need to accept a `progress_callback` instead of directly accessing `root.after` and global UI variables.
  </action>
  <verify>Check files exist and functions are syntactically correct.</verify>
  <done>Networking and ZIP logic migrated to standalone functions.</done>
</task>

## Success Criteria
- [ ] New folder structure created.
- [ ] Core utilities and constants removed from global scope of what will be specialized files.
