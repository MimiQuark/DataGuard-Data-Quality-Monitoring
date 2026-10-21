from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from .models import CheckResult, RunSummary
from .rules import get_rule, registered_rules

VALID_SEVERITIES = {"high", "medium", "low"}

REQUIRED_FIELDS = {
    "required_columns": ("columns",),
    "not_null": ("column",),
    "unique": ("columns",),
    "null_rate": ("columns", "max_rate"),
    "regex": ("column", "pattern"),
    "allowed_values": ("column", "values"),
    "range": ("column",),
    "date_not_after": ("column", "as_of_date"),
    "referential_integrity": ("column", "parent_table", "parent_column"),
    "cross_table_consistency": (
        "key_column",
        "value_column",
        "parent_table",
        "parent_key_column",
        "parent_value_column",
    ),
    "freshness": ("column", "as_of_date", "max_age_days"),
    "row_count": (),
}


class ConfigError(ValueError):
    """Raised when the quality-monitor configuration is invalid."""


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise ConfigError("配置必须是 JSON 对象")
    sources = config.get("sources")
    checks = config.get("checks")
    if not isinstance(sources, dict) or not sources:
        raise ConfigError("sources 必须是非空对象")
    if not isinstance(checks, list) or not checks:
        raise ConfigError("checks 必须是非空数组")
    for name, source in sources.items():
        if not isinstance(source, dict):
            raise ConfigError(f"数据源 {name} 必须是对象")
        source_type = source.get("type", "csv")
        if source_type not in {"csv", "mysql"}:
            raise ConfigError(f"数据源 {name} 的 type 不支持: {source_type}")
        if source_type == "csv" and not source.get("path"):
            raise ConfigError(f"数据源 {name} 缺少 path")
        if source_type == "mysql":
            if not source.get("query"):
                raise ConfigError(f"数据源 {name} 缺少 query")
            for field in ("host", "user", "database"):
                if not source.get(field):
                    raise ConfigError(f"MySQL 数据源 {name} 缺少 {field}")
            try:
                int(source.get("port", 3306))
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"MySQL 数据源 {name} 的 port 不是整数") from exc

    seen_ids = set()
    known_rules = set(registered_rules())
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ConfigError(f"第 {index + 1} 个 check 必须是对象")
        check_id = check.get("id")
        if not isinstance(check_id, str) or not check_id:
            raise ConfigError(f"第 {index + 1} 个 check 缺少有效 id")
        if check_id in seen_ids:
            raise ConfigError(f"check id 重复: {check_id}")
        seen_ids.add(check_id)
        rule_type = check.get("type")
        if rule_type not in known_rules:
            raise ConfigError(f"check {check_id} 使用未知规则类型: {rule_type}")
        table = check.get("table")
        if not isinstance(table, str) or table not in sources:
            raise ConfigError(f"check {check_id} 引用了未知数据源: {table}")
        severity = check.get("severity", "medium")
        if severity not in VALID_SEVERITIES:
            raise ConfigError(
                f"check {check_id} 的 severity 必须是 high/medium/low，实际为 {severity}"
            )
        for field in REQUIRED_FIELDS[rule_type]:
            if field not in check:
                raise ConfigError(f"check {check_id} 缺少字段: {field}")
        for field in ("column",):
            if field in check and (not isinstance(check[field], str) or not check[field]):
                raise ConfigError(f"check {check_id} 的 {field} 必须是非空字符串")
        for field in ("columns",):
            if field in check and (
                not isinstance(check[field], list)
                or not check[field]
                or not all(isinstance(item, str) and item for item in check[field])
            ):
                raise ConfigError(f"check {check_id} 的 {field} 必须是非空字符串数组")
        if "values" in check and (
            not isinstance(check["values"], list) or not check["values"]
        ):
            raise ConfigError(f"check {check_id} 的 values 必须是非空数组")
        for field in ("max_rate", "min", "max", "max_age_days"):
            if field in check:
                try:
                    float(check[field])
                except (TypeError, ValueError) as exc:
                    raise ConfigError(f"check {check_id} 的 {field} 不是数字") from exc
        if rule_type == "regex":
            try:
                re.compile(check["pattern"])
            except re.error as exc:
                raise ConfigError(f"check {check_id} 的正则无效: {exc}") from exc
        if rule_type == "row_count" and "min" not in check and "max" not in check:
            raise ConfigError(f"check {check_id} 的 row_count 必须设置 min 或 max")
        if rule_type in {"date_not_after", "freshness"}:
            try:
                datetime.strptime(str(check["as_of_date"]), "%Y-%m-%d")
            except ValueError as exc:
                raise ConfigError(f"check {check_id} 的 as_of_date 不是 YYYY-MM-DD") from exc
        if rule_type == "referential_integrity" and check["parent_table"] not in sources:
            raise ConfigError(f"check {check_id} 引用了未知父表: {check['parent_table']}")
        if rule_type == "cross_table_consistency" and check["parent_table"] not in sources:
            raise ConfigError(f"check {check_id} 引用了未知父表: {check['parent_table']}")

    thresholds = config.get("thresholds", {})
    if not isinstance(thresholds, dict):
        raise ConfigError("thresholds 必须是对象")
    if "fail_on_high" in thresholds and not isinstance(thresholds["fail_on_high"], bool):
        raise ConfigError("thresholds.fail_on_high 必须是布尔值")


class DataQualityEngine:
    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path).resolve()
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        validate_config(self.config)
        configured_base = self.config.get("base_dir")
        self.base_dir = (
            Path(configured_base).expanduser().resolve()
            if configured_base
            else self.config_path.parent.parent
        )
        self.tables: dict[str, pd.DataFrame] = {}
        self.checks: list[CheckResult] = []

    def load_table(self, name: str, source: dict) -> pd.DataFrame:
        source_type = source.get("type", "csv")
        if source_type == "csv":
            path = Path(source["path"])
            if not path.is_absolute():
                path = self.base_dir / path
            return pd.read_csv(
                path, dtype=str, keep_default_na=False, encoding="utf-8-sig"
            )
        if source_type == "mysql":
            try:
                import pymysql
            except ImportError as exc:
                raise RuntimeError(
                    "MySQL source requires PyMySQL. Install: pip install '.[mysql]'"
                ) from exc
            connection = pymysql.connect(
                host=source["host"],
                port=int(source.get("port", 3306)),
                user=source["user"],
                password=source.get("password", ""),
                database=source["database"],
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
        started_at = datetime.now()
        started = time.perf_counter()
        self.load_all()
        self.checks = []
        for check in self.config["checks"]:
            enriched = dict(check)
            enriched["_primary_key"] = self.config["sources"][check["table"]].get(
                "primary_key"
            )
            try:
                self.checks.append(get_rule(check["type"])(self.tables, enriched))
            except Exception as exc:  # isolate one bad rule from the whole run
                self.checks.append(
                    CheckResult(
                        check_id=check["id"],
                        rule_type=check["type"],
                        table=check.get("table", ""),
                        severity=check.get("severity", "medium"),
                        passed=False,
                        checked_rows=0,
                        metric=None,
                        message="检查执行失败",
                        duration_ms=0.0,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
        finished_at = datetime.now()
        issues = [issue for check in self.checks for issue in check.issues]
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        failed_checks = sum(1 for check in self.checks if not check.passed)
        error_count = sum(1 for check in self.checks if check.error)
        fail_on_high = bool(self.config.get("thresholds", {}).get("fail_on_high", True))
        if (severity_counts["high"] and fail_on_high) or error_count:
            status = "failed"
        elif issues or failed_checks:
            status = "warning"
        else:
            status = "passed"
        summary = RunSummary(
            run_id=uuid.uuid4().hex,
            project_name=self.config.get("project_name", "DataGuard"),
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
            "sources": {
                name: {"rows": len(frame), "columns": list(frame.columns)}
                for name, frame in self.tables.items()
            },
        }
        return summary, self.checks, context


def run_from_config(config_path: str | Path):
    return DataQualityEngine(config_path).run()
