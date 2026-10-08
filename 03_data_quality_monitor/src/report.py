from __future__ import annotations

import csv
import html
import json
from pathlib import Path

SEVERITY_CN = {"high": "高", "medium": "中", "low": "低"}
STATUS_CN = {"passed": "通过", "warning": "告警", "failed": "失败"}


def esc(value):
    return html.escape("" if value is None else str(value))


def severity_badge(severity):
    return f"<span class='badge {esc(severity)}'>{esc(SEVERITY_CN.get(severity, severity))}</span>"


def build_trend_svg(history):
    if not history:
        return "<p>暂无历史趋势。</p>"
    width, height = 1000, 220
    max_issues = max([int(row.get("issue_count", 0)) for row in history] + [1])
    points = []
    labels = []
    for index, row in enumerate(history):
        x = 40 + index * ((width - 80) / max(1, len(history) - 1))
        y = height - 30 - (int(row.get("issue_count", 0)) / max_issues * (height - 60))
        points.append(f"{x:.1f},{y:.1f}")
        labels.append(f"<text x='{x:.1f}' y='{height - 8}' text-anchor='middle' font-size='10' fill='#64748b'>{esc(row['finished_at'][5:10])}</text>")
    return (
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='问题数量趋势'>"
        f"<line x1='40' y1='{height-30}' x2='{width-40}' y2='{height-30}' stroke='#cbd5e1'/>"
        f"<polyline points='{' '.join(points)}' fill='none' stroke='#1f4e79' stroke-width='4'/>"
        + "".join(labels) + "</svg>"
    )


def build_report(context, history, output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = context["summary"]
    issues = context["issues"]
    checks = context["checks"]

    issues_path = output_dir / "issues.csv"
    with issues_path.open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["issue_key", "check_id", "rule_type", "table", "row_index", "column", "value", "severity", "message"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(issues)

    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

    source_rows = "".join(
        f"<tr><td>{esc(name)}</td><td>{info['rows']:,}</td><td>{len(info['columns'])}</td></tr>"
        for name, info in context["sources"].items()
    )
    check_rows = "".join(
        "<tr>"
        f"<td>{esc(check['check_id'])}</td><td>{esc(check['rule_type'])}</td><td>{esc(check['table'])}</td>"
        f"<td>{severity_badge(check['severity'])}</td><td>{'通过' if check['passed'] else '失败'}</td>"
        f"<td>{esc(check['metric'])}</td><td>{esc(check['message'])}</td>"
        "</tr>"
        for check in checks
    )
    issue_rows = "".join(
        "<tr>"
        f"<td>{severity_badge(issue['severity'])}</td><td>{esc(issue['check_id'])}</td>"
        f"<td>{esc(issue['table'])}</td><td>{esc(issue['row_index'])}</td><td>{esc(issue['column'])}</td>"
        f"<td>{esc(issue['value'])}</td><td>{esc(issue['message'])}</td>"
        "</tr>"
        for issue in issues[:300]
    )
    trend = build_trend_svg(history)

    html_text = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>数据质量监控报告</title>
<style>
:root{{--navy:#1f4e79;--blue:#2f80ed;--ink:#17212b;--muted:#64748b;--line:#dbe4ee;--bg:#f5f8fb;--red:#c62828;--amber:#b26a00;--green:#2e7d32}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Microsoft YaHei",Arial,sans-serif}}
main{{max-width:1240px;margin:0 auto;padding:32px 24px 56px}}h1{{margin:0;color:var(--navy);font-size:30px}}h2{{margin:0 0 16px;color:var(--navy);font-size:18px}}
.subtitle{{color:var(--muted);margin-top:6px}}.grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin:22px 0}}
.card,.panel{{background:white;border:1px solid var(--line);border-radius:14px;box-shadow:0 6px 18px rgba(31,78,121,.06)}}
.card{{padding:18px}}.card .label{{color:var(--muted)}}.card .value{{font-size:25px;font-weight:700;margin-top:5px}}
.panel{{padding:20px;margin-bottom:18px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{background:#f8fbfe;color:var(--navy)}}.badge{{display:inline-block;padding:2px 8px;border-radius:999px;color:white;font-size:12px}}
.badge.high{{background:var(--red)}}.badge.medium{{background:var(--amber)}}.badge.low{{background:var(--green)}}
.status{{display:inline-block;padding:6px 12px;border-radius:999px;color:white;background:{'#c62828' if summary['status']=='failed' else '#b26a00' if summary['status']=='warning' else '#2e7d32'}}}
footer{{color:var(--muted);text-align:center;margin-top:24px}}@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><main>
<h1>数据质量监控报告</h1><div class="subtitle">{esc(summary['project_name'])} · Run ID {esc(summary['run_id'])}</div>
<div class="grid">
<div class="card"><div class="label">总体状态</div><div class="value"><span class="status">{esc(STATUS_CN.get(summary['status'], summary['status']))}</span></div></div>
<div class="card"><div class="label">检查项</div><div class="value">{summary['total_checks']}</div></div>
<div class="card"><div class="label">通过 / 失败</div><div class="value">{summary['passed_checks']} / {summary['failed_checks']}</div></div>
<div class="card"><div class="label">问题总数</div><div class="value">{summary['issue_count']}</div></div>
<div class="card"><div class="label">高中低</div><div class="value">{summary['high_count']} / {summary['medium_count']} / {summary['low_count']}</div></div>
</div>
<div class="panel"><h2>问题数量趋势</h2>{trend}</div>
<div class="panel"><h2>数据源概览</h2><table><thead><tr><th>数据表</th><th>记录数</th><th>字段数</th></tr></thead><tbody>{source_rows}</tbody></table></div>
<div class="panel"><h2>检查结果</h2><table><thead><tr><th>检查 ID</th><th>规则</th><th>数据表</th><th>等级</th><th>结果</th><th>指标</th><th>说明</th></tr></thead><tbody>{check_rows}</tbody></table></div>
<div class="panel"><h2>问题明细（最多展示 300 条）</h2><table><thead><tr><th>等级</th><th>检查 ID</th><th>数据表</th><th>行号</th><th>字段</th><th>值</th><th>问题</th></tr></thead><tbody>{issue_rows}</tbody></table></div>
<footer>执行时间：{esc(summary['finished_at'])} · 耗时：{summary['duration_seconds']} 秒</footer>
</main></body></html>"""
    report_path = output_dir / "dq_report.html"
    report_path.write_text(html_text, encoding="utf-8")
    return {"report": str(report_path), "issues_csv": str(issues_path), "summary_json": str(summary_path)}