from datetime import date

import pytest

from certiguard.agent import CertificateVerificationAgent

TODAY = date(2026, 11, 5)
ENV = {"authorized_user": True, "database_available": True}
RECORD = {
    "certificate_id": "CERT-TEST-001",
    "name": "Aarav Sharma",
    "institution": "Example Technical University",
    "qualification": "B.Tech Computer Science",
    "issue_date": "2024-06-15",
    "expiry_date": "2028-06-15",
    "document_hash": "DEMO_DIGEST_001",
    "status": "active",
}


@pytest.fixture
def agent():
    return CertificateVerificationAgent([RECORD], today=TODAY)


def certificate(**updates):
    result = dict(RECORD)
    result.update(updates)
    return result


def test_exact_valid_record_is_verified(agent):
    result = agent.evaluate(certificate(), ENV)
    assert result["action"] == "VERIFIED"
    assert result["status"] == "NORMAL"


def test_missing_authorization_is_denied(agent):
    result = agent.evaluate(certificate(), {"database_available": True})
    assert result["action"] == "ACCESS DENIED"


def test_database_outage_requires_manual_review(agent):
    result = agent.evaluate(certificate(), {"authorized_user": True, "database_available": False})
    assert result["action"] == "MANUAL REVIEW"
    assert result["status"] == "UNCERTAIN"


def test_incomplete_certificate_requires_manual_review(agent):
    result = agent.evaluate(certificate(name=""), ENV)
    assert result["action"] == "MANUAL REVIEW"
    assert "name" in result["observations"][0]


def test_invalid_date_is_flagged(agent):
    result = agent.evaluate(certificate(issue_date="15/06/2024"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_future_issue_date_is_flagged(agent):
    result = agent.evaluate(certificate(issue_date="2027-01-01", expiry_date="2028-06-15"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_expiry_before_issue_is_flagged(agent):
    result = agent.evaluate(certificate(issue_date="2025-01-01", expiry_date="2024-01-01"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_initials_variant_requires_human_review(agent):
    result = agent.evaluate(certificate(name="A. Sharma"), ENV)
    assert result["action"] == "MANUAL REVIEW"
    assert result["status"] == "UNCERTAIN"


def test_material_name_change_is_flagged(agent):
    result = agent.evaluate(certificate(name="Rohan Mehta"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_institution_mismatch_is_flagged(agent):
    result = agent.evaluate(certificate(institution="Unknown College"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_qualification_mismatch_is_flagged(agent):
    result = agent.evaluate(certificate(qualification="MBA Finance"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_issue_date_mismatch_is_flagged(agent):
    result = agent.evaluate(certificate(issue_date="2024-06-16"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_expiry_date_mismatch_is_flagged(agent):
    result = agent.evaluate(certificate(expiry_date="2028-06-16"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_digest_mismatch_is_flagged(agent):
    result = agent.evaluate(certificate(document_hash="OTHER_DIGEST"), ENV)
    assert result["action"] == "SUSPICIOUS"


def test_expired_but_matching_certificate_requires_review():
    expired_record = dict(RECORD, expiry_date="2025-06-15")
    expired_agent = CertificateVerificationAgent([expired_record], today=TODAY)
    result = expired_agent.evaluate(expired_record, ENV)
    assert result["action"] == "MANUAL REVIEW"


def test_unknown_certificate_id_is_not_verified(agent):
    result = agent.evaluate(certificate(certificate_id="CERT-UNKNOWN"), ENV)
    assert result["action"] == "SUSPICIOUS"
    assert result["action"] != "VERIFIED"


def test_duplicate_source_identifier_requires_investigation():
    duplicate = dict(RECORD, name="Different Holder", document_hash="OTHER")
    duplicate_agent = CertificateVerificationAgent([RECORD, duplicate], today=TODAY)
    result = duplicate_agent.evaluate(certificate(), ENV)
    assert result["action"] == "SUSPICIOUS"
    assert "duplicate" in result["reason"].lower()


def test_revoked_issuer_status_is_not_verified():
    revoked_record = dict(RECORD, status="revoked")
    revoked_agent = CertificateVerificationAgent([revoked_record], today=TODAY)
    result = revoked_agent.evaluate(revoked_record, ENV)
    assert result["action"] == "MANUAL REVIEW"
    assert result["status"] == "ALERT"


def test_missing_issuer_status_requires_manual_review():
    record_without_status = {key: value for key, value in RECORD.items() if key != "status"}
    missing_status_agent = CertificateVerificationAgent([record_without_status], today=TODAY)
    result = missing_status_agent.evaluate(record_without_status, ENV)
    assert result["action"] == "MANUAL REVIEW"
