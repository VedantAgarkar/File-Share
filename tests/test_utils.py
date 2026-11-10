import pytest
from unittest.mock import patch, MagicMock
from src.utils.helpers import format_size, format_time
from src.utils.network import get_local_ip

def test_format_size():
    assert format_size(0) == "0 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024 * 1024 * 5.5) == "5.5 MB"
    assert format_size(1024 * 1024 * 1024 * 2) == "2.0 GB"

def test_format_time():
    assert format_time(-1) == "--"
    assert format_time(0) == "0m 0s"
    assert format_time(61) == "1m 1s"
    assert format_time(3600) == "1h 0m"

def test_get_local_ip_success():
    with patch("socket.socket") as mock_socket:
        mock_instance = MagicMock()
        mock_socket.return_value = mock_instance
        mock_instance.getsockname.return_value = ("192.168.1.10", 12345)
        
        assert get_local_ip() == "192.168.1.10"

def test_get_local_ip_failure():
    with patch("socket.socket") as mock_socket:
        mock_socket.side_effect = Exception("error")
        assert get_local_ip() == "127.0.0.1"
