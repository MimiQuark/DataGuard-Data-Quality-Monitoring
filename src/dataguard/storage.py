from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from hashlib import sha1
from pathlib import Path

SEVERITY_ORDER = "CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END"


class RunStorage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
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
                    issue_key TEXT PRIMARY KEY, project_name TEXT NOT NULL DEFAULT '',
                    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                    resolved_at TEXT, status TEXT NOT NULL, occurrences INTEGER NOT NULL DEFAULT 1,
                    check_id TEXT NOT NULL, rule_type TEXT NOT NULL, table_name TEXT NOT NULL,
                    row_index INTEGER, column_name TEXT, value TEXT, severity TEXT NOT NULL, message TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_issue_history_run ON issue_history(run_id);
                CREATE INDEX IF NOT EXISTS idx_issue_registry_status ON issue_registry(status);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(issue_registry)")
            }
            if "project_name" not in columns:
                connection.execute(
                    "ALTER TABLE issue_registry ADD COLUMN project_name TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_issue_registry_scope "
                "ON issue_registry(project_name, check_id, status)"
            )
            connection.execute("PRAGMA user_version = 2")

    def save_run(self, summary, issues, executed_check_ids):
        data = summary.to_dict()
        now = summary.finished_at.isoformat(timespec="seconds")
        executed = sorted(set(executed_check_ids))
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO run_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    data["run_id"],
                    data["project_name"],
                    data["started_at"],
                    data["finished_at"],
                    data["status"],
                    data["total_checks"],
                    data["passed_checks"],
                    data["failed_checks"],
                    data["issue_count"],
                    data["high_count"],
                    data["medium_count"],
                    data["low_count"],
                    data["duration_seconds"],
                ),
            )
            registry_keys = []
            for issue in issues:
                item = issue.to_dict()
                registry_key = sha1(
                    f"{data['project_name']}|{item['issue_key']}".encode("utf-8")
                ).hexdigest()
                registry_keys.append(registry_key)
                connection.execute(
                    """INSERT INTO issue_history
                    (run_id, issue_key, check_id, rule_type, table_name, row_index, column_name, value, severity, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        summary.run_id,
                        item["issue_key"],
                        item["check_id"],
                        item["rule_type"],
                        item["table"],
                        item["row_index"],
                        item["column"],
                        item["value"],
                        item["severity"],
                        item["message"],
                    ),
                )
                connection.execute(
                    """INSERT INTO issue_registry
                    (issue_key, project_name, first_seen, last_seen, resolved_at, status, occurrences,
                     check_id, rule_type, table_name, row_index, column_name, value, severity, message)
                    VALUES (?, ?, ?, ?, NULL, 'open', 1, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(issue_key) DO UPDATE SET
                        last_seen=excluded.last_seen, status='open', resolved_at=NULL,
                        occurrences=issue_registry.occurrences + 1, value=excluded.value,
                        severity=excluded.severity, message=excluded.message,
                        row_index=excluded.row_index, column_name=excluded.column_name""",
                    (
                        registry_key,
                        data["project_name"],
                        now,
                        now,
                        item["check_id"],
                        item["rule_type"],
                        item["table"],
                        item["row_index"],
                        item["column"],
                        item["value"],
                        item["severity"],
                        item["message"],
                    ),
                )
            keys = registry_keys
            if executed:
                placeholders = ",".join("?" for _ in executed)
                params = [now, data["project_name"], *executed]
                sql = (
                    "UPDATE issue_registry SET status='resolved', resolved_at=? "
                    "WHERE status='open' AND project_name=? "
                    f"AND check_id IN ({placeholders})"
                )
                if keys:
                    key_placeholders = ",".join("?" for _ in keys)
                    sql += f" AND issue_key NOT IN ({key_placeholders})"
                    params += keys
                connection.execute(sql, params)
            connection.commit()

    def history(self, limit=30):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM run_history ORDER BY finished_at DESC LIMIT ?", (int(limit),)
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def open_issues(self, project_name=None):
        with self.connection() as connection:
            if project_name is None:
                rows = connection.execute(
                    f"SELECT * FROM issue_registry WHERE status='open' ORDER BY {SEVERITY_ORDER}, table_name, row_index"
                ).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT * FROM issue_registry WHERE status='open' AND project_name=? "
                    f"ORDER BY {SEVERITY_ORDER}, table_name, row_index",
                    (project_name,),
                ).fetchall()
        return [dict(row) for row in rows]
