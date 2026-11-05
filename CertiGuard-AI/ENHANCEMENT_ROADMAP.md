# CertiGuard AI — enhancement roadmap

The best next step is to turn the current rules-and-statistics teaching prototype into a **careful verification workflow**. Do not jump straight to a model that labels people or certificates as fraudulent. Build trusted issuer verification and human review first.

## Phase 1 — Make the verification rules trustworthy

**Goal:** establish a source of truth and reduce incorrect alerts.

- Replace the in-memory synthetic institution list with an issuer-controlled database or an authenticated issuer API.
- Define a stable certificate schema: issuer ID, certificate ID, holder name, qualification code, issue date, expiry date, credential status, and version/revocation information.
- Add issuer aliases and controlled qualification mappings so spelling variants can be handled without silently accepting altered credentials.
- Separate outcomes into `VERIFIED`, `MANUAL REVIEW`, `UNVERIFIED`, `REVOKED`, `EXPIRED`, and `ACCESS DENIED`. Reserve `SUSPICIOUS` for a review signal, not a verdict.
- Add reason codes and a complete audit record for every check.
- Add unit tests using records from more than one issuer and boundary dates.

**Acceptance tests:** a genuine certificate should be verified only when a trusted issuer confirms the record; missing data or unavailable services must never become a verified outcome.

## Phase 2 — Add safe PDF/image intake and OCR

**Goal:** read certificate fields from documents while keeping a human in control.

1. Add a backend upload endpoint with strict file size, MIME type, and extension checks.
2. Store uploads in private temporary storage, not in the public repository or a public web directory.
3. Extract text from digital PDFs first. Use OCR only for scanned images/PDF pages.
4. Extract candidate fields such as certificate number, person name, institution, course, issue date, and expiry date.
5. Display the extracted values to an authorized reviewer for confirmation before running issuer lookup.
6. Keep the original file and extracted text under a documented retention policy; delete temporary copies when the workflow ends.

OCR is imperfect. Treat extracted text as untrusted input. Do not use OCR confidence by itself as evidence that a certificate is genuine or fake.

## Phase 3 — Use cryptography correctly

**Goal:** establish file integrity and issuer provenance.

- Calculate SHA-256 from the actual uploaded file bytes on the server; never trust a hash string typed by the person submitting the certificate.
- Compare that digest only against a value supplied through a trusted issuer channel.
- Prefer issuer digital signatures or signed QR payloads that can be validated with issuer public keys. A hash alone only detects changes relative to a trusted reference; it does not prove who created the file.
- Support key rotation, certificate revocation, expiry, and issuer-key lifecycle records.
- Record the exact document version that was checked.

## Phase 4 — Build a usable application

**Suggested beginner-friendly stack:**

| Layer | Suggested technology | Purpose |
|---|---|---|
| Front end | Streamlit for a prototype; React for a later full app | Upload screen, extracted fields, verification result, reviewer queue |
| API | FastAPI | Authenticated verification endpoints and validation |
| Database | PostgreSQL | Issuer records, users, audit events, review decisions |
| Data layer | SQLAlchemy + Alembic | Database models and controlled migrations |
| File storage | Private object storage | Temporary encrypted certificate files |
| Tests | pytest | Rule, API, and integration tests |
| Deployment | Docker | Repeatable application packaging |

Keep the verification logic in `src/certiguard/` independent of the UI. The UI should call the backend; it should not implement its own verification decisions.

## Phase 5 — Add human review and explainability

- Create a reviewer queue for incomplete, ambiguous, expired, revoked, or conflicting records.
- Show which fields matched, which did not, the issuer response, and the rule trace.
- Require an authorized reviewer to record a reason before closing a case.
- Allow an applicant or institution to request correction of inaccurate source data.
- Log reviewer actions and changes without exposing unnecessary personal data.
- Measure false positives and false negatives separately; do not rely on accuracy alone.

## Phase 6 — Add machine learning only when you have suitable data

Machine learning can help prioritize cases, but it should not replace issuer confirmation.

Potential features, after appropriate lawful data governance:

- unusual field combinations;
- unexpected certificate-number patterns;
- duplicate document or credential identifiers;
- image-layout anomalies relative to a known issuer template;
- OCR extraction uncertainty;
- changes in issuer-specific document formats.

Requirements before training:

1. Collect a sufficiently large, correctly labeled dataset from authorized sources.
2. Remove unnecessary personal information and document the lawful purpose and retention rules.
3. Split data by issuer/time/source to avoid leakage between training and testing.
4. Report precision, recall, false-positive rate, false-negative rate, and calibration. Accuracy alone can conceal poor fraud-case recall or excessive false alerts.
5. Check performance across institutions, document types, languages, and scan qualities.
6. Use model output as a review-priority score, not an automatic rejection.
7. Monitor drift and retrain only with reviewed, versioned labels.

## Phase 7 — Security, privacy, and production operations

- Implement server-side authentication, role-based access control, and multi-factor authentication for privileged reviewers.
- Encrypt data in transit and at rest; keep keys in a managed secret store.
- Use least-privilege database credentials and parameterized queries.
- Keep personal data out of application logs and analytics unless essential.
- Define retention, deletion, access-request, and incident-response processes.
- Add rate limits, upload malware scanning, backups, monitoring, and security patching.
- Run dependency and secret scanning in CI; review GitHub Actions permissions.
- Conduct security and privacy review before using real student records.

## Recommended order for a student project

1. Finish the issuer-record schema and improve rule-based checks.
2. Build a small Streamlit interface that accepts manually entered sample fields and shows the explainable rule trace.
3. Add PDF text extraction and human confirmation.
4. Add real SHA-256 file hashing and an issuer-signed QR/digital-signature demonstration.
5. Add FastAPI + database + authentication.
6. Only then evaluate whether an ML triage model is useful.

This order creates a demonstrable project without claiming that synthetic rules or placeholder hashes authenticate real certificates.
