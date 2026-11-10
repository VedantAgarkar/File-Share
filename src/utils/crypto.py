# src/utils/crypto.py
import datetime
import ipaddress
import tempfile
import os
import ssl

def generate_self_signed_cert(ip_address="127.0.0.1", hostname="localhost"):
    """
    Generates a secure self-signed X.509 certificate and private key in temporary files.
    Returns (cert_path, key_path).
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LocalDrop Secure"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname or "LocalDrop"),
        ])

        san_list = [x509.DNSName("localhost")]
        if hostname and hostname != "localhost":
            san_list.append(x509.DNSName(hostname))

        if ip_address:
            try:
                san_list.append(x509.IPAddress(ipaddress.ip_address(ip_address)))
            except ValueError:
                pass

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName(san_list), critical=False)
            .sign(key, hashes.SHA256())
        )

        cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".crt")
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
        cert_file.close()

        key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
        key_file.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        key_file.close()

        return cert_file.name, key_file.name
    except Exception as e:
        print(f"Warning: Failed to generate TLS cert ({e}). Falling back to HTTP.")
        return None, None

def create_ssl_context(cert_path, key_path):
    """Creates a TLS context configured with modern ciphers."""
    if not cert_path or not key_path or not os.path.exists(cert_path) or not os.path.exists(key_path):
        return None
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        # Enforce modern TLS versions
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context
    except Exception as e:
        print(f"Failed to create SSL context: {e}")
        return None
