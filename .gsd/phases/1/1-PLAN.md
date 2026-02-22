---
phase: 1
plan: 1
wave: 1
---

# Plan 1.1: Enable Multi-File Selection

## Objective
Update the client-side upload interface to support selecting and uploading multiple files in a single batch.

## Context
- .gsd/SPEC.md
- .gsd/ARCHITECTURE.md
- app.py

## Tasks

<task type="auto">
  <name>Update HTML and JS for multiple file support</name>
  <files>app.py</files>
  <action>
    - Add the `multiple` attribute to the `fileInput` HTML element in the `show_upload_options` method.
    - Verify that `uploadFiles` JavaScript function correctly appends all selected files to the `FormData` object (it currently seems to do this, but double check).
    - Ensure the UI feedback (label showing file names) handles multiple files gracefully.
  </action>
  <verify>Check the HTML source code in `app.py` for the `multiple` attribute on `fileInput`.</verify>
  <done>`id="fileInput"` has `multiple` attribute and JS iterates through `selectedFiles`.</done>
</task>

<task type="auto">
  <name>Verify and update backend upload processing</name>
  <files>app.py</files>
  <action>
    - Review the `handle_upload` method to ensure it correctly iterates through all parts of the multipart request.
    - Confirm that `saved_files` list captures all processed files and the UI update loop (using `root.after`) correctly displays the multiple received files.
  </action>
  <verify>Review `handle_upload` logic in `app.py`.</verify>
  <done>`handle_upload` processes all files in a single request and updates UI for each.</done>
</task>

## Success Criteria
- [ ] Users can select multiple files in the browser.
- [ ] All selected files are uploaded and saved to the receiving directory.
- [ ] The desktop UI shows receipt of each file.
