# My First Quant

A股量化交易框架，支持因子研究、策略回测和实盘交易。

## 特性

- **数据支撑**：Tushare/AKShare 数据源，PostgreSQL 存储
- **策略模块**：Verses 因子库 → Lanetech 模型 → Alpha → 优化器
- **回测系统**：因子/策略回测，IC/Sharpe/回撤等指标
- **交易执行**：订单管理、券商接口、风控

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

### 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 填写配置
# 必须配置：
# - DB_* 数据库连接
# - TUSHARE_TOKEN Tushare API Token
```

### 初始化数据库

```bash
quant db create
```

## 项目结构

```
my_first_quant/              # 项目根目录
├── quant/                   # Python 包
│   ├── data/                # 数据支撑模块
│   │   ├── sources/         # 数据源适配器
│   │   ├── etl/             # 数据清洗
│   │   └── models/          # 数据库模型
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
│   │   ├── config.py        # 配置管理
│   │   └── logging.py       # 日志配置
│   └── cli.py               # 命令行接口
├── tests/                   # 测试
├── pyproject.toml           # 依赖管理
└── README.md
```

## 使用示例

```python
from quant.core import get_settings, setup_logging
from quant.data.models import StockInfo, DailyQuote, get_engine
from sqlalchemy.orm import Session

# 初始化
setup_logging()
settings = get_settings()

# 使用数据库
engine = get_engine(settings.db.url)
with Session(engine) as session:
    stocks = session.query(StockInfo).limit(10).all()
    for stock in stocks:
        print(stock.ts_code, stock.name)
```

## 命令行工具

```bash
quant version              # 显示版本
quant init                 # 初始化配置
quant db create            # 创建数据库表
quant fetch tushare daily  # 获取日线数据
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
