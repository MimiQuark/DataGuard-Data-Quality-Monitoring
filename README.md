# DataGuard：数据质量监控与闭环治理

> 用可配置的规则发现数据缺陷，并把问题跟踪到关闭，输出可复核的报告。

## 项目定位

数据进入下游之前需要一道可复核的关卡。本项目把「检查什么、怎么判、发现问题后如何闭环」
做成可配置的规则集，面向 CSV 与 MySQL 两类数据源，用同一套引擎执行检查、留痕并出报告。

## 核心能力

- **12 类规则 / 28 项检查** —— 覆盖完整性、唯一性、一致性、有效性等维度，规则集中在 `config/rules.json`，改配置即可增删检查项。
- **检出能力可验证** —— 样例数据中刻意注入 35 个已知缺陷，用来验证每条规则确实生效，而不是"跑通即通过"。
- **闭环治理** —— 检查结果落 SQLite，记录问题从发现到关闭的状态流转，避免每次全量重报。
- **三种报告** —— HTML（可读）、CSV（可分析）、JSON（可对接下游）。
- **两类数据源共用一套规则** —— 数据源差异收敛在接口层，业务规则不重复实现。
- **自动化测试** —— 4 项测试全部通过。

## 项目内容导航

| 路径 | 内容 |
|---|---|
| `03_data_quality_monitor/src/rules.py` | 12 类规则的定义与判定逻辑 |
| `03_data_quality_monitor/src/engine.py` | 检查执行引擎 |
| `03_data_quality_monitor/src/storage.py` | SQLite 历史与问题闭环 |
| `03_data_quality_monitor/src/report.py` | HTML / CSV / JSON 报告输出 |
| `03_data_quality_monitor/config/rules.json` | 规则配置 |
| `03_data_quality_monitor/docs/rules.md` | 规则说明 |
| `docs/index.html` | 报告示例 |

## 环境安装

```powershell
pip install -r 03_data_quality_monitor/requirements.txt
```

## 快速开始

```powershell
.\03_data_quality_monitor\run.ps1
```

运行后会生成带已知缺陷的样例数据、执行全部检查，并把报告写到输出目录。

## 项目结构

```
03_data_quality_monitor/
├── config/      规则与数据源配置
├── docs/        规则说明与实施计划
├── src/         引擎 / 规则 / 存储 / 报告 / CLI
├── tests/       自动化测试
└── run.ps1      一键运行
docs/            报告示例（HTML / CSV / JSON）
```

## 说明与边界

样例数据是**按已知缺陷构造**的，因此「35 个缺陷全部检出」验证的是规则是否生效，
**不代表在真实数据上的召回率**。
