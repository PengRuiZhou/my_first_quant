# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A股量化交易框架，包含四大模块：
- **数据支撑**：Tushare/AKShare 数据源，PostgreSQL 存储
- **策略**：Verses 因子库 → Lanetech 模型 → Alpha → 优化器
- **回测**：因子/策略回测，IC/Sharpe/回撤等指标
- **交易**：订单管理、券商接口、风控

## Tech Stack

| 组件 | 技术 |
|------|------|
| 操作系统 | macOS (Apple Silicon M5 Pro) |
| Python 环境 | Conda: `/opt/miniconda3/envs/peng` (Python 3.12.12) |
| 语言 | Python 主体 + Rust/C++ 性能模块 |
| 数据源 | Tushare / AKShare |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 (async) |
| 数据频率 | 日线级别 |
| 目标市场 | A 股 |

### 核心依赖

| 类别 | 库 | 版本 | 用途 |
|------|-----|------|------|
| **数据处理** | pandas | 3.0.1 | 数据框架 |
| | numpy | 2.4.3 | 数值计算 |
| | scipy | 1.17.1 | 科学计算（缩尾处理等） |
| **数据源** | tushare | 1.4.25 | A股数据 API |
| | akshare | 1.18.43 | A股数据 API（备用） |
| **数据库** | sqlalchemy | 2.0.48 | ORM（async） |
| | asyncpg | 0.31.0 | 异步 PostgreSQL 驱动 |
| | psycopg2 | 2.9.9 | PostgreSQL 同步驱动 |
| **配置/日志** | pydantic-settings | 2.8.0 | 配置管理 |
| | loguru | 0.7.2 | 日志 |
| **CLI** | typer | 0.15.1 | CLI 框架 |
| | rich | 13.9.4 | 终端美化 |
| **调度** | apscheduler | 3.11.0 | 定时任务 |
| **ML** | scikit-learn | 1.8.0 | 传统 ML |
| | lightgbm | 4.6.0 | GBDT |
| | xgboost | 3.2.0 | GBDT |
| **DL** | torch | 2.10.0 | 深度学习（MPS 可用） |
| **RL** | stable-baselines3 | 2.6.0 | 强化学习 |
| **开发** | pytest | 9.0.2 | 测试 |
| | black | 26.3.1 | 格式化 |
| | ruff | 0.9.7 | Lint |
| | mypy | 1.15.0 | 类型检查 |
| **可视化** | matplotlib | 3.10.8 | 绑图 |
| | seaborn | 0.13.2 | 统计可视化 |
| | plotly | 6.6.0 | 交互式图表 |

### 架构组件

| 模块 | 实现状态 | 关键文件 |
|------|----------|----------|
| **数据源层** | ✅ 完成 | `quant/data/sources/` - Tushare/AKShare 适配器 + 交叉验证 |
| **ETL 清洗层** | ✅ 完成 | `quant/data/etl/` - 缺失值/异常值/复权/状态过滤/管道 |
| **存储层** | ✅ 完成 | `quant/data/storage/` - DataRepository + DataScheduler |
| **数据模型** | ✅ 完成 | `quant/data/models/` - 11 个 SQLAlchemy 模型 |
| **配置系统** | ✅ 完成 | `quant/core/config.py` - pydantic-settings + URL 编码 |
| **CLI 工具** | ✅ 完成 | `quant/cli/` - typer + rich (fetch/scheduler/init-data) |
| **开发环境** | ✅ 完成 | PostgreSQL 15 + asyncpg + .env 配置 |

## Core Concepts

### Verses（因子）
```
Verse = Operator(Data)
例：quantile(市值), ts_mean(close, 20), group_rank(ROE, 行业)
```

### Lanetech（模型）
- 输入：多个 Verses（features）
- 输出：Alpha 向量（残差收益预测）
- 类型：传统ML / 深度学习 / 强化学习

### 优化器
- 输入：Alpha + Universe + Constraints
- 输出：目标仓位
- 方法：MVO, QP, 风险平价

## Module Structure

```
my_first_quant/              # 项目根目录
├── quant/                   # Python 包
│   ├── data/                # 数据支撑模块
│   │   ├── sources/         # 数据源适配器（Tushare/AKShare）
│   │   ├── etl/             # 数据清洗 ETL Pipeline
│   │   ├── storage/         # 存储层（Repository + Scheduler）
│   │   └── models/          # 数据模型（SQLAlchemy）
│   ├── strategy/            # 策略模块
│   │   ├── verses/          # 因子库
│   │   ├── lanetech/        # 模型集合
│   │   ├── alpha/           # Alpha 生成
│   │   └── optimizer/       # 优化器
│   ├── backtest/            # 回测模块
│   │   ├── engine/          # 回测引擎
│   │   └── metrics/         # 评估指标
│   ├── execution/           # 交易模块
│   │   ├── orders/          # 订单管理
│   │   ├── brokers/         # 券商接口
│   │   └── risk/            # 风控
│   ├── core/                # 核心工具
│   │   ├── config.py        # 配置管理（pydantic-settings）
│   │   └── logging.py       # 日志配置（loguru）
│   └── cli/                 # 命令行接口（typer）
│       ├── __init__.py      # 主入口，注册所有命令
│       ├── fetch.py         # fetch 命令（数据获取）
│       ├── scheduler.py     # scheduler 命令（调度器管理）
│       ├── db.py            # db 命令（数据库操作）
│       ├── init_data.py     # init-data 命令
│       └── backtest.py      # backtest 命令（待实现）
├── tests/                   # 测试
├── docs/                    # 文档
│   └── superpowers/specs/   # 设计文档
├── Makefile                 # 常用命令
└── pyproject.toml           # 依赖管理
```

## Development Workflow

1. **规划文件**：task_plan.md, findings.md, progress.md
2. **分支策略**：feature/* 分支开发，完成后合并
3. **测试**：每个模块编写单元测试

## Build Commands

```bash
# 安装
pip install -e ".[dev]"     # 开发模式
pip install -e ".[all]"     # 包含所有可选依赖

# 测试
pytest                      # 运行测试
pytest --cov=quant          # 带覆盖率

# 代码质量
black .                     # 格式化
ruff check .                # lint
mypy quant                  # 类型检查

# 数据库
quant db create             # 创建表
quant db drop               # 删除表

# Makefile 快捷命令
make test                   # 运行测试
make lint                   # lint 检查
make format                 # 格式化
```

## Data Source Notes

**Tushare vs AKShare**：
- Tushare 使用 REST API，需要配置 Token
- AKShare 使用直接函数调用，无需 Token
- 两者都是同步 API，使用 `asyncio.run_in_executor` 包装为异步
- AKShare 接口名可能变化，使用 `getattr` 动态调用

**Tushare 自定义 API**：
- 支持 `TUSHARE_API_URL` 配置自定义 API 地址（如 lianghua 镜像）
- 使用 `setattr(pro, "_DataApi__http_url", url)` 设置私有属性

**Pylance 类型提示**：
- AKShare 无完整类型存根，部分警告可忽略
- 使用 `getattr(ak, "func_name", None)` 动态调用避免类型错误
- 使用 `setattr()` 设置私有属性避免类型警告

## CLI Commands

```bash
quant version              # 显示版本
quant init                 # 初始化配置（创建.env）
quant db create            # 创建数据库表
quant db drop              # 删除数据库表

# 数据获取
quant fetch stock_list     # 获取股票列表
quant fetch index_list     # 获取指数列表
quant fetch daily          # 获取日线数据
quant fetch index          # 获取指数行情
quant fetch basic          # 获取每日指标
quant fetch calendar       # 获取交易日历
quant fetch financial      # 获取财务指标（所有股票）
quant fetch financial --ts-code 000001.SZ  # 获取指定股票的财务指标
quant fetch financial --max-workers 10      # 使用10个并行线程获取
quant fetch all -s 20230101 -e 20231231  # 批量更新所有数据（指定日期范围）
quant fetch all -s 20230101 -e 20231231 --max-workers 8  # 批量更新并指定并行度
quant fetch daily -s 20230101 -e 20231231  # 指定日期范围

# 调度器
quant scheduler list       # 列出所有任务
quant scheduler start      # 启动调度器（后台）
quant scheduler status     # 查看调度状态
quant scheduler run -j update_daily_quotes  # 手动运行任务
quant scheduler stop       # 停止调度器
# 日志文件: .quant/scheduler/scheduler.log

# 初始化数据
quant init-data --years 3  # 初始化3年历史数据（含财务指标）

quant backtest <strategy>  # 运行回测
```

## Known Limitations

**adj_factor（复权因子）未入库**：
- 当前 TushareClient 有 `get_adj_factor()` 方法，但复权因子数据未持久化到数据库
- ETL 层的 `PriceAdjuster` 可实时计算复权价格
- **潜在风险**：增量更新时复权可能不精确（历史因子可能因分红/拆股而变化）
- **后续方案**：如需精确增量复权，可添加 `AdjFactor` 模型和入库逻辑

## Key Files

- [task_plan.md](task_plan.md) - 任务计划和阶段跟踪
- [findings.md](findings.md) - 需求和技术发现
- [progress.md](progress.md) - 进度日志
- [docs/superpowers/specs/](docs/superpowers/specs/) - 设计文档目录
  - [2026-03-22-data-module-design.md](docs/superpowers/specs/2026-03-22-data-module-design.md) - Stage 3 数据模块设计
  - [2026-03-25-cli-refactor-design.md](docs/superpowers/specs/2026-03-25-cli-refactor-design.md) - CLI 模块化重构设计 ✅
- [quant/cli/](quant/cli/) - CLI 模块目录
  - [__init__.py](quant/cli/__init__.py) - 主入口
  - [scheduler.py](quant/cli/scheduler.py) - 调度器命令
  - [fetch.py](quant/cli/fetch.py) - 数据获取命令
- [docs/superpowers/plans/](docs/superpowers/plans/) - 实现计划目录
  - [2026-03-22-stage3-implementation.md](docs/superpowers/plans/2026-03-22-stage3-implementation.md) - Stage 3 实现计划
