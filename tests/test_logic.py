import os
import shutil
import tempfile
import zipfile
import pytest
from src.core.logic import zip_folder_with_progress

def test_zip_folder_success():
    # Setup dummy directory
    temp_dir = tempfile.mkdtemp()
    test_folder = os.path.join(temp_dir, "test_folder")
    os.makedirs(test_folder)
    
    file_content = "hello world"
    with open(os.path.join(test_folder, "test_file.txt"), "w") as f:
        f.write(file_content)
    
    # Track progress
    progress_updates = []
    def progress_callback(done, percent, speed, remaining, total):
        progress_updates.append((done, percent))
    
    # Run zip
    zip_path, zip_temp_dir = zip_folder_with_progress(
        test_folder, 
        progress_callback, 
        lambda: False
    )
    
    try:
        assert zip_path is not None
        assert os.path.exists(zip_path)
        
        # Verify ZIP content
        with zipfile.ZipFile(zip_path, 'r') as z:
            assert "test_file.txt" in z.namelist()
            assert z.read("test_file.txt").decode() == file_content
            
        assert len(progress_updates) > 0
    finally:
        # Cleanup
        if zip_temp_dir and os.path.exists(zip_temp_dir):
            shutil.rmtree(zip_temp_dir)
        shutil.rmtree(temp_dir)

def test_zip_folder_cancel():
    temp_dir = tempfile.mkdtemp()
    test_folder = os.path.join(temp_dir, "test_folder")
    os.makedirs(test_folder)
    with open(os.path.join(test_folder, "file.txt"), "w") as f:
        f.write("data")
        
    zip_path, zip_temp_dir = zip_folder_with_progress(
        test_folder,
        lambda *args: None,
        lambda: True # Immediate cancel
    )
    
    try:
        assert zip_path is None
        assert zip_temp_dir is None
    finally:
        shutil.rmtree(temp_dir)
