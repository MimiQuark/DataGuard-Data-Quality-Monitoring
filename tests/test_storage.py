from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from dataguard.engine import run_from_config
from dataguard.models import Issue, RunSummary
from dataguard.storage import RunStorage
from fixtures import make_project


def _summary(project="DataGuard", status="failed"):
    now = datetime.now()
    return RunSummary(
        run_id=f"run-{now.timestamp()}",
        project_name=project,
        started_at=now,
        finished_at=now,
        status=status,
        total_checks=1,
        passed_checks=0,
        failed_checks=1,
        issue_count=3,
        high_count=1,
        medium_count=1,
        low_count=1,
        duration_seconds=0.1,
    )


def test_severity_order_is_high_medium_low(tmp_path: Path):
    storage = RunStorage(tmp_path / "dq.sqlite")
    issues = [
        Issue("c1", "not_null", "t", 2, "x", None, "low", "low issue", row_key="a"),
        Issue("c1", "not_null", "t", 3, "x", None, "high", "high issue", row_key="b"),
        Issue("c1", "not_null", "t", 4, "x", None, "medium", "medium issue", row_key="c"),
    ]
    storage.save_run(_summary(), issues, executed_check_ids=["c1"])
    assert [issue["severity"] for issue in storage.open_issues()] == ["high", "medium", "low"]


def test_partial_config_does_not_close_other_checks(tmp_path: Path):
    config_path = make_project(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    customers = dict(config)
    customers["checks"] = [
        check for check in config["checks"] if check["table"] == "customers"
    ]
    orders = dict(config)
    orders["checks"] = [check for check in config["checks"] if check["table"] == "orders"]
    customers_path = tmp_path / "customers.json"
    orders_path = tmp_path / "orders.json"
    customers_path.write_text(json.dumps(customers, ensure_ascii=False), encoding="utf-8")
    orders_path.write_text(json.dumps(orders, ensure_ascii=False), encoding="utf-8")

    storage = RunStorage(tmp_path / "dq.sqlite")
    summary, checks, _ = run_from_config(customers_path)
    storage.save_run(
        summary,
        [issue for check in checks for issue in check.issues],
        executed_check_ids=[check.check_id for check in checks],
    )
    customer_open = len(storage.open_issues(summary.project_name))
    assert customer_open > 0

    summary2, checks2, _ = run_from_config(orders_path)
    storage.save_run(
        summary2,
        [issue for check in checks2 for issue in check.issues],
        executed_check_ids=[check.check_id for check in checks2],
    )
    assert len(storage.open_issues(summary.project_name)) >= customer_open


def test_projects_are_isolated_in_registry(tmp_path: Path):
    storage = RunStorage(tmp_path / "dq.sqlite")
    issue = Issue("c1", "not_null", "t", 2, "x", None, "high", "issue", row_key="a")
    storage.save_run(_summary(project="A"), [issue], executed_check_ids=["c1"])
    storage.save_run(_summary(project="B"), [issue], executed_check_ids=["c1"])
    assert len(storage.open_issues("A")) == 1
    assert len(storage.open_issues("B")) == 1


def test_second_run_resolves_fixed_issue(tmp_path: Path):
    data = tmp_path / "t.csv"
    config = {
        "project_name": "DataGuard",
        "base_dir": str(tmp_path),
        "sources": {"t": {"type": "csv", "path": "t.csv", "primary_key": "id"}},
        "checks": [
            {"id": "t_not_null", "type": "not_null", "table": "t", "column": "id", "severity": "high"}
        ],
        "thresholds": {"fail_on_high": True},
    }
    config_path = tmp_path / "rules.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    storage = RunStorage(tmp_path / "dq.sqlite")

    pd.DataFrame({"id": ["", "x"]}).to_csv(data, index=False)
    summary, checks, _ = run_from_config(config_path)
    storage.save_run(summary, [i for c in checks for i in c.issues], [c.check_id for c in checks])
    assert len(storage.open_issues("DataGuard")) == 1

    pd.DataFrame({"id": ["a", "x"]}).to_csv(data, index=False)
    summary2, checks2, _ = run_from_config(config_path)
    storage.save_run(summary2, [i for c in checks2 for i in c.issues], [c.check_id for c in checks2])
    assert storage.open_issues("DataGuard") == []
    assert len(storage.history()) == 2
