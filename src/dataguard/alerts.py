from __future__ import annotations

import json
from urllib import request


def build_alert(summary):
    return {
        "event": "data_quality_run",
        "status": summary.status,
        "run_id": summary.run_id,
        "project": summary.project_name,
        "issue_count": summary.issue_count,
        "high_count": summary.high_count,
        "medium_count": summary.medium_count,
        "low_count": summary.low_count,
    }


def emit_webhook(url: str, payload: dict, timeout: int = 10) -> dict:
    """Post the alert without aborting the report pipeline on webhook failure."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_obj = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(request_obj, timeout=timeout) as response:
            return {"ok": True, "status": response.status}
    except Exception as exc:  # malformed URLs can raise http.client.HTTPException
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
