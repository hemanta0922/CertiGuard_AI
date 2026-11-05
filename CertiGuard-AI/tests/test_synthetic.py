from certiguard.synthetic import SCENARIO_COUNTS, generate_dataset


def test_synthetic_dataset_has_expected_size_and_scenarios():
    dataset, results, stats, issuer_records = generate_dataset()
    assert len(dataset) == sum(SCENARIO_COUNTS.values()) == 400
    assert len(results) == len(dataset)
    assert len(issuer_records) >= 900
    assert dataset["scenario"].value_counts().to_dict() == SCENARIO_COUNTS
    assert stats["total_predictions"] == 400


def test_all_documented_synthetic_scenarios_match_expected_action():
    _dataset, results, stats, _issuer_records = generate_dataset()
    assert results["correct"].all()
    assert stats["overall_accuracy"] == 1.0
    assert stats["genuine_cases_flagged_suspicious"] == 0
    assert stats["false_accepts_on_synthetic_forged_cases"] == 0
