from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR / "src"))

from engine import run_from_config  # noqa: E402
from report import build_report  # noqa: E402
from storage import RunStorage  # noqa: E402


class DataQualityMonitorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary, cls.checks, cls.context = run_from_config(BASE_DIR / "config" / "rules.json")

    def test_engine_detects_known_defects(self):
        self.assertEqual(self.summary.status, "failed")
        self.assertGreaterEqual(self.summary.total_checks, 20)
        self.assertGreaterEqual(self.summary.issue_count, 10)
        self.assertGreater(self.summary.high_count, 0)

    def test_rule_families_are_covered(self):
        descriptions = json.dumps(self.context["issues"], ensure_ascii=False)
        for expected in ["不能为空", "唯一键重复", "格式不符合规则", "超出数值范围", "父表中不存在", "字段值与父表不一致"]:
            self.assertIn(expected, descriptions)

    def test_storage_history_and_open_issues(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = RunStorage(Path(temp_dir) / "dq.sqlite")
            issues = [issue for check in self.checks for issue in check.issues]
            storage.save_run(self.summary, issues)
            history = storage.history()
            open_issues = storage.open_issues()
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["run_id"], self.summary.run_id)
            self.assertEqual(len(open_issues), len(issues))

    def test_report_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            outputs = build_report(self.context, [], temp_dir)
            report_path = Path(outputs["report"])
            issues_path = Path(outputs["issues_csv"])
            summary_path = Path(outputs["summary_json"])
            self.assertTrue(report_path.exists())
            self.assertTrue(issues_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertIn("数据质量监控报告", report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(issues_path.read_text(encoding="utf-8-sig").splitlines()), self.summary.issue_count + 1)


if __name__ == "__main__":
    unittest.main()