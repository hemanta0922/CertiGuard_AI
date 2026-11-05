"""CertiGuard AI: a teaching prototype for certificate verification."""
from .agent import CertificateVerificationAgent, normalize_text, parse_iso_date

__all__ = ["CertificateVerificationAgent", "normalize_text", "parse_iso_date"]
__version__ = "1.0.0"
