# CertiGuard AI — ZIP audit and fixes

## Scope inspected

The ZIP contained four Python files:

- `generate_certificate_dataset.py`
- `sampling_experiment.py`
- `sampling_distribution_experiment.py`
- `shape_outliers_groups.py`

It did not contain a README, requirements file, tests, CSV input data, institutional database export, PDF/OCR component, application UI, or deployment configuration. All four Python files parsed successfully, but this did not mean all could run from the extracted ZIP layout.

## Findings in the original project

| Severity | Finding | Evidence / impact | Correction in this repository |
|---|---|---|---|
| High | Name-initials scenario was misclassified | Original generated results showed 20 of 20 `name_initials_variant` cases expected `MANUAL REVIEW` but returned `SUSPICIOUS`. The original synthetic benchmark therefore scored 380/400 = 95.0%, with 20 genuine cases flagged suspicious. | Detects a narrow first-name-initial variant and routes it to human review; it never auto-verifies an abbreviation. |
| High | Issued/expiry dates were not compared with issuer dates | The original agent checked date formatting and expiry, but did not compare submitted `issue_date` or `expiry_date` to the institutional record. | Both dates are now compared with the source record, and date chronology is checked. |
| High | Demo digest was presented as a document hash | The original values such as `HASH_A1001` and `HASH_2001` were fixed labels, not digests calculated from uploaded document bytes. | Documentation explicitly labels these as synthetic metadata tokens. A production design must hash file bytes and anchor the digest to an issuer-controlled record. |
| Medium | Experiment 7 path was invalid for the ZIP layout | Running the original script from the extracted project failed with `FileNotFoundError`: it looked for a sibling `Experiment-4/certificate_dataset.csv` directory that was not in the ZIP. | Experiment 7 now reads `data/generated/certificate_dataset.csv` relative to the repository root. |
| Medium | Experiment 5 input file was absent | The original script required `student_data.csv`, but the ZIP did not include it. It could not run as delivered. | Experiment 5 now uses the generated CertiGuard dataset and explicit columns suitable for this data. |
| Medium | Current date was monkey-patched globally | The original generator replaced the imported `datetime` class inside the module so tests would behave as of 1-Oct-2026. This tightly coupled test time to module globals. | The agent accepts an injected `today` date. The synthetic dataset uses a clearly documented fixed reference date for reproducibility. |
| Medium | Sampling edge cases were not guarded | The original Experiment 5 could fail if the sample size exceeded the population, if a selected category column was absent, or if rounding made stratified allocation inconsistent. Percentage error also divided by the population mean without guarding a zero mean. | Adds population/sample validation, exact proportional stratified allocation, column checks, and zero-mean handling. |
| Medium | Input/output directories depended on working directory | The original scripts expected CSVs in different relative locations and wrote results wherever the terminal happened to be. | Scripts resolve inputs and outputs from their repository location. |
| Low | No automated regression tests or setup instructions | The ZIP supplied no package/dependency manifest, tests, or GitHub Actions workflow. | Added `pyproject.toml`, `requirements.txt`, pytest tests, README, and CI workflow. |

## Original execution checks

Checks performed against the supplied scripts:

- Python syntax/AST parsing: all four files passed.
- Original dataset generator: completed successfully and created 400 synthetic cases.
- Original Experiment 6: completed when run after the generator with the generated CSV in its current working directory.
- Original Experiment 7: failed because its hard-coded `Experiment-4` folder did not exist in the ZIP layout.
- Original Experiment 5: could not be run from the ZIP because `student_data.csv` was not supplied.

Original generator benchmark summary:

- Total synthetic cases: 400
- Original action agreement: 380/400 (95.0%)
- Initials-variant false alerts: 20
- Synthetic forged/altered records incorrectly marked VERIFIED: 0

## Changes made in the fixed version

1. Created a reusable `CertificateVerificationAgent` in `src/certiguard/agent.py`.
2. Added explicit checks for issue-date and expiry-date mismatches and invalid date chronology.
3. Routed initials-only name variants to manual review instead of flagging them as suspicious automatically.
4. Added issuer-status handling; revoked, suspended, missing, or unrecognized status values are not marked VERIFIED.
5. Preserved authorization-denied and database-unavailable safe outcomes.
6. Injected an evaluation date instead of monkey-patching date/time globally.
7. Rebuilt dataset generation as a reproducible module and moved generated files into `data/generated/`.
8. Repaired Experiment 5, Experiment 6, and Experiment 7 path and output behaviour.
9. Added a command-line metadata verifier that uses the generated issuer-record CSV.
10. Added tests for positive, negative, uncertain, date, identity, duplicate, issuer-status, and synthetic benchmark cases.
11. Added repository documentation, dependency metadata, `.gitignore`, license, and GitHub Actions CI.

## Validation status

The repaired repository was validated with:

```bash
python -m pip install -e ".[dev]"
pytest
python scripts/generate_certificate_dataset.py
python scripts/sampling_experiment.py
python scripts/sampling_distribution_experiment.py
python scripts/shape_outliers_groups.py
```

Execution results in this environment:

- Python compilation: passed.
- Automated tests: **21 passed**.
- Synthetic generator: passed; 400 test cases created.
- CLI example: returned `VERIFIED` for the synthetic issuer record.
- Experiment 5: passed.
- Experiment 6: passed.
- Experiment 7: passed.
- Synthetic expected-action agreement: **400/400 (100.0%)**.
- Synthetic forged/altered cases incorrectly marked VERIFIED: **0**.
- Synthetic genuine cases flagged SUSPICIOUS: **0**.

The 100% benchmark result is expected for a controlled, rule-generated synthetic dataset whose scenarios were designed around these rules. It is not a real-world estimate and should not be used as a claim of production fraud-detection accuracy.
