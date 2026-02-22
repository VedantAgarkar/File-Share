---
phase: 3
plan: 1
wave: 1
---

# Plan 3.1: Utility and Core Logic Testing

## Objective
Implement unit tests for helper functions and the ZIP logic.

## Context
- .gsd/SPEC.md
- src/utils/helpers.py
- src/utils/network.py
- src/core/logic.py

## Tasks

<task type="auto">
  <name>Setup test environment and utility tests</name>
  <files>tests/test_utils.py</files>
  <action>
    - Create `tests/` directory.
    - Implement tests for `format_size` and `format_time` in `tests/test_utils.py`.
    - Implement tests for `get_local_ip` using `unittest.mock` to simulate various networking states.
  </action>
  <verify>Run `pytest tests/test_utils.py`.</verify>
  <done>Utility tests passing.</done>
</task>

<task type="auto">
  <name>Implement Core Logic Tests</name>
  <files>tests/test_logic.py</files>
  <action>
    - Implement tests for `zip_folder_with_progress` in `tests/test_logic.py`.
    - Test successful ZIP creation of a small dummy directory.
    - Test ZIP cancellation logic using a mock callback.
  </action>
  <verify>Run `pytest tests/test_logic.py`.</verify>
  <done>Logic tests passing.</done>
</task>

## Success Criteria
- [ ] Tests for all utility functions.
- [ ] Tests for ZIP logic including cancellation.
