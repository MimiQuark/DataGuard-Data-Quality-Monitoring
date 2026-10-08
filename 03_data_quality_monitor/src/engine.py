from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from models import CheckResult, RunSummary
from rules import get_rule


class DataQualityEngine:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.base_dir = self.config_path.parent.parent
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.tables: dict[str, pd.DataFrame] = {}
        self.checks: list[CheckResult] = []

    def load_table(self, name: str, source: dict) -> pd.DataFrame:
        source_type = source.get("type", "csv")
        if source_type == "csv":
            path = Path(source["path"])
            if not path.is_absolute():
                path = self.base_dir / path
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        if source_type == "mysql":
            try:
                import pymysql
            except ImportError as exc:
                raise RuntimeError("MySQL source requires PyMySQL. Install requirements.txt.") from exc
            connection = pymysql.connect(
                host=source["host"], port=int(source.get("port", 3306)), user=source["user"],
                password=source.get("password", ""), database=source["database"],
                charset=source.get("charset", "utf8mb4"),
            )
            try:
                return pd.read_sql_query(source["query"], connection)
            finally:
                connection.close()
        raise ValueError(f"Unsupported source type: {source_type}")

    def load_all(self):
        for name, source in self.config["sources"].items():
            self.tables[name] = self.load_table(name, source)

    def run(self) -> tuple[RunSummary, list[CheckResult], dict]:
        self.load_all()
        started_at = datetime.now()
        started = time.perf_counter()
        self.checks = []
        for check in self.config["checks"]:
            self.checks.append(get_rule(check["type"])(self.tables, check))
        finished_at = datetime.now()
        issues = [issue for check in self.checks for issue in check.issues]
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        failed_checks = sum(1 for check in self.checks if not check.passed)
        status = "failed" if severity_counts["high"] else "warning" if severity_counts["medium"] else "passed"
        summary = RunSummary(
            run_id=uuid.uuid4().hex,
            project_name=self.config.get("project_name", "Data Quality Monitor"),
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            total_checks=len(self.checks),
            passed_checks=len(self.checks) - failed_checks,
            failed_checks=failed_checks,
            issue_count=len(issues),
            high_count=severity_counts["high"],
            medium_count=severity_counts["medium"],
            low_count=severity_counts["low"],
            duration_seconds=round(time.perf_counter() - started, 3),
        )
        context = {
            "summary": summary.to_dict(),
            "checks": [check.to_dict() for check in self.checks],
            "issues": [issue.to_dict() for issue in issues],
            "sources": {name: {"rows": len(frame), "columns": list(frame.columns)} for name, frame in self.tables.items()},
        }
        return summary, self.checks, context


def run_from_config(config_path: str | Path):
    return DataQualityEngine(config_path).run()