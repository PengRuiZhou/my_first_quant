# 任务计划：量化交易框架搭建

## 目标

构建一整套 A 股量化交易框架，包含策略、交易、数据支撑、回测四大模块，支持因子研究、模型训练、策略回测和实盘交易。

## 当前阶段

阶段 1（完成）→ 阶段 2（完成）→ 阶段 3（完成）→ 阶段 4（待开始）

## 项目规格

| 维度 | 选择 |
|------|------|
| 目标市场 | A 股（沪深两市） |
| 数据频率 | 日线级别 |
| 数据源 | Tushare / AKShare |
| 存储 | PostgreSQL |
| 开发语言 | Python 主体 + Rust/C++ 性能模块 |
| 目标 | 研究 + 实盘 |

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        量化交易框架                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    模块3: 数据支撑 (Data)                    │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │ 数据源接口   │  │ 数据清洗     │  │ PostgreSQL   │      │   │
│  │  │ Tushare/     │  │ ETL Pipeline │  │ 数据存储     │      │   │
│  │  │ AKShare      │  │              │  │              │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    模块1: 策略 (Strategy)                    │   │
│  │                                                              │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │   │
│  │  │ Verses因子库 │ →  │ Lanetech模型 │ →  │ Alpha向量    │  │   │
│  │  │              │    │              │    │              │  │   │
│  │  │ Operator+    │    │ ML/RL模型    │    │ 残差收益预测 │  │   │
│  │  │ Data组合     │    │ 集合         │    │              │  │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘  │   │
│  │                              ↓                               │   │
│  │                    ┌──────────────┐                         │   │
│  │                    │ 优化器       │                         │   │
│  │                    │              │                         │   │
│  │                    │ Alpha +      │                         │   │
│  │                    │ Universe +   │                         │   │
│  │                    │ Constraints  │                         │   │
│  │                    │ ↓            │                         │   │
│  │                    │ 目标仓位     │                         │   │
│  │                    └──────────────┘                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    模块2: 交易 (Execution)                   │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │   │
│  │  │ 订单管理     │ →  │ 券商接口     │ →  │ 成交确认     │  │   │
│  │  │ 拆单/风控    │    │ 发单执行     │    │              │  │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    模块4: 回测 (Backtest)                    │   │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │   │
│  │  │ 因子回测     │    │ 策略回测     │    │ 绩效分析     │  │   │
│  │  │ IC/IR分析    │    │ 收益/风险    │    │ Sharpe/回撤  │  │   │
│  │  └──────────────┘    └──────────────┘    └──────────────┘  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 数据流

```
原始数据 → Verses(因子) → Lanetech(模型) → Alpha → 优化器 → 目标仓位 → 交易执行
            ↑                                              ↑
         因子计算                                      约束条件
         IC检验                                      Universe
```

## 阶段列表

### 阶段 1：需求与探索 ✅
- [x] 细化四大模块的具体需求
- [x] 确定技术栈
- [x] 设计数据模型和接口规范
- **状态：** complete

### 阶段 2：项目骨架搭建 ✅
- [x] 创建项目目录结构
- [x] 配置依赖管理（pyproject.toml）
- [x] 设计数据库 Schema
- [x] 配置文件模板
- **状态：** complete

### 阶段 3：数据支撑模块
- [x] 数据源抽象接口 (sources/base.py)
- [x] Tushare 适配器 (sources/tushare_client.py)
- [x] AKShare 适配器 (sources/akshare_client.py)
- [x] 双源交叉验证器 (sources/validator.py)
- [x] ETL 清洗器基类 (etl/base.py)
- [x] ETL 清洗器 (etl/cleaners.py - 缺失值/异常值/去重)
- [x] 复权处理 (etl/adjust.py)
- [x] 状态过滤 (etl/filters.py - ST/停牌/退市)
- [x] ETL 管道编排 (etl/pipeline.py)
- [x] 数据仓库模式 (storage/repository.py)
- [x] APScheduler 调度 (storage/scheduler.py)
- [x] CLI 命令扩展 (fetch/scheduler/init_data)
- [x] 单元测试 (tests/data/test_etl.py, test_sources.py, test_repository.py, test_scheduler.py)
- [x] 集成测试 (tests/data/test_integration.py)
- **设计文档：** [2026-03-22-data-module-design.md](docs/superpowers/specs/2026-03-22-data-module-design.md)
- **实现计划：** [2026-03-22-stage3-implementation.md](docs/superpowers/plans/2026-03-22-stage3-implementation.md)
- **架构方案：** 分层架构（数据源/清洗/存储/调度各层分离）
- **数据源策略：** 双源并行，交叉验证
- **初始数据：** 股票列表/指数行情/股票日线/每日指标/交易日历/财务指标
- **测试覆盖：** 135 个测试用例通过
- **状态：** complete

### 阶段 3.1：CLI 模块化重构 ✅
- [x] 创建 `quant/cli/` 目录结构
- [x] 创建 `cli/console.py` - 共享 Console 对象
- [x] 创建 `cli/version.py` - version + init 命令
- [x] 创建 `cli/db.py` - db 命令
- [x] 创建 `cli/fetch.py` - fetch 命令
- [x] 创建 `cli/scheduler.py` - scheduler 命令（~240行）
- [x] 创建 `cli/init_data.py` - init-data 命令
- [x] 创建 `cli/backtest.py` - backtest 命令（占位）
- [x] 创建 `cli/__init__.py` 注册所有命令
- [x] 删除原 `quant/cli.py`
- [x] 运行测试验证（135 测试通过）
- **设计文档：** [2026-03-25-cli-refactor-design.md](docs/superpowers/specs/2026-03-25-cli-refactor-design.md)
- **实现计划：** [2026-03-25-cli-refactor-implementation.md](docs/superpowers/plans/2026-03-25-cli-refactor-implementation.md)
- **状态：** complete

### 阶段 3.2：开发环境配置 ✅
- [x] 创建 `.env` 配置文件
- [x] 安装 PostgreSQL 15 (Homebrew)
- [x] 创建 `quant` 数据库
- [x] 设置数据库用户密码
- [x] 安装 `asyncpg` 依赖
- [x] 修复 pydantic-settings 嵌套模型环境变量加载问题
- [x] 修复数据库密码 URL 编码问题（`@` 符号）
- [x] 创建数据库表（11 个表）
- [x] 配置 Tushare API Token
- [x] 配置自定义 Tushare API URL（lianghua 镜像）
- **状态：** complete

### 阶段 3.2.1：Tushare API 配置 ✅
- [x] 配置 TUSHARE_TOKEN 和 TUSHARE_API_URL
- [x] 修改 TushareClient 支持自定义 API 地址
- [x] 使用 setattr() 设置私有属性避免 Pylance 警告
- **状态：** complete

### 阶段 3.2.2：数据初始化 ✅
- [x] 安装 greenlet 依赖
- [x] 修复日期字符串转换（pd.to_datetime().dt.date）
- [x] 修复 asyncpg 参数数量限制（分批插入）
- [x] 移除 is_hs 字段（模型中不存在）
- [x] 初始化 3 年历史数据
- **数据状态：**
  - stock_info: 5,493 条
  - trade_calendar: 1,096 条
  - daily_quote: 6,000 条
- **状态：** complete

### 阶段 4：策略模块
- [ ] Verses 因子库
  - [ ] 基础操作符（rank, quantile, zscore）
  - [ ] 时序操作符（ts_mean, ts_std, ts_rank）
  - [ ] 分组操作符（group_rank, group_mean）
  - [ ] 高级操作符（交互、条件）
- [ ] Lanetech 模型
  - [ ] 传统 ML（LGBM/XGBoost）
  - [ ] 深度学习（LSTM/Transformer）
  - [ ] 强化学习（DQN/PPO）
- [ ] Alpha 生成器
- [ ] 优化器（MVO/QP）
- **状态：** pending

### 阶段 5：回测模块
- [ ] 回测引擎设计
- [ ] 因子评估指标（IC/IR/RankIC）
- [ ] 收益指标（年化/累计/超额）
- [ ] 风险指标（最大回撤/波动率/Sharpe）
- [ ] 交易指标（换手率/胜率/盈亏比）
- **状态：** pending

### 阶段 6：交易模块
- [ ] 订单管理系统
- [ ] 券商接口对接
- [ ] 风控模块
  - [ ] 仓位限制
  - [ ] 止损限制
  - [ ] 黑白名单
- **状态：** pending

### 阶段 7：集成与测试
- [ ] 模块集成
- [ ] 端到端测试
- [ ] 性能优化（Rust/C++ 加速）
- [ ] 文档编写
- **状态：** pending

## 已做决策
| 决策 | 理由 |
|------|------|
| 数据源：Tushare/AKShare | 免费开源，适合入门和研究 |
| 存储：PostgreSQL | 关系型，适合结构化数据 |
| 目标：研究+实盘 | 先回测研究，后续扩展实盘 |
| 市场：A 股 | 用户需求 |
| 频率：日线 | 用户需求，适合中低频策略 |
| 语言：Python + Rust/C++ | Python 开发效率 + 性能模块加速 |
| 模型：逐步扩展 | 先跑通流程，再迭代优化 |
| ORM：SQLAlchemy 2.0 | 现代 Python ORM，支持异步 |
| 配置：pydantic-settings | 类型安全，支持环境变量 |
| CLI：typer + rich | 现代 CLI 框架，美观输出 |
| 日志：loguru | 简单易用，功能强大 |
| 数据库表：10个 | 股票/指数/行情/财务/因子分类存储 |
| 包结构：quant/ 顶层包 | 清晰的命名空间，避免与系统包冲突 |
| Python 版本：>= 3.12 | 使用最新稳定版本 |
| 数据源策略：双源并行 | Tushare + AKShare 交叉验证，提高数据质量 |
| 调度器：APScheduler | 轻量级定时任务，适合单机部署 |
| ETL 架构：管道模式 | 可组合的清洗器链，灵活配置 |

## 遇到的错误
| 错误 | 尝试次数 | 解决方案 |
|------|---------|---------|
| hatchling 无法识别包结构 | 2 | 修改 pyproject.toml 添加 hatch 配置 |
| lightgbm 找不到 libomp | 1 | 设置 DYLD_LIBRARY_PATH 环境变量 |
| my_first_quant 导入冲突 | 1 | 重构为 quant/ 顶层包 |
| pydantic-settings 嵌套模型不加载 .env | 2 | 在嵌套模型中添加 `env_file=".env"` |
| 数据库密码 `@` 符号破坏 URL | 1 | `urllib.parse.quote_plus()` URL 编码 |
| Pylance: `_DataApi__http_url` 属性未知 | 1 | 使用 `setattr()` 代替直接属性访问 |
| asyncpg 参数数量超限 (32767) | 1 | `_bulk_insert` 分批插入 (batch_size=2000) |
| 日期字符串无法插入 DATE 列 | 1 | `pd.to_datetime().dt.date` 转换 |
| SQLAlchemy async 缺少 greenlet | 1 | `pip install greenlet` |
