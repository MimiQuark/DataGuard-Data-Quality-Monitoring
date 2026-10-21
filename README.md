# DataGuard：数据质量监控与闭环治理

[![CI](https://github.com/MimiQuark/DataGuard-Data-Quality-Monitoring/actions/workflows/ci.yml/badge.svg)](https://github.com/MimiQuark/DataGuard-Data-Quality-Monitoring/actions/workflows/ci.yml)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717?logo=github&logoColor=white)](https://github.com/MimiQuark/DataGuard-Data-Quality-Monitoring)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![pandas](https://img.shields.io/badge/pandas-2.2%2B-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![SQLite](https://img.shields.io/badge/SQLite-history-003B57?logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

DataGuard 是一套可配置的数据质量监控工具：读取 CSV 或 MySQL 数据源，按 JSON 规则执行检查，输出 HTML / CSV / JSON 报告，并用 SQLite 记录运行历史、问题首次出现时间和闭环状态。

> 12 类规则 / 28 项检查 · HTML / CSV / JSON 报告 · SQLite 问题闭环 · 17 项自动化测试

## 项目定位

数据进入下游之前需要一道可复核的关卡。DataGuard 把“检查什么、怎么判、发现问题后如何跟踪”做成配置：

- 规则、阈值、严重等级写在 `config/rules.json`，改配置即可增删检查。
- 检查结果落 SQLite：保留运行历史、问题首次/最近出现时间和 resolved 状态。
- 一次运行同时产出可读 HTML、可分析 CSV 和可对接 JSON。
- 样例数据刻意注入 20 处缺陷，产生 35 条 issue 记录（不是 35 个独立缺陷），用于验证规则确实生效。

## 架构

```text
config/rules.json
      |
      v
engine.py  --->  rules.py（12 类规则注册表）
      |                 |
      |                 v
      |            models.py（Issue / CheckResult / RunSummary）
      v
storage.py（SQLite 历史 + 问题生命周期）   report.py（HTML / CSV / JSON）
      |                                         |
      +-----------------> cli.py <---------------+
                              |
                              v
                       alerts.py（可选 Webhook）
```

- **engine**：加载数据源、校验配置、执行规则、隔离单条规则异常、计算状态。
- **rules**：12 类规则，统一返回 `CheckResult` 和 `Issue`。
- **storage**：稳定 `issue_key`、项目/检查范围闭环、历史趋势。
- **report**：HTML 报告、CSV 问题清单（防公式注入）、JSON 摘要。
- **cli**：`python -m dataguard` / `dataguard` 命令入口。

## 快速开始

环境：Python 3.11+，pandas 2.2+。MySQL 为可选依赖。

```powershell
python -m pip install -e ".[dev]"
.\run.ps1
```

`run.ps1` 会依次生成样例数据、执行全部检查、写报告和 SQLite，并运行测试。也可以分步执行：

```powershell
python -m dataguard.sample_data_generator
python -m dataguard --config config\rules.json --output-dir output --db output\dq_history.sqlite --no-fail
python -m pytest -q
```

默认配置在 `config/rules.json`；MySQL 示例在 `config/mysql.example.json`，需要先安装：

```powershell
python -m pip install -e ".[mysql]"
```

## 样例验证结果

当前 `config/rules.json` 对样例数据的实测：

| 项 | 数值 |
|---|---:|
| 规则类型 | 12 |
| 检查项 | 28 |
| 通过 / 失败 | 8 / 20 |
| issue 记录 | 35 |
| high / medium / low | 31 / 4 / 0 |
| 自动化测试 | 14 |

样例数据包含 20 处刻意注入的异常（客户 6、商品 4、订单 10）；35 是级联和重复计数后的 issue 记录数。一次空主键会造成多条订单外键问题，一组重复键会按行产生多条 issue，因此不能把 35 当成 35 个独立的人工缺陷。

## 输出

| 文件 | 内容 |
|---|---|
| `output/dq_report.html` | 可独立打开的可视化报告 |
| `output/issues.csv` | 问题明细，可直接分派处理 |
| `output/run_summary.json` | 完整运行摘要、检查结果与数据源统计 |
| `output/dq_history.sqlite` | 运行历史、问题历史与闭环状态 |

## 项目结构

```text
.
├── config/
│   ├── rules.json
│   └── mysql.example.json
├── src/dataguard/
│   ├── __main__.py / cli.py
│   ├── engine.py / rules.py / models.py
│   ├── storage.py / report.py / alerts.py
│   └── sample_data_generator.py
├── tests/
│   ├── fixtures.py
│   ├── test_engine.py
│   ├── test_storage.py
│   ├── test_report.py
│   └── test_cli.py
├── docs/
│   ├── rules.md          # 规则参数与语义
│   ├── PROJECT_PLAN.md   # 验收清单
│   └── index.html        # 报告示例 / Pages
├── pyproject.toml
├── requirements.txt
└── run.ps1
```

## 规则与闭环

完整语义见 [docs/rules.md](docs/rules.md)。几个容易误解的点：

- `regex` 使用**全字符串匹配**（`fullmatch`），不是前缀匹配。
- `unique` 的 `metric` 是涉及重复的行数，与 issue 行数一致。
- 问题 key 使用 `check_id + table + rule_type + column + primary_key`；动态比率/日期差只放在 message 里，不会因为指标轻微变化而误关闭/重开。
- 闭环只关闭“同项目 + 本次实际执行的 check_id”范围内的问题；部分配置运行不会关闭其他检查的旧问题。
- 没有人工关闭/忽略 UI；“闭环”指自动按执行范围更新状态。

## 测试与 CI

```powershell
python -m pytest -q
```

17 项测试覆盖：基线 28 项检查、35 条 issue、缺列不崩溃、配置校验、状态策略、唯一键指标、regex 全匹配、空外键、issue key 稳定、部分配置不误关、二次运行 resolved、severity 排序、CSV 公式注入、趋势标签和 CLI 退出码。

CI 在 Python 3.11 上安装项目、生成临时 fixture、运行 pytest 和 `python -m dataguard --help`。

## 说明与边界

- 样例数据是**按已知异常构造**的；35 条 issue 验证的是规则能发现问题，不代表真实数据上的召回率。
- MySQL 分支需要 PyMySQL 和真实 schema；当前 CI 只验证 CSV 路径，MySQL 未在 CI 中验证。
- 闭环是自动按本次执行范围关闭，不是完整的人工整改工作流。
- 报告中的行号对 CSV 是“数据行 + 2”（含表头）的展示行号；MySQL 行号不作为稳定业务标识。

## License

MIT。见 [LICENSE](LICENSE)。
