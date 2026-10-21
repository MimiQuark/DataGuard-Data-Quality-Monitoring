from __future__ import annotations

import argparse
import json
from pathlib import Path

from .alerts import build_alert, emit_webhook
from .engine import ConfigError, run_from_config
from .report import build_report
from .storage import RunStorage

BASE_DIR = Path(__file__).resolve().parents[2]


def parse_args():
    parser = argparse.ArgumentParser(description="Run configurable data quality checks.")
    parser.add_argument("--config", default=str(BASE_DIR / "config" / "rules.json"))
    parser.add_argument("--output-dir", default=str(BASE_DIR / "output"))
    parser.add_argument("--db", default=str(BASE_DIR / "output" / "dq_history.sqlite"))
    parser.add_argument("--webhook-url", default=None)
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Return exit code 0 even when high-severity issues exist.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary, checks, context = run_from_config(args.config)
    except (ConfigError, FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 2

    storage = RunStorage(args.db)
    issues = [issue for check in checks for issue in check.issues]
    storage.save_run(
        summary,
        issues,
        executed_check_ids=[check.check_id for check in checks if check.error is None],
    )
    history = storage.history(30)
    outputs = build_report(context, history, args.output_dir)
    alert = build_alert(summary)
    if args.webhook_url:
        alert["webhook_status"] = emit_webhook(args.webhook_url, alert)
    result = {"summary": summary.to_dict(), "outputs": outputs, "alert": alert}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if summary.status == "failed" and not args.no_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
