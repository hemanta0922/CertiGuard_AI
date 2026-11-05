"""Verify a JSON certificate-metadata record against the generated demo issuer CSV."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from certiguard.agent import CertificateVerificationAgent  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the rule-based CertiGuard agent on certificate metadata JSON."
    )
    parser.add_argument(
        "--certificate",
        type=Path,
        default=ROOT / "examples" / "sample_certificate.json",
        help="JSON file containing certificate metadata.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / "data" / "generated" / "institutional_records_demo.csv",
        help="Synthetic issuer-record CSV produced by the dataset generator.",
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=date.today(),
        help="Evaluation date in YYYY-MM-DD format (default: today's local date).",
    )
    parser.add_argument(
        "--authorized-user",
        action="store_true",
        help="Simulate an authenticated and authorized requester.",
    )
    parser.add_argument(
        "--database-unavailable",
        action="store_true",
        help="Simulate an institutional database outage.",
    )
    args = parser.parse_args()

    if not args.certificate.is_file():
        parser.error(f"Certificate JSON not found: {args.certificate}")
    if not args.database.is_file():
        parser.error(
            f"Issuer CSV not found: {args.database}. Run scripts/generate_certificate_dataset.py first."
        )

    try:
        certificate = json.loads(args.certificate.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        parser.error(f"Invalid certificate JSON: {exc}")
    if not isinstance(certificate, dict):
        parser.error("Certificate JSON must contain one JSON object.")

    records = pd.read_csv(args.database, dtype=str).fillna("").to_dict(orient="records")
    agent = CertificateVerificationAgent(records, today=args.today)
    environment = {
        "authorized_user": args.authorized_user,
        "database_available": not args.database_unavailable,
    }
    result = agent.evaluate(certificate, environment)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
