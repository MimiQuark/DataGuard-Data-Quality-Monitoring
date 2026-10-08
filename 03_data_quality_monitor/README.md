# 通用数据质量监控工具

这是一个面向数据专员、数据分析师和数据治理岗位的可配置数据质量监控项目。工具读取 CSV 或 MySQL 数据源，按 JSON 规则执行质量检查，生成问题清单、HTML 报告和 SQLite 历史趋势记录。

## 功能

- 空值检查与空值率阈值。
- 主键非空和重复值检查。
- 邮箱等字段格式检查。
- 枚举值和数值范围检查。
- 日期有效性和数据新鲜度检查。
- 主外键完整性检查。
- 跨表字段一致性检查。
- 记录数上下限检查。
- 问题等级、问题明细和未关闭问题跟踪。
- SQLite 运行历史、首次出现和最近出现记录。
- 可选 Webhook 告警。

## 目录

```text
config/rules.json              规则、数据源和阈值配置
data/raw/                      带已知异常的样例数据
src/sample_data_generator.py   固定种子样例数据生成
src/engine.py                  数据加载与规则调度
src/rules.py                   规则实现和注册表
src/storage.py                 SQLite 历史和问题生命周期
src/report.py                  HTML、CSV 和 JSON 输出
src/alerts.py                  Webhook 告警
src/cli.py                    命令行入口
tests/test_monitor.py          引擎、规则、存储和报告测试
output/                        报告、问题清单和历史库
```

## 运行

```powershell
$env:PYTHON_EXE = "C:\path\to\python.exe"
.\run.ps1
```

直接运行并允许高严重度问题返回退出码 1：

```powershell
python src\cli.py --config config\rules.json --output-dir output --db output\dq_history.sqlite
```

## 输出

- `output/dq_report.html`：可视化质量报告。
- `output/issues.csv`：问题明细，可直接分派处理。
- `output/run_summary.json`：完整运行摘要、检查结果和数据源统计。
- `output/dq_history.sqlite`：运行历史、问题历史和闭环状态。

## 验证结果

- 数据表：3 张。
- 检查项：28 项。
- 通过：8 项。
- 失败：20 项。
- 问题：35 个，其中高严重度 31 个、中严重度 4 个。
- 单元测试：4/4 通过。

样例数据故意包含空主键、重复主键、错误邮箱、未来日期、无效外键、负数量、负价格、折扣越界、错误区域和错误枚举值，用于验证各规则能真实发现问题。