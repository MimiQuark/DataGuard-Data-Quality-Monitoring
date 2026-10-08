from __future__ import annotations

import re
from datetime import datetime
from typing import Callable

import pandas as pd

from models import CheckResult, Issue

RuleFunction = Callable[[dict[str, pd.DataFrame], dict], CheckResult]
_REGISTRY: dict[str, RuleFunction] = {}


def register(name: str):
    def decorator(function: RuleFunction) -> RuleFunction:
        _REGISTRY[name] = function
        return function
    return decorator


def get_rule(name: str) -> RuleFunction:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown rule type: {name}")
    return _REGISTRY[name]


def registered_rules() -> list[str]:
    return sorted(_REGISTRY)


def value_text(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def make_issue(check, row_index=None, column=None, value=None, message="", severity=None) -> Issue:
    return Issue(check_id=check["id"], rule_type=check["type"], table=check.get("table", ""), row_index=row_index,
                 column=column, value=value_text(value), severity=severity or check.get("severity", "medium"), message=message)


def result(check, issues, checked_rows, metric, message, started):
    return CheckResult(check_id=check["id"], rule_type=check["type"], table=check.get("table", ""),
                       severity=check.get("severity", "medium"), passed=not issues, checked_rows=checked_rows,
                       metric=metric, message=message, duration_ms=round((datetime.now() - started).total_seconds() * 1000, 2), issues=issues)


@register("required_columns")
def required_columns(context, check):
    started = datetime.now(); frame = context[check["table"]]
    missing = [column for column in check["columns"] if column not in frame.columns]
    issues = [make_issue(check, column=column, message=f"缺少必需字段：{column}") for column in missing]
    return result(check, issues, len(frame), len(missing), "字段完整性检查", started)


@register("not_null")
def not_null(context, check):
    started = datetime.now(); frame = context[check["table"]]; column = check["column"]
    missing = frame[column].isna() | (frame[column].astype(str).str.strip() == "")
    issues = [make_issue(check, int(index) + 2, column, frame.at[index, column], f"{column} 不能为空") for index in frame.index[missing]]
    return result(check, issues, len(frame), int(missing.sum()), "空值检查", started)


@register("unique")
def unique(context, check):
    started = datetime.now(); frame = context[check["table"]]; columns = check["columns"]
    duplicated = frame.duplicated(subset=columns, keep=False)
    issues = [make_issue(check, int(index) + 2, "+".join(columns), " | ".join(str(frame.at[index, col]) for col in columns), f"唯一键重复：{'+'.join(columns)}") for index in frame.index[duplicated]]
    duplicate_rows = len(frame) - len(frame.drop_duplicates(subset=columns))
    return result(check, issues, len(frame), int(duplicate_rows), "唯一性检查", started)


@register("null_rate")
def null_rate(context, check):
    started = datetime.now(); frame = context[check["table"]]; max_rate = float(check["max_rate"])
    issues = []; null_count = 0
    for column in check["columns"]:
        missing = frame[column].isna() | (frame[column].astype(str).str.strip() == "")
        count = int(missing.sum()); null_count += count; rate = count / len(frame) if len(frame) else 0
        if rate > max_rate:
            issues.append(make_issue(check, column=column, message=f"{column} 空值率 {rate:.2%} 超过阈值 {max_rate:.2%}"))
    overall_rate = null_count / (len(frame) * max(1, len(check["columns"]))) if len(frame) else 0
    return result(check, issues, len(frame), overall_rate, "空值率检查", started)


@register("regex")
def regex(context, check):
    started = datetime.now(); frame = context[check["table"]]; column = check["column"]
    pattern = re.compile(check["pattern"]); values = frame[column].astype(str); invalid = ~values.str.match(pattern)
    if check.get("allow_null", True):
        invalid &= ~(frame[column].isna() | (values.str.strip() == ""))
    issues = [make_issue(check, int(index) + 2, column, frame.at[index, column], f"{column} 格式不符合规则") for index in frame.index[invalid]]
    return result(check, issues, len(frame), int(invalid.sum()), "格式检查", started)


@register("allowed_values")
def allowed_values(context, check):
    started = datetime.now(); frame = context[check["table"]]; column = check["column"]
    invalid = ~frame[column].isin(set(check["values"]))
    issues = [make_issue(check, int(index) + 2, column, frame.at[index, column], f"{column} 取值不在允许范围内") for index in frame.index[invalid]]
    return result(check, issues, len(frame), int(invalid.sum()), "枚举值检查", started)


@register("range")
def range_check(context, check):
    started = datetime.now(); frame = context[check["table"]]; column = check["column"]
    numeric = pd.to_numeric(frame[column], errors="coerce"); invalid = numeric.isna() if check.get("required", True) else pd.Series(False, index=frame.index)
    if "min" in check: invalid |= numeric < float(check["min"])
    if "max" in check: invalid |= numeric > float(check["max"])
    issues = [make_issue(check, int(index) + 2, column, frame.at[index, column], f"{column} 超出数值范围") for index in frame.index[invalid]]
    return result(check, issues, len(frame), int(invalid.sum()), "数值范围检查", started)


@register("date_not_after")
def date_not_after(context, check):
    started = datetime.now(); frame = context[check["table"]]; column = check["column"]
    as_of = pd.Timestamp(check["as_of_date"]); values = pd.to_datetime(frame[column], errors="coerce")
    invalid = values.isna() | (values > as_of)
    issues = [make_issue(check, int(index) + 2, column, frame.at[index, column], f"{column} 不是有效历史日期或晚于 {check['as_of_date']}") for index in frame.index[invalid]]
    return result(check, issues, len(frame), int(invalid.sum()), "日期有效性检查", started)


@register("referential_integrity")
def referential_integrity(context, check):
    started = datetime.now(); frame = context[check["table"]]; child = check["column"]
    parents = set(context[check["parent_table"]][check["parent_column"]].dropna().astype(str))
    invalid = ~frame[child].astype(str).isin(parents)
    issues = [make_issue(check, int(index) + 2, child, frame.at[index, child], f"{child} 在父表中不存在") for index in frame.index[invalid]]
    return result(check, issues, len(frame), int(invalid.sum()), "主外键完整性检查", started)


@register("cross_table_consistency")
def cross_table_consistency(context, check):
    started = datetime.now(); frame = context[check["table"]]; parent = context[check["parent_table"]]
    mapping = parent.drop_duplicates(check["parent_key_column"]).set_index(check["parent_key_column"])[check["parent_value_column"]]
    expected = frame[check["key_column"]].map(mapping)
    invalid = expected.notna() & (frame[check["value_column"]].astype(str) != expected.astype(str))
    issues = [make_issue(check, int(index) + 2, check["value_column"], frame.at[index, check["value_column"]], "字段值与父表不一致") for index in frame.index[invalid]]
    return result(check, issues, len(frame), int(invalid.sum()), "跨表一致性检查", started)


@register("freshness")
def freshness(context, check):
    started = datetime.now(); frame = context[check["table"]]; as_of = pd.Timestamp(check["as_of_date"])
    dates = pd.to_datetime(frame[check["column"]], errors="coerce"); historical = dates[dates <= as_of]
    if historical.empty:
        return result(check, [make_issue(check, column=check["column"], message="没有可用的历史日期")], len(frame), None, "数据新鲜度检查", started)
    latest = historical.max(); age_days = int((as_of - latest).days); issues = []
    if age_days > int(check["max_age_days"]):
        issues.append(make_issue(check, column=check["column"], value=latest.date().isoformat(), message=f"最新数据距今 {age_days} 天，超过 {check['max_age_days']} 天"))
    return result(check, issues, len(frame), age_days, "数据新鲜度检查", started)


@register("row_count")
def row_count(context, check):
    started = datetime.now(); frame = context[check["table"]]; count = len(frame); issues = []
    if "min" in check and count < int(check["min"]): issues.append(make_issue(check, message=f"记录数 {count} 小于最小值 {check['min']}"))
    if "max" in check and count > int(check["max"]): issues.append(make_issue(check, message=f"记录数 {count} 大于最大值 {check['max']}"))
    return result(check, issues, count, count, "记录数检查", started)