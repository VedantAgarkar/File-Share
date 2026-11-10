import unittest
import socket
from src.utils.network import find_free_port
from src.utils.crypto import generate_self_signed_cert, create_ssl_context
from src.core.server import _limiter, MAX_FAILED_ATTEMPTS

class TestIndustryStandards(unittest.TestCase):
    def test_find_free_port(self):
        port = find_free_port(9000)
        self.assertGreaterEqual(port, 9000)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            self.assertEqual(s.getsockname()[1], port)

    def test_tls_cert_generation(self):
        cert, key = generate_self_signed_cert("127.0.0.1", "localhost")
        self.assertIsNotNone(cert)
        self.assertIsNotNone(key)
        ctx = create_ssl_context(cert, key)
        self.assertIsNotNone(ctx)

    def test_rate_limiter_bruteforce_protection(self):
        test_ip = "192.168.1.99"
        _limiter.reset(test_ip)
        self.assertFalse(_limiter.is_locked(test_ip))

        for _ in range(MAX_FAILED_ATTEMPTS):
            _limiter.record_failure(test_ip)

        self.assertTrue(_limiter.is_locked(test_ip))
        _limiter.reset(test_ip)
        self.assertFalse(_limiter.is_locked(test_ip))

if __name__ == "__main__":
    unittest.main()
