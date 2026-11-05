"""Rule-based certificate verification engine.

This module deliberately treats uncertain matches as review cases. It does not
make a legal or definitive finding that a person has committed fraud.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping


REQUIRED_FIELDS = (
    "certificate_id",
    "name",
    "institution",
    "qualification",
    "issue_date",
    "expiry_date",
    "document_hash",
)


def normalize_text(value: Any) -> str:
    """Normalize whitespace and case for conservative exact text comparison."""
    if value is None:
        return ""
    return " ".join(str(value).strip().casefold().split())


def parse_iso_date(value: Any) -> date | None:
    """Parse a strict YYYY-MM-DD date; return None when invalid."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def is_initials_variant(submitted_name: str, official_name: str) -> bool:
    """Detect a narrow first-name-initial variant and route it to manual review.

    Example: ``A. Sharma`` vs ``Aarav Sharma``. This is not accepted as a match;
    it is only used to avoid automatically treating a common abbreviation as
    evidence of document tampering.
    """
    submitted = normalize_text(submitted_name).split()
    official = normalize_text(official_name).split()
    if len(submitted) != len(official) or len(submitted) < 2:
        return False

    submitted_first = submitted[0].rstrip(".")
    official_first = official[0]
    same_remaining_names = submitted[1:] == official[1:]
    return (
        same_remaining_names
        and len(submitted_first) == 1
        and submitted_first == official_first[:1]
    )


class CertificateVerificationAgent:
    """Evaluate submitted certificate metadata against institutional records.

    Parameters
    ----------
    records:
        Iterable of trusted institutional metadata records. In this ZIP project,
        these are synthetic in-memory records, not a real issuer connection.
    today:
        Optional evaluation date. Supply a fixed date for reproducible tests;
        otherwise the system's current local date is used.
    """

    def __init__(
        self,
        records: Iterable[Mapping[str, Any]],
        today: date | None = None,
    ) -> None:
        self.records = [dict(record) for record in records]
        self.today = today or date.today()
        self.name = "CertiGuard Rule-Based Verification Agent"

    def find_records(self, certificate_id: Any) -> list[dict[str, Any]]:
        """Return every institutional record matching an ID, case-insensitively."""
        wanted = normalize_text(certificate_id).upper()
        if not wanted:
            return []
        return [
            record
            for record in self.records
            if normalize_text(record.get("certificate_id")).upper() == wanted
        ]

    @staticmethod
    def _result(
        action: str,
        status: str,
        reason: str,
        rules: list[str],
        observations: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "action": action,
            "status": status,
            "reason": reason,
            "rules": rules,
            "observations": observations or [],
        }

    def evaluate(
        self,
        certificate: Mapping[str, Any] | None,
        environment: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a decision, explanation, rule trace, and observations.

        ``SUSPICIOUS`` means a verification check raised a concern and must be
        investigated. It is not a conclusive fraud determination.
        """
        cert = dict(certificate or {})
        env = dict(environment or {})
        rules: list[str] = []
        observations: list[str] = []

        # R1: authorization. Missing authorization is denied by default.
        if env.get("authorized_user", False) is not True:
            rules.append("R1: User is not authorized.")
            return self._result(
                "ACCESS DENIED",
                "SAFE",
                "The requester is not authorized to access verification results.",
                rules,
            )
        rules.append("R1: User authorization verified.")

        # R2: availability. Do not infer authenticity when the source is offline.
        if env.get("database_available", False) is not True:
            rules.append("R2: Institutional database unavailable.")
            observations.append("Cross-verification could not be completed.")
            return self._result(
                "MANUAL REVIEW",
                "UNCERTAIN",
                "Institutional records are unavailable; authenticity cannot be established.",
                rules,
                observations,
            )
        rules.append("R2: Institutional database available.")

        # R3: required values.
        missing = [field for field in REQUIRED_FIELDS if not cert.get(field)]
        if missing:
            rules.append("R3: Required certificate fields are missing.")
            observations.append("Missing fields: " + ", ".join(missing))
            return self._result(
                "MANUAL REVIEW",
                "UNCERTAIN",
                "The submitted metadata is incomplete.",
                rules,
                observations,
            )
        rules.append("R3: Required certificate fields are present.")

        # R4: date validation and chronology.
        issue_date = parse_iso_date(cert.get("issue_date"))
        expiry_date = parse_iso_date(cert.get("expiry_date"))
        if issue_date is None or expiry_date is None:
            rules.append("R4: Invalid certificate date format.")
            observations.append("Dates must use the YYYY-MM-DD format.")
            return self._result(
                "SUSPICIOUS",
                "ALERT",
                "One or more certificate dates could not be parsed.",
                rules,
                observations,
            )
        if issue_date > expiry_date or issue_date > self.today:
            rules.append("R4: Certificate date chronology is invalid.")
            observations.append("Issue date must not be after expiry date or the evaluation date.")
            return self._result(
                "SUSPICIOUS",
                "ALERT",
                "Certificate date chronology is inconsistent.",
                rules,
                observations,
            )
        rules.append("R4: Certificate dates are valid and chronologically consistent.")

        # R5: lookup by certificate identifier.
        matches = self.find_records(cert.get("certificate_id"))
        if not matches:
            rules.append("R5: Certificate ID not found in institutional records.")
            observations.append("No matching institutional record was returned.")
            return self._result(
                "SUSPICIOUS",
                "ALERT",
                "The certificate could not be verified against the available issuer records.",
                rules,
                observations,
            )
        rules.append(f"R5: {len(matches)} institutional record(s) found.")

        # R6: duplicate identifier means conflicting source data, not an automatic fraud verdict.
        if len(matches) > 1:
            rules.append("R6: Duplicate certificate ID found.")
            observations.append("Multiple institutional records use the same certificate ID.")
            return self._result(
                "SUSPICIOUS",
                "ALERT",
                "The issuer data contains a duplicate identifier and needs investigation.",
                rules,
                observations,
            )
        rules.append("R6: Certificate ID is unique in the institutional records.")
        official = matches[0]

        # R7: holder identity. An initials-only difference is reviewed, never auto-approved.
        submitted_name = normalize_text(cert.get("name"))
        official_name = normalize_text(official.get("name"))
        if submitted_name != official_name:
            if is_initials_variant(str(cert.get("name", "")), str(official.get("name", ""))):
                rules.append("R7: Name uses an initials variant; exact identity match is not established.")
                observations.append("Submitted and official holder names differ only by a first-name initial.")
                return self._result(
                    "MANUAL REVIEW",
                    "UNCERTAIN",
                    "A name abbreviation may be legitimate, but a human must confirm identity.",
                    rules,
                    observations,
                )
            rules.append("R7: Holder name mismatch detected.")
            observations.extend([
                f"Submitted name: {cert.get('name')}",
                f"Institutional name: {official.get('name')}",
            ])
            return self._result(
                "SUSPICIOUS",
                "ALERT",
                "The holder name differs from the institutional record.",
                rules,
                observations,
            )
        rules.append("R7: Holder name matches institutional record.")

        # R8-R10: verify issuer, award and both dates against the source of truth.
        comparisons = (
            ("institution", "R8", "Issuing institution mismatch detected.", "Institution"),
            ("qualification", "R9", "Qualification mismatch detected.", "Qualification"),
            ("issue_date", "R10", "Issue date mismatch detected.", "Issue date"),
            ("expiry_date", "R11", "Expiry date mismatch detected.", "Expiry date"),
        )
        for field, rule_id, reason, label in comparisons:
            left = normalize_text(cert.get(field))
            right = normalize_text(official.get(field))
            if left != right:
                rules.append(f"{rule_id}: {reason}")
                observations.append(f"{label} does not match the issuer record.")
                return self._result(
                    "SUSPICIOUS",
                    "ALERT",
                    f"{label} information differs from institutional records.",
                    rules,
                    observations,
                )
            rules.append(f"{rule_id}: {label} matches institutional record.")

        # R12: compare the stored document digest token. For production, this must
        # be calculated from uploaded file bytes and anchored by a trusted issuer.
        if str(cert.get("document_hash")).strip() != str(official.get("document_hash", "")).strip():
            rules.append("R12: Document digest mismatch detected.")
            observations.append("Submitted digest differs from institutional metadata.")
            return self._result(
                "SUSPICIOUS",
                "ALERT",
                "Document integrity metadata does not match the issuer record.",
                rules,
                observations,
            )
        rules.append("R12: Document digest metadata matches institutional record.")

        # R13: honor issuer-side revocation/suspension state where provided.
        issuer_status = normalize_text(official.get("status"))
        if issuer_status in {"revoked", "suspended", "cancelled", "canceled", "invalid"}:
            rules.append(f"R13: Issuer reports credential status '{issuer_status}'.")
            observations.append("The issuer record is not in an active state.")
            return self._result(
                "MANUAL REVIEW",
                "ALERT",
                "The issuer reports a revoked, suspended, or invalid credential status.",
                rules,
                observations,
            )
        if issuer_status not in {"active", "valid", "current", "expired"}:
            rules.append(f"R13: Unrecognized issuer status '{issuer_status}'.")
            observations.append("The credential status needs confirmation from the issuer.")
            return self._result(
                "MANUAL REVIEW",
                "UNCERTAIN",
                "The issuer returned a status this prototype does not recognize.",
                rules,
                observations,
            )
        rules.append(f"R13: Issuer status '{issuer_status}' checked.")

        # R14: expiry is a validity status, not proof that the award was fabricated.
        official_expiry = parse_iso_date(official.get("expiry_date"))
        if official_expiry is None or official_expiry < self.today or issuer_status == "expired":
            rules.append("R14: Certificate validity period has ended.")
            observations.append("Certificate details match, but the validity period has ended.")
            return self._result(
                "MANUAL REVIEW",
                "UNCERTAIN",
                "The certificate metadata matches the issuer record but is expired.",
                rules,
                observations,
            )
        rules.append("R14: Certificate is within its validity period.")
        rules.append("R15: All automated verification checks passed.")
        return self._result(
            "VERIFIED",
            "NORMAL",
            "Certificate metadata matches the available institutional record.",
            rules,
            observations,
        )
