# 规则说明

## 支持规则

| 规则类型 | 用途 | 关键参数 |
|---|---|---|
| `required_columns` | 检查必需字段 | `columns` |
| `not_null` | 检查字段非空 | `column` |
| `unique` | 检查唯一键重复 | `columns` |
| `null_rate` | 检查空值率 | `columns`, `max_rate` |
| `regex` | 检查字符串格式 | `column`, `pattern`, `allow_null` |
| `allowed_values` | 检查枚举值 | `column`, `values` |
| `range` | 检查数值上下限和数值类型 | `column`, `min`, `max` |
| `date_not_after` | 检查日期有效且不晚于基准日 | `column`, `as_of_date` |
| `referential_integrity` | 检查主外键完整性 | 子表字段、父表字段 |
| `cross_table_consistency` | 检查跨表字段一致 | 关联键和比较字段 |
| `freshness` | 检查数据新鲜度 | `as_of_date`, `max_age_days` |
| `row_count` | 检查记录数上下限 | `min`, `max` |

## 严重等级

- `high`：主键、外键、金额、日期等会影响核心分析结果的问题。
- `medium`：格式、枚举、数据新鲜度等需要修正但通常不直接阻断分析的问题。
- `low`：提示性问题或后续优化项。

当存在 `high` 问题时，运行状态为 `failed`；只有 `medium` 时为 `warning`；没有问题时为 `passed`。

## 问题闭环

每个问题使用 `issue_key` 唯一标识。运行时：

1. 新问题写入 `issue_registry`，状态为 `open`。
2. 再次出现时更新 `last_seen` 和出现次数。
3. 本次未出现且此前为 `open` 的问题自动标记为 `resolved`。
4. 所有运行和问题明细保留在 SQLite 中，便于趋势分析和复盘。