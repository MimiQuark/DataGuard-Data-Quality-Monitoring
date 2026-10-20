from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha1


@dataclass
class Issue:
    check_id: str
    rule_type: str
    table: str
    row_index: int | None
    column: str | None
    value: str | None
    severity: str
    message: str
    row_key: str | None = None
    issue_key: str = ""

    def __post_init__(self):
        if not self.issue_key:
            identity = (
                f"key:{self.row_key}"
                if self.row_key not in (None, "")
                else f"row:{self.row_index}"
                if self.row_index is not None
                else "aggregate"
            )
            raw = "|".join(
                [self.check_id, self.table, identity, self.column or "", self.rule_type]
            )
            self.issue_key = sha1(raw.encode("utf-8")).hexdigest()

    def to_dict(self):
        return asdict(self)


@dataclass
class CheckResult:
    check_id: str
    rule_type: str
    table: str
    severity: str
    passed: bool
    checked_rows: int
    metric: float | int | None
    message: str
    duration_ms: float
    issues: list[Issue] = field(default_factory=list)
    error: str | None = None

    def to_dict(self):
        data = asdict(self)
        data["issues"] = [issue.to_dict() for issue in self.issues]
        return data


@dataclass
class RunSummary:
    run_id: str
    project_name: str
    started_at: datetime
    finished_at: datetime
    status: str
    total_checks: int
    passed_checks: int
    failed_checks: int
    issue_count: int
    high_count: int
    medium_count: int
    low_count: int
    duration_seconds: float

    def to_dict(self):
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat(timespec="seconds")
        data["finished_at"] = self.finished_at.isoformat(timespec="seconds")
        return data
