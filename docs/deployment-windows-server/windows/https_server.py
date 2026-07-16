from __future__ import annotations

import ipaddress
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cheroot.ssl.builtin import BuiltinSSLAdapter
from cheroot.wsgi import Server
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


PROJECT_DIR = Path(__file__).resolve().parents[2]
os.chdir(PROJECT_DIR)
sys.path.insert(0, str(PROJECT_DIR))

from wsgi import app  # noqa: E402


def ensure_certificate(cert_path: Path, key_path: Path, server_name: str) -> None:
    if cert_path.exists() and key_path.exists():
        return

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, server_name)]
    )
    now = datetime.now(timezone.utc)

    san_name: x509.GeneralName
    try:
        san_name = x509.IPAddress(ipaddress.ip_address(server_name))
    except ValueError:
        san_name = x509.DNSName(server_name)

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName([san_name]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8782"))
    server_name = os.getenv("SERVER_NAME", "8.161.230.61")
    cert_path = Path(
        os.getenv("TLS_CERT_FILE", PROJECT_DIR / "certs" / "server.crt")
    )
    key_path = Path(
        os.getenv("TLS_KEY_FILE", PROJECT_DIR / "certs" / "server.key")
    )

    ensure_certificate(cert_path, key_path, server_name)

    server = Server(
        (host, port),
        app,
        numthreads=int(os.getenv("SERVER_THREADS", "8")),
        server_name=server_name,
        timeout=int(os.getenv("REQUEST_TIMEOUT", "180")),
    )
    server.ssl_adapter = BuiltinSSLAdapter(str(cert_path), str(key_path))
    server.start()


if __name__ == "__main__":
    main()
