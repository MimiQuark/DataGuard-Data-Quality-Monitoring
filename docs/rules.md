# 规则与语义说明

## 支持规则

| 规则类型 | 用途 | 关键参数与语义 |
|---|---|---|
| `required_columns` | 检查必需字段 | `columns`；字段缺失时会产生问题，后续依赖该字段的规则会被隔离为失败检查，不会中断整次运行 |
| `not_null` | 检查字段非空 | `column`；`NaN`、空字符串和纯空白都算空 |
| `unique` | 检查唯一键重复 | `columns`；重复组内**每一行**都产生一条问题，`metric` 等于涉及重复的行数 |
| `null_rate` | 检查空值率 | `columns`, `max_rate`；按每个字段计算空值数 / 表行数，超过阈值产生问题 |
| `regex` | 检查字符串格式 | `column`, `pattern`, `allow_null`；使用**全字符串匹配**（`fullmatch`），不是前缀匹配；`allow_null` 默认 `true`，空值/空白不参与格式判断 |
| `allowed_values` | 检查枚举值 | `column`, `values`；值必须精确出现在 `values` 中，空值默认不合法 |
| `range` | 检查数值范围 | `column`, `min`, `max`, `required`；`required` 默认 `true`，非数字或空值视为不合法；`min`/`max` 可只配置一个 |
| `date_not_after` | 检查日期有效且不晚于基准日 | `column`, `as_of_date`；无法解析的日期和晚于基准日的日期都算问题；基准日按 check 配置 |
| `referential_integrity` | 检查主外键完整性 | `column`, `parent_table`, `parent_column`；父表空/空白键会被过滤，子表空/空白键或父表中不存在的键均算问题 |
| `cross_table_consistency` | 检查跨表字段一致 | `key_column`, `value_column`, `parent_table`, `parent_key_column`, `parent_value_column`；父键必须唯一，否则报告父表问题；子表键缺失或值不一致均产生问题 |
| `freshness` | 检查数据新鲜度 | `column`, `as_of_date`, `max_age_days`；取不晚于基准日的最新日期计算天数；没有历史日期会产生问题 |
| `row_count` | 检查记录数上下限 | `min`, `max`；至少配置一个边界，否则配置校验失败 |

## 严重等级与状态

- `high`：主键、外键、金额、日期等影响核心结果的问题。
- `medium`：格式、枚举、新鲜度等需要修正但通常不阻断分析的问题。
- `low`：提示性问题或后续优化项。

状态规则：

- 存在 `high` 问题且 `thresholds.fail_on_high = true`（默认）→ `failed`。
- `fail_on_high = false` 时，`high` 问题只产生 `warning`。
- 存在任何问题（包括 `low`）→ 至少为 `warning`，不会在检查失败时误报 `passed`。
- 任意检查执行失败（即使没有 issue）→ `failed`，不会误报 `passed`。
- 没有任何问题 → `passed`。

`severity` 只能是 `high` / `medium` / `low`，拼写错误会在配置校验阶段直接报错。

## 问题身份与闭环

`issue_key` 使用稳定字段生成：

```text
check_id | table | rule_type | column | row_key
```

- 行级问题优先使用数据源配置的 `primary_key` 值；没有主键时才退回行号。
- 聚合问题（空值率、记录数、新鲜度等）使用固定 aggregate 标识，**不把阈值/比率/日期差写进 key**。
- 动态指标只放在 `message` / `value` 中，不会因为指标轻微变化导致问题被误判为“已解决 + 新开”。

闭环范围：

- 只关闭“同项目 + 本次实际执行的 check_id”范围内、且本次未出现的旧问题。
- 使用部分配置运行（例如只跑 customers 或只跑 orders）不会关闭其他检查的问题。
- 这是自动按执行范围关闭，不是人工整改工作流；没有提供手动关闭/忽略 UI。

## 配置校验

启动时会校验：

- `sources` / `checks` 非空，数据源类型合法；
- check id 唯一，规则类型已注册；
- 表名、父表名存在；
- `severity` 合法；
- 规则必需字段存在；
- 正则可编译；
- `row_count` 至少有一个边界；
- 日期字段可解析；
- `thresholds` 类型正确。

配置错误会返回明确的 `ConfigError`，CLI 以退出码 2 退出，不输出原始 traceback。

## 相对路径

CSV 的 `path` 默认相对于 `config_path.parent.parent`（即项目根）；也可以在配置中设置 `base_dir` 覆盖。`--config` 指向其他位置时，建议显式设置 `base_dir`。

## CSV 导出安全

`issues.csv` 会对以 `= + - @ 制表符 回车` 开头的值加前缀 `'`，防止在 Excel 中被当作公式执行；HTML 输出使用转义。

## MySQL

MySQL 数据源需要 `pip install ".[mysql]"`，并且需要自行准备 schema/表。当前 CI 只验证 CSV 路径；MySQL 路径和 dtype 差异未在 CI 中验证。
