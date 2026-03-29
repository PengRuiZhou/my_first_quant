# My First Quant

A股量化交易框架，支持因子研究、策略回测和实盘交易。

## 特性

- **数据支撑** ✅：Tushare/AKShare 数据源，PostgreSQL 存储，ETL 清洗，定时调度
- **策略模块**：Verses 因子库 → Lanetech 模型 → Alpha → 优化器
- **回测系统**：因子/策略回测，IC/Sharpe/回撤等指标
- **交易执行**：订单管理、券商接口、风控

## 开发进度

| 阶段 | 模块 | 状态 |
|------|------|------|
| Stage 1 | 需求与探索 | ✅ 完成 |
| Stage 2 | 项目骨架搭建 | ✅ 完成 |
| Stage 3 | 数据支撑模块 | ✅ 完成 |
| Stage 4 | 策略模块 | 🚧 待开发 |
| Stage 5 | 回测模块 | 📋 计划中 |
| Stage 6 | 交易模块 | 📋 计划中 |
| Stage 7 | 集成与测试 | 📋 计划中 |

## 环境信息

| 项目 | 配置 |
|------|------|
| 操作系统 | macOS (Apple Silicon M5 Pro) |
| Python 环境 | Conda: `/opt/miniconda3/envs/peng` |
| Python 版本 | 3.12.12 |
| 数据库 | PostgreSQL >= 13 |

## 快速开始

### 环境配置

```bash
# 激活 Conda 环境
conda activate peng

# 进入项目目录
cd /Users/peng/my_first_quant

# 安装依赖
pip install -e ".[dev]"     # 开发模式（推荐）
# 或
pip install -e ".[all]"     # 包含所有可选依赖（ML/DL/RL）

# 安装异步 PostgreSQL 驱动
pip install asyncpg

# VSCode 配置
# Cmd+Shift+P -> Python: Select Interpreter
# 选择: /opt/miniconda3/envs/peng/bin/python
```

### 依赖说明

| 安装选项 | 包含内容 |
|---------|---------|
| `pip install -e .` | 核心依赖（pandas, numpy, sqlalchemy, tushare...） |
| `pip install -e ".[dev]"` | 核心 + 开发工具（pytest, black, ruff, mypy） |
| `pip install -e ".[ml]"` | 核心 + 机器学习（scikit-learn, lightgbm, xgboost） |
| `pip install -e ".[dl]"` | 核心 + 深度学习（torch） |
| `pip install -e ".[rl]"` | 核心 + 强化学习（stable-baselines3） |
| `pip install -e ".[viz]"` | 核心 + 可视化（matplotlib, seaborn, plotly） |
| `pip install -e ".[all]"` | 所有依赖 |

> **M5 Pro 注意事项**：
> - PyTorch 等库使用 Apple Silicon 原生版本以获得最佳性能
> - LightGBM 需要设置环境变量：`export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"`
> - 建议将上述环境变量添加到 `~/.zshrc` 中

### PostgreSQL 安装

**macOS (Homebrew)**：
```bash
# 安装 PostgreSQL 15
brew install postgresql@15

# 启动服务
brew services start postgresql@15

# 创建数据库
createdb quant

# 设置用户密码（可选）
psql -d quant -c "ALTER USER $(whoami) WITH PASSWORD 'your_password';"
```

**Docker**：
```bash
docker run --name quant-postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=quant \
  -p 5432:5432 \
  -d postgres:15
```

### 配置

```bash
# 创建配置文件
quant init

# 编辑 .env 填写配置
```

**`.env` 配置项**：

```bash
# 数据库配置（必填）
DB_HOST=localhost
DB_PORT=5432
DB_USER=peng                    # macOS Homebrew 默认使用系统用户名
DB_PASSWORD=your_password
DB_DATABASE=quant

# Tushare 配置（必填）
TUSHARE_TOKEN=your_token        # 从 https://tushare.pro 获取
TUSHARE_API_URL=http://api.tushare.pro  # 可选：自定义 API 地址

# 可选配置
ENV=development
DEBUG=false
LOG_LEVEL=INFO
```

> **Tushare Token**：访问 https://tushare.pro/register 注册并获取 Token

### 初始化数据库

```bash
# 创建数据库表
quant db create

# 验证表创建
psql -d quant -c "\dt"
```

## 项目结构

```
my_first_quant/              # 项目根目录
├── quant/                   # Python 包
│   ├── data/                # 数据支撑模块 ✅
│   │   ├── sources/         # 数据源适配器（Tushare/AKShare）
│   │   ├── etl/             # 数据清洗 ETL Pipeline
│   │   ├── storage/         # 存储层（Repository + Scheduler）
│   │   └── models/          # 数据库模型（11 个表）
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
│   ├── core/                # 核心工具 ✅
│   │   ├── config.py        # 配置管理（pydantic-settings）
│   │   └── logging.py       # 日志配置（loguru）
│   └── cli/                 # 命令行接口 ✅
│       ├── __init__.py      # 主入口
│       ├── console.py       # 共享 Console
│       ├── fetch.py         # 数据获取
│       ├── scheduler.py     # 调度器管理
│       ├── db.py            # 数据库操作
│       └── init_data.py     # 历史数据初始化
├── .quant/                  # 运行时文件（gitignore）
│   └── scheduler/           # 调度器运行时文件
│       ├── scheduler.pid    # 进程 ID
│       ├── scheduler.log    # 日志文件
│       └── runner.py        # 运行脚本
├── tests/                   # 测试（151 个测试用例）
├── docs/                    # 文档
│   └── superpowers/         # 设计文档和实现计划
├── pyproject.toml           # 依赖管理
├── .env                     # 环境配置（不提交）
├── .env.example             # 配置模板
└── README.md
```

## 使用示例

### 数据获取

```bash
# 获取股票列表
quant fetch stock_list

# 获取指数列表
quant fetch index_list

# 获取指定日期范围的日线数据
quant fetch daily -s 20230101 -e 20231231

# 批量更新所有数据类型（含财务指标并行获取）
quant fetch all -s 20230101 -e 20231231
quant fetch all -s 20230101 -e 20231231 --max-workers 8  # 指定并行度

# 初始化3年历史数据（首次使用，含财务指标）
quant init-data --years 3
```

### Python API

```python
import asyncio
from quant.data.sources.tushare_client import TushareClient
from quant.data.storage.repository import DataRepository
from quant.data.etl.pipeline import create_minimal_pipeline

async def main():
    # 初始化
    client = TushareClient()
    repo = DataRepository()

    # 获取股票列表
    stocks = await client.get_stock_list()
    print(f"获取到 {len(stocks)} 只股票")

    # 获取日线行情
    quotes = await client.get_daily_quotes(
        start_date="20230101",
        end_date="20231231"
    )

    # ETL 清洗
    pipeline = create_minimal_pipeline()
    clean_quotes = pipeline.run(quotes)

    # 存储到数据库
    count = await repo.upsert_daily_quotes(clean_quotes)
    print(f"插入 {count} 条记录")

asyncio.run(main())
```

## 命令行工具

```bash
# 基础命令
quant version              # 显示版本
quant init                 # 初始化配置
quant db create            # 创建数据库表
quant db drop              # 删除数据库表

# 数据获取
quant fetch stock_list     # 获取股票列表
quant fetch index_list     # 获取指数列表
quant fetch daily          # 获取日线数据
quant fetch index          # 获取指数行情
quant fetch basic          # 获取每日指标
quant fetch calendar       # 获取交易日历
quant fetch financial      # 获取财务指标（所有股票，20线程并行）
quant fetch financial --ts-code 000001.SZ  # 获取指定股票的财务指标
quant fetch financial --max-workers 10     # 使用10个并行线程获取
quant fetch all -s 20230101 -e 20231231  # 批量更新所有数据（指定日期范围）
quant fetch all -s 20230101 -e 20231231 --max-workers 8  # 批量更新并指定并行度
quant fetch daily -s 20230101 -e 20231231  # 指定日期范围

# 调度器管理
quant scheduler list       # 列出所有定时任务
quant scheduler start      # 启动调度器（后台运行）
quant scheduler status     # 查看运行状态和最近日志
quant scheduler run -j update_daily_quotes  # 手动运行任务
quant scheduler stop       # 停止调度器
# 日志文件位于: .quant/scheduler/scheduler.log

# 初始化历史数据（含财务指标）
quant init-data --years 3  # 初始化3年历史数据

# 回测
quant backtest my_strategy # 运行回测
```

## 开发

```bash
# 运行测试
pytest

# 代码格式化
black .

# 代码检查
ruff check .

# 类型检查
mypy quant
```

## 许可证

MIT License
