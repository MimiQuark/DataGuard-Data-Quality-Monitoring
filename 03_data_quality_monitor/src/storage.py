from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


class RunStorage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self):
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS run_history (
                    run_id TEXT PRIMARY KEY, project_name TEXT NOT NULL, started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL, status TEXT NOT NULL, total_checks INTEGER NOT NULL,
                    passed_checks INTEGER NOT NULL, failed_checks INTEGER NOT NULL, issue_count INTEGER NOT NULL,
                    high_count INTEGER NOT NULL, medium_count INTEGER NOT NULL, low_count INTEGER NOT NULL,
                    duration_seconds REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS issue_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, issue_key TEXT NOT NULL,
                    check_id TEXT NOT NULL, rule_type TEXT NOT NULL, table_name TEXT NOT NULL,
                    row_index INTEGER, column_name TEXT, value TEXT, severity TEXT NOT NULL,
                    message TEXT NOT NULL, FOREIGN KEY (run_id) REFERENCES run_history(run_id)
                );
                CREATE TABLE IF NOT EXISTS issue_registry (
                    issue_key TEXT PRIMARY KEY, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                    resolved_at TEXT, status TEXT NOT NULL, occurrences INTEGER NOT NULL DEFAULT 1,
                    check_id TEXT NOT NULL, rule_type TEXT NOT NULL, table_name TEXT NOT NULL,
                    row_index INTEGER, column_name TEXT, value TEXT, severity TEXT NOT NULL, message TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_issue_history_run ON issue_history(run_id);
                CREATE INDEX IF NOT EXISTS idx_issue_registry_status ON issue_registry(status);
                """
            )

    def save_run(self, summary, issues):
        data = summary.to_dict()
        now = summary.finished_at.isoformat(timespec="seconds")
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO run_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (data["run_id"], data["project_name"], data["started_at"], data["finished_at"], data["status"],
                 data["total_checks"], data["passed_checks"], data["failed_checks"], data["issue_count"],
                 data["high_count"], data["medium_count"], data["low_count"], data["duration_seconds"]),
            )
            for issue in issues:
                item = issue.to_dict()
                connection.execute(
                    """INSERT INTO issue_history
                    (run_id, issue_key, check_id, rule_type, table_name, row_index, column_name, value, severity, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (summary.run_id, item["issue_key"], item["check_id"], item["rule_type"], item["table"], item["row_index"],
                     item["column"], item["value"], item["severity"], item["message"]),
                )
                connection.execute(
                    """INSERT INTO issue_registry
                    (issue_key, first_seen, last_seen, resolved_at, status, occurrences, check_id, rule_type, table_name,
                     row_index, column_name, value, severity, message)
                    VALUES (?, ?, ?, NULL, 'open', 1, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(issue_key) DO UPDATE SET
                        last_seen=excluded.last_seen, status='open', resolved_at=NULL,
                        occurrences=issue_registry.occurrences + 1, message=excluded.message""",
                    (item["issue_key"], now, now, item["check_id"], item["rule_type"], item["table"], item["row_index"],
                     item["column"], item["value"], item["severity"], item["message"]),
                )
            keys = [issue.issue_key for issue in issues]
            if keys:
                placeholders = ",".join("?" for _ in keys)
                connection.execute(
                    f"UPDATE issue_registry SET status='resolved', resolved_at=? WHERE status='open' AND issue_key NOT IN ({placeholders})",
                    [now, *keys],
                )
            else:
                connection.execute("UPDATE issue_registry SET status='resolved', resolved_at=? WHERE status='open'", (now,))
            connection.commit()

    def history(self, limit=30):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM run_history ORDER BY finished_at DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def open_issues(self):
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM issue_registry WHERE status='open' ORDER BY severity DESC, table_name, row_index").fetchall()
        return [dict(row) for row in rows]