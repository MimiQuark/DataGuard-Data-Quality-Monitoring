from __future__ import annotations

from pathlib import Path

from dataguard.report import build_report


def _context():
    return {
        "summary": {
            "run_id": "run-1",
            "project_name": "DataGuard",
            "started_at": "2026-01-15T10:00:00",
            "finished_at": "2026-01-15T10:00:01",
            "status": "failed",
            "total_checks": 1,
            "passed_checks": 0,
            "failed_checks": 1,
            "issue_count": 1,
            "high_count": 1,
            "medium_count": 0,
            "low_count": 0,
            "duration_seconds": 0.1,
        },
        "checks": [
            {
                "check_id": "c1",
                "rule_type": "not_null",
                "table": "t",
                "severity": "high",
                "passed": False,
                "metric": 1,
                "message": "x 不能为空",
                "error": None,
            }
        ],
        "issues": [
            {
                "issue_key": "k1",
                "check_id": "c1",
                "rule_type": "not_null",
                "table": "t",
                "row_index": 2,
                "column": "x",
                "value": "=cmd",
                "severity": "high",
                "message": "+malicious",
            }
        ],
        "sources": {"t": {"rows": 1, "columns": ["x"]}},
    }


def test_csv_formula_injection_is_escaped(tmp_path: Path):
    build_report(_context(), [], tmp_path)
    text = (tmp_path / "issues.csv").read_text(encoding="utf-8-sig")
    assert "'=cmd" in text
    assert "'+malicious" in text


def test_trend_labels_include_time(tmp_path: Path):
    history = [
        {"finished_at": "2026-01-15T10:00:00", "issue_count": 1},
        {"finished_at": "2026-01-15T11:30:00", "issue_count": 2},
    ]
    build_report(_context(), history, tmp_path)
    html = (tmp_path / "dq_report.html").read_text(encoding="utf-8")
    assert "01-15 10:00" in html
    assert "01-15 11:30" in html
