from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dataguard.engine import ConfigError, run_from_config
from dataguard.models import Issue
from dataguard.rules import referential_integrity, regex
from fixtures import make_project


def test_baseline_counts_and_status(tmp_path: Path):
    summary, checks, _ = run_from_config(make_project(tmp_path))
    assert summary.total_checks == 28
    assert summary.passed_checks == 8
    assert summary.failed_checks == 20
    assert summary.issue_count == 35
    assert (summary.high_count, summary.medium_count, summary.low_count) == (31, 4, 0)
    assert summary.status == "failed"


def test_missing_column_does_not_abort_run(tmp_path: Path):
    config_path = make_project(tmp_path)
    data = tmp_path / "data" / "raw" / "customers.csv"
    frame = pd.read_csv(data, dtype=str, keep_default_na=False)
    frame.drop(columns=["email"]).to_csv(data, index=False, encoding="utf-8-sig")

    summary, checks, _ = run_from_config(config_path)
    assert summary.total_checks == 28
    email_check = next(check for check in checks if check.check_id == "customers_email_format")
    assert email_check.passed is False
    assert email_check.error
    assert summary.status == "failed"


def test_invalid_severity_rejected(tmp_path: Path):
    config_path = make_project(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["checks"][0]["severity"] = "critical"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ConfigError):
        run_from_config(config_path)


def test_fail_on_high_false_becomes_warning(tmp_path: Path):
    config_path = make_project(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["thresholds"]["fail_on_high"] = False
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    summary, _, _ = run_from_config(config_path)
    assert summary.high_count > 0
    assert summary.status == "warning"


def test_unique_metric_matches_issue_rows(tmp_path: Path):
    _, checks, _ = run_from_config(make_project(tmp_path))
    check = next(check for check in checks if check.check_id == "customers_pk_unique")
    assert check.metric == len(check.issues)


def test_regex_uses_full_match():
    check = {
        "id": "r1",
        "type": "regex",
        "table": "t",
        "column": "x",
        "pattern": r"\d{4}",
        "allow_null": True,
        "severity": "high",
    }
    result = regex({"t": pd.DataFrame({"x": ["1234abc", "1234"]})}, check)
    assert not result.passed
    assert len(result.issues) == 1


def test_referential_integrity_rejects_blank_child():
    check = {
        "id": "f1",
        "type": "referential_integrity",
        "table": "child",
        "column": "cid",
        "parent_table": "parent",
        "parent_column": "cid",
        "severity": "high",
    }
    context = {
        "parent": pd.DataFrame({"cid": ["C1", ""]}),
        "child": pd.DataFrame({"cid": ["C1", "", "C2"]}),
    }
    result = referential_integrity(context, check)
    assert len(result.issues) == 2


def test_issue_key_is_stable_across_messages():
    a = Issue("c1", "null_rate", "t", None, "x", None, "high", "rate 1%")
    b = Issue("c1", "null_rate", "t", None, "x", None, "high", "rate 2%")
    assert a.issue_key == b.issue_key


def test_errored_check_never_passes(tmp_path: Path):
    data = tmp_path / "t.csv"
    pd.DataFrame({"id": ["a"]}).to_csv(data, index=False)
    config = {
        "project_name": "DataGuard",
        "base_dir": str(tmp_path),
        "sources": {"t": {"type": "csv", "path": "t.csv", "primary_key": "id"}},
        "checks": [
            {"id": "missing_column", "type": "not_null", "table": "t", "column": "absent", "severity": "low"}
        ],
        "thresholds": {"fail_on_high": True},
    }
    config_path = tmp_path / "rules.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    summary, checks, _ = run_from_config(config_path)
    assert checks[0].error
    assert summary.status == "failed"


def test_duplicate_pk_issues_have_distinct_keys(tmp_path: Path):
    _, checks, _ = run_from_config(make_project(tmp_path))
    check = next(c for c in checks if c.check_id == "customers_pk_unique")
    assert len(check.issues) == 2
    assert len({issue.issue_key for issue in check.issues}) == 2
