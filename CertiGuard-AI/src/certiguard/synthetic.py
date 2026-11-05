"""Create reproducible synthetic certificate records and evaluation outputs."""
from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .agent import CertificateVerificationAgent, normalize_text

# A fixed date makes the generated teaching dataset reproducible across machines.
REFERENCE_DATE = date(2026, 11, 5)
DEFAULT_SEED = 42

FIRST_NAMES = [
    "Aarav", "Priya", "Rahul", "Neha", "Rohan", "Ananya", "Vikram", "Sneha",
    "Karan", "Meera", "Arjun", "Divya", "Ishaan", "Pooja", "Siddharth", "Kavya",
    "Manish", "Riya", "Nikhil", "Tanvi", "Amit", "Sana", "Varun", "Isha",
]
LAST_NAMES = [
    "Sharma", "Verma", "Mehta", "Singh", "Gupta", "Rao", "Nair", "Patel",
    "Joshi", "Kumar", "Reddy", "Iyer", "Bansal", "Chauhan", "Malhotra", "Bisht",
]
INSTITUTIONS = {
    "ABC University": "University",
    "XYZ Institute": "Institute",
    "National Skill Academy": "Training Centre",
    "Himalayan Technical University": "University",
    "Skill India Training Hub": "Training Centre",
    "Doon Institute of Technology": "Institute",
}
QUALIFICATIONS = {
    "University": [
        ("B.Tech Computer Science", "Degree", 4),
        ("MBA Finance", "Degree", 3),
        ("B.Sc Data Science", "Degree", 3),
        ("M.Tech AI", "Degree", 2),
    ],
    "Institute": [
        ("Data Analytics Certification", "Professional Certificate", 2),
        ("Cloud Computing Diploma", "Diploma", 2),
        ("Cyber Security Certification", "Professional Certificate", 3),
    ],
    "Training Centre": [
        ("Advanced Welding Skill Certificate", "Skill Certificate", 2),
        ("Electrician Skill Certificate", "Skill Certificate", 3),
        ("CNC Operator Certificate", "Skill Certificate", 2),
    ],
}
SCENARIO_COUNTS = {
    "genuine_valid": 150,
    "genuine_expired": 30,
    "id_not_found": 30,
    "name_altered": 30,
    "institution_altered": 20,
    "qualification_altered": 20,
    "hash_mismatch": 24,
    "duplicate_id": 20,
    "database_unavailable": 24,
    "missing_field": 12,
    "invalid_date": 12,
    "unauthorized_user": 8,
    "name_initials_variant": 20,
}
EXPECTED_ACTIONS = {
    "genuine_valid": "VERIFIED",
    "genuine_expired": "MANUAL REVIEW",
    "id_not_found": "SUSPICIOUS",
    "name_altered": "SUSPICIOUS",
    "institution_altered": "SUSPICIOUS",
    "qualification_altered": "SUSPICIOUS",
    "hash_mismatch": "SUSPICIOUS",
    "duplicate_id": "SUSPICIOUS",
    "database_unavailable": "MANUAL REVIEW",
    "missing_field": "MANUAL REVIEW",
    "invalid_date": "SUSPICIOUS",
    "unauthorized_user": "ACCESS DENIED",
    "name_initials_variant": "MANUAL REVIEW",
}
GROUND_TRUTH = {
    "genuine_valid": "Genuine",
    "genuine_expired": "Genuine (expired)",
    "name_initials_variant": "Genuine",
    "database_unavailable": "Genuine",
    "missing_field": "Incomplete",
    "unauthorized_user": "Genuine",
}


def _add_years(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year + years)
    except ValueError:  # e.g. 29 February in a non-leap year
        return value.replace(year=value.year + years, day=28)


def _make_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def _random_date(rng: random.Random, start_year: int, end_year: int, ref_date: date) -> date:
    start = date(start_year, 1, 1)
    end = min(date(end_year, 12, 31), ref_date)
    return start + timedelta(days=rng.randint(0, (end - start).days))


def build_institution_database(
    seed: int = DEFAULT_SEED,
    reference_date: date = REFERENCE_DATE,
    record_count: int = 900,
) -> list[dict[str, Any]]:
    """Build synthetic issuer records. These are not real university records."""
    rng = random.Random(seed)
    records: list[dict[str, Any]] = []
    for index in range(record_count):
        institution = rng.choice(list(INSTITUTIONS))
        institution_type = INSTITUTIONS[institution]
        qualification, level, validity_years = rng.choice(QUALIFICATIONS[institution_type])
        issue_date = _random_date(rng, 2022, reference_date.year, reference_date)
        expiry_date = _add_years(issue_date, validity_years)
        records.append(
            {
                "certificate_id": f"CERT{2001 + index}",
                "name": _make_name(rng),
                "institution": institution,
                "qualification": qualification,
                "issue_date": issue_date.isoformat(),
                "expiry_date": expiry_date.isoformat(),
                "status": "expired" if expiry_date < reference_date else "active",
                # Synthetic placeholder only; not a SHA-256 digest of a PDF.
                "document_hash": f"HASH_{2001 + index}",
                "_level": level,
                "_type": institution_type,
                "_validity": validity_years,
            }
        )
    return records


def generate_dataset(
    seed: int = DEFAULT_SEED,
    reference_date: date = REFERENCE_DATE,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    """Generate certificate scenarios, run the agent, and return data + metrics."""
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    database = build_institution_database(seed=seed, reference_date=reference_date)

    active = [record for record in database if record["status"] == "active"]
    expired = [record for record in database if record["status"] == "expired"]
    rng.shuffle(active)
    rng.shuffle(expired)

    extra_duplicate_records: list[dict[str, Any]] = []
    scenarios: list[tuple[str, dict[str, Any], dict[str, bool], str, str, int]] = []
    new_id = 0

    def take(pool: list[dict[str, Any]]) -> dict[str, Any]:
        if not pool:
            raise RuntimeError("Synthetic record pool exhausted; increase record_count.")
        return dict(pool.pop())

    for scenario, count in SCENARIO_COUNTS.items():
        for _ in range(count):
            base = take(expired if scenario == "genuine_expired" else active)
            certificate = {
                field: base[field]
                for field in (
                    "certificate_id", "name", "institution", "qualification",
                    "issue_date", "expiry_date", "document_hash",
                )
            }
            level, institution_type, validity_years = (
                base["_level"], base["_type"], base["_validity"]
            )
            environment = {"authorized_user": True, "database_available": True}

            if scenario == "id_not_found":
                new_id += 1
                certificate["certificate_id"] = f"CERT{8000 + new_id}"
                certificate["document_hash"] = f"HASH_X{8000 + new_id}"
            elif scenario == "name_altered":
                altered = _make_name(rng)
                while altered == base["name"]:
                    altered = _make_name(rng)
                certificate["name"] = altered
            elif scenario == "institution_altered":
                certificate["institution"] = rng.choice(
                    [name for name in INSTITUTIONS if name != base["institution"]]
                )
            elif scenario == "qualification_altered":
                all_qualifications = [
                    item[0] for group in QUALIFICATIONS.values() for item in group
                    if item[0] != base["qualification"]
                ]
                certificate["qualification"] = rng.choice(all_qualifications)
            elif scenario == "hash_mismatch":
                certificate["document_hash"] = f"HASH_F{rng.randint(1000, 9999)}"
            elif scenario == "duplicate_id":
                duplicate = dict(base)
                duplicate["name"] = _make_name(rng)
                duplicate["document_hash"] = str(base["document_hash"]) + "_B"
                extra_duplicate_records.append(duplicate)
            elif scenario == "database_unavailable":
                environment["database_available"] = False
            elif scenario == "missing_field":
                certificate[rng.choice(["name", "institution", "qualification", "document_hash"])] = ""
            elif scenario == "invalid_date":
                certificate[rng.choice(["issue_date", "expiry_date"])] = rng.choice(
                    ["2024-13-45", "15/06/2024", "not-a-date"]
                )
            elif scenario == "unauthorized_user":
                environment["authorized_user"] = False
            elif scenario == "name_initials_variant":
                first, last = str(base["name"]).split(maxsplit=1)
                certificate["name"] = f"{first[0]}. {last}"

            scenarios.append((scenario, certificate, environment, level, institution_type, validity_years))

    # The source database is copied into the agent without synthetic helper fields.
    clean_database = [
        {key: value for key, value in record.items() if not key.startswith("_")}
        for record in database + extra_duplicate_records
    ]
    agent = CertificateVerificationAgent(clean_database, today=reference_date)
    rng.shuffle(scenarios)

    data_rows: list[dict[str, Any]] = []
    result_rows: list[dict[str, Any]] = []
    for index, (scenario, certificate, environment, level, institution_type, validity_years) in enumerate(scenarios, start=1):
        result = agent.evaluate(certificate, environment)
        matching_records = (
            agent.find_records(certificate.get("certificate_id"))
            if environment["database_available"] and environment["authorized_user"]
            else []
        )
        first_record = matching_records[0] if matching_records else None

        def match_field(submitted_field: str, official_field: str) -> float:
            if first_record is None:
                return np.nan
            return float(
                normalize_text(certificate.get(submitted_field))
                == normalize_text(first_record.get(official_field))
            )

        try:
            issued = date.fromisoformat(certificate["issue_date"])
            expires = date.fromisoformat(certificate["expiry_date"])
            validity = round((expires - issued).days / 365.25, 1)
            days_to_expiry = (expires - reference_date).days
        except (TypeError, ValueError):
            validity = np.nan
            days_to_expiry = np.nan

        record_id = f"R{index:03d}"
        row = {
            "record_id": record_id,
            "certificate_id": certificate["certificate_id"],
            "holder_name": certificate["name"] or np.nan,
            "institution": certificate["institution"] or np.nan,
            "institution_type": institution_type,
            "qualification": certificate["qualification"] or np.nan,
            "qualification_level": level,
            "issue_date": certificate["issue_date"],
            "expiry_date": certificate["expiry_date"],
            "validity_years": validity,
            "days_to_expiry": days_to_expiry,
            "document_hash": certificate["document_hash"] or np.nan,
            "authorized_user": int(environment["authorized_user"]),
            "database_available": int(environment["database_available"]),
            "db_record_count": len(matching_records) if (environment["database_available"] and environment["authorized_user"]) else np.nan,
            "name_match": match_field("name", "name"),
            "institution_match": match_field("institution", "institution"),
            "qualification_match": match_field("qualification", "qualification"),
            "hash_match": (
                np.nan if first_record is None
                else int(certificate["document_hash"] == first_record["document_hash"])
            ),
            "missing_fields": sum(
                1 for field in (
                    "certificate_id", "name", "institution", "qualification",
                    "issue_date", "expiry_date", "document_hash",
                ) if not certificate[field]
            ),
            "scenario": scenario,
            "ground_truth": GROUND_TRUTH.get(scenario, "Forged / altered"),
            "expected_action": EXPECTED_ACTIONS[scenario],
        }
        data_rows.append(row)
        result_rows.append(
            {
                "record_id": record_id,
                "agent_action": result["action"],
                "correct": int(result["action"] == EXPECTED_ACTIONS[scenario]),
                "agent_status": result["status"],
                "agent_reason": result["reason"],
            }
        )

    dataset = pd.DataFrame(data_rows)
    agent_results = pd.DataFrame(result_rows)
    full = dataset.merge(agent_results, on="record_id", validate="one_to_one")

    confusion = pd.crosstab(full["expected_action"], full["agent_action"])
    by_scenario = full.groupby("scenario", sort=True).agg(
        count=("correct", "size"),
        expected_action=("expected_action", "first"),
        accuracy=("correct", "mean"),
        actual_actions=("agent_action", lambda values: ", ".join(
            f"{key}: {value}" for key, value in values.value_counts().items()
        )),
    )
    stats: dict[str, Any] = {
        "reference_date": reference_date.isoformat(),
        "seed": seed,
        "shape": [int(dataset.shape[0]), int(dataset.shape[1])],
        "target_counts": {str(k): int(v) for k, v in dataset["expected_action"].value_counts().items()},
        "scenario_counts": {str(k): int(v) for k, v in dataset["scenario"].value_counts().items()},
        "overall_accuracy": float(full["correct"].mean()),
        "correct_predictions": int(full["correct"].sum()),
        "total_predictions": int(len(full)),
        "by_scenario": [
            {
                "scenario": str(name),
                "count": int(row["count"]),
                "expected_action": str(row["expected_action"]),
                "accuracy": float(row["accuracy"]),
                "actual_actions": str(row["actual_actions"]),
            }
            for name, row in by_scenario.iterrows()
        ],
        "confusion_matrix": {
            "index": [str(item) for item in confusion.index],
            "columns": [str(item) for item in confusion.columns],
            "values": [[int(value) for value in row] for row in confusion.to_numpy()],
        },
        "false_accepts_on_synthetic_forged_cases": int(
            ((full["ground_truth"] == "Forged / altered") & (full["agent_action"] == "VERIFIED")).sum()
        ),
        "genuine_cases_flagged_suspicious": int(
            ((full["ground_truth"] == "Genuine") & (full["agent_action"] == "SUSPICIOUS")).sum()
        ),
        "duplicate_certificate_ids_in_submissions": int(dataset["certificate_id"].duplicated().sum()),
    }
    return dataset, full, stats, clean_database


def write_outputs(
    output_dir: Path,
    seed: int = DEFAULT_SEED,
    reference_date: date = REFERENCE_DATE,
) -> dict[str, Any]:
    """Generate CSV, JSON, and PNG artefacts under ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset, full, stats, clean_database = generate_dataset(seed=seed, reference_date=reference_date)
    dataset.to_csv(output_dir / "certificate_dataset.csv", index=False)
    full.to_csv(output_dir / "certificate_dataset_agent_results.csv", index=False)
    pd.DataFrame(clean_database).to_csv(output_dir / "institutional_records_demo.csv", index=False)
    (output_dir / "stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    counts = dataset["expected_action"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(counts.index, counts.values)
    ax.set_title("Synthetic dataset: expected verification action")
    ax.set_ylabel("Number of records")
    ax.tick_params(axis="x", rotation=15)
    for bar, value in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 1, str(value), ha="center")
    fig.tight_layout()
    fig.savefig(output_dir / "action_distribution.png", dpi=160)
    plt.close(fig)

    accuracy = full.groupby("scenario")["correct"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(accuracy.index, accuracy.values * 100)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Scenario accuracy (%)")
    ax.set_title("Rule-agent accuracy by synthetic test scenario")
    fig.tight_layout()
    fig.savefig(output_dir / "scenario_accuracy.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    values = dataset["days_to_expiry"].dropna()
    ax.hist(values, bins=30, edgecolor="white")
    ax.axvline(values.median(), linestyle="--", label=f"Median: {values.median():.0f} days")
    ax.set_xlabel("Days until expiry (negative = expired)")
    ax.set_ylabel("Certificates")
    ax.set_title("Synthetic certificate expiry distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "expiry_distribution.png", dpi=160)
    plt.close(fig)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CertiGuard's synthetic evaluation dataset.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data" / "generated",
        help="Directory for CSV, JSON and chart outputs (default: project data/generated).",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    stats = write_outputs(args.output_dir, seed=args.seed)
    print(f"Generated {stats['total_predictions']} synthetic cases in: {args.output_dir.resolve()}")
    print(f"Rule-agent benchmark accuracy: {stats['overall_accuracy']:.1%}")
    print("Reminder: this measures agreement with synthetic expected labels, not real-world fraud detection accuracy.")


if __name__ == "__main__":
    main()
