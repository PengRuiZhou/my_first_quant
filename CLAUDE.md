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
| Python 环境 | Conda: `/opt/miniconda3/envs/peng` |
| 语言 | Python 主体 + Rust/C++ 性能模块 |
| 数据源 | Tushare / AKShare |
| 数据库 | PostgreSQL |
| 数据频率 | 日线级别 |
| 目标市场 | A 股 |

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
│   └── cli.py               # 命令行接口（typer）
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

## CLI Commands

```bash
quant version              # 显示版本
quant init                 # 初始化配置（创建.env）
quant db create            # 创建数据库表
quant db drop              # 删除数据库表

# 数据获取（Stage 3 新增）
quant fetch stock_list     # 获取股票列表
quant fetch daily          # 获取日线数据
quant fetch index          # 获取指数行情
quant fetch basic          # 获取每日指标
quant fetch calendar       # 获取交易日历

# 调度器（Stage 3 新增）
quant scheduler start      # 启动调度器
quant scheduler stop       # 停止调度器
quant scheduler status     # 查看调度状态

# 初始化数据（Stage 3 新增）
quant init-data --years 3  # 初始化3年历史数据

quant backtest <strategy>  # 运行回测
```

## Key Files

- [task_plan.md](task_plan.md) - 任务计划和阶段跟踪
- [findings.md](findings.md) - 需求和技术发现
- [progress.md](progress.md) - 进度日志
- [docs/superpowers/specs/](docs/superpowers/specs/) - 设计文档目录
  - [2026-03-22-data-module-design.md](docs/superpowers/specs/2026-03-22-data-module-design.md) - Stage 3 数据模块设计
