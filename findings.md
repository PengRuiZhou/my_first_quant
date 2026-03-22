# 发现与决策

## 需求摘要

### 项目规格
| 维度 | 选择 |
|------|------|
| 操作系统 | macOS (Apple Silicon M5 Pro) |
| Python 环境 | Conda: `/opt/miniconda3/envs/peng` (3.12.12) |
| 目标市场 | A 股（沪深两市） |
| 数据频率 | 日线级别 |
| 数据源 | Tushare / AKShare |
| 存储 | PostgreSQL |
| 开发语言 | Python 主体 + Rust/C++ 性能模块 |
| 目标 | 研究 + 实盘 |

### 模块1：策略部分
- **Verses 因子库**
  - Verse = 因子/信号，通过 operator + 数据组合生成
  - 例：quantile(市值), rank(ROE), ts_mean(close, 20)
  - 要求：因子间相关性尽量低
  - 操作符类型：
    - 基础操作符：rank, quantile, zscore, log, abs...
    - 时序操作符：ts_mean, ts_std, ts_rank, ts_delta, ts_max, ts_min...
    - 分组操作符：group_rank, group_mean, group_zscore...
    - 高级操作符：条件表达式、交互操作

- **Lanetech 模型**
  - 输入：多个 Verses（作为 features）
  - 输出：Alpha 向量（每支股票的残差收益预测）
  - 模型类型（逐步扩展）：
    - 传统 ML：LGBM, XGBoost, RandomForest
    - 深度学习：LSTM, Transformer, GRU
    - 强化学习：DQN, PPO, A2C

- **优化器**
  - 输入：Alpha + Universe（票池）+ Constraints
  - 约束条件：
    - 仓位限制（单股上限、行业暴露）
    - 换手率限制
    - 交易量限制
  - 输出：目标仓位（买卖信号）
  - 方法：均值方差优化(MVO)、二次规划(QP)

### 模块2：交易部分
- 订单管理系统
- 券商接口对接
- 风控模块：
  - 仓位限制
  - 止损限制
  - 黑白名单机制

### 模块3：数据支撑
- 每日交易数据获取（OHLCV、财务数据）
- 市场信息获取（指数、行业分类）
- 数据清洗 ETL
- PostgreSQL 持久化
- **Stage 3 设计决策**：
  - 数据源策略：双源并行（Tushare + AKShare），交叉验证
  - 定时调度：APScheduler
  - ETL 范围：基础清洗/异常值处理/复权处理/股票状态过滤
  - 初始数据：股票列表/指数行情/股票日线/每日指标/交易日历/财务指标
  - 架构：分层架构（sources/etl/storage 各层分离）
  - 设计文档：`docs/superpowers/specs/2026-03-22-data-module-design.md`

#### Stage 3 架构详情

**目录结构**：
```
quant/data/
├── sources/           # 数据源层
│   ├── base.py        # 抽象接口 (BaseDataSource)
│   ├── tushare_client.py
│   ├── akshare_client.py
│   └── validator.py   # 双源交叉验证
├── etl/               # ETL 清洗层
│   ├── base.py        # 清洗器基类
│   ├── cleaners.py    # 缺失值/异常值/去重
│   ├── adjust.py      # 复权处理
│   ├── filters.py     # 状态过滤
│   └── pipeline.py    # ETL 管道编排
├── storage/           # 存储层
│   ├── repository.py  # 数据仓库 (CRUD)
│   └── scheduler.py   # APScheduler 调度
└── models/            # 数据模型（已有）
```

**数据流**：
```
Tushare ──┐
          ├──> validator.py ──> pipeline.py ──> repository.py ──> PostgreSQL
AKShare ──┘                         │
                                    ▼
                            scheduler.py (定时触发)
```

#### Stage 3 Phase 1 实现发现（数据源层）

**Tushare 与 AKShare 差异**：
| 差异点 | Tushare | AKShare |
|--------|---------|---------|
| 股票代码格式 | `000001.SZ` | `000001` |
| 接口风格 | REST API (pro_api) | 直接函数调用 |
| 字段命名 | 英文 (ts_code, trade_date) | 中文 (代码, 日期) |
| 异步支持 | 需用 run_in_executor 包装 | 需用 run_in_executor 包装 |
| 复权因子 | 直接提供 adj_factor | 需通过 qfq/原始价格比值计算 |
| 类型提示 | 有类型存根 | 无完整类型存根，需用 getattr 动态调用 |

**技术实现要点**：
1. **异步适配**：Tushare/AKShare 都是同步 API，使用 `asyncio.run_in_executor` 包装
2. **重试机制**：`@retry_on_failure` 装饰器，支持配置重试次数和延迟
3. **字段映射**：使用字典映射 Tushare/AKShare 字段到标准数据库字段
4. **代码转换**：AKShare 需要代码格式转换（`_convert_code_to_ts`, `_convert_ts_to_code`）
5. **交叉验证**：`DataValidator` 支持数值容差比较和字符串完全匹配
6. **动态调用**：AKShare 接口名可能变化，使用 `getattr(ak, "func_name", None)` 动态获取

**Pylance 类型问题处理**：
- `last_error` 初始化为 `None`，需添加类型注解和 None 检查
- `df.get(key, default)` 返回值可能是 Series 或默认值，用 `if key in df.columns` 判断
- 可选属性 `self._report` 需在使用前检查 `is not None`

**BaseDataSource 接口方法**：
- `get_stock_list()` - 股票列表
- `get_index_list()` - 指数列表
- `get_daily_quotes()` - 日线行情
- `get_index_quotes()` - 指数行情
- `get_trade_calendar()` - 交易日历
- `get_daily_basic()` - 每日指标
- `get_financial_indicator()` - 财务指标
- `get_adj_factor()` - 复权因子

### 模块4：回测
- 因子回测（单因子 IC/IR 分析）
- 策略回测（组合收益/风险）
- 评估指标：
  - 因子指标：IC, IR, RankIC
  - 收益指标：年化收益、累计收益、超额收益
  - 风险指标：最大回撤、波动率、Sharpe、Sortino
  - 交易指标：换手率、胜率、盈亏比

## 核心概念

### Verse（因子）
```
Verse = Operator(Data)
例：
- quantile(市值)           # 基础操作符
- ts_mean(close, 20)       # 时序操作符
- group_rank(ROE, 行业)    # 分组操作符
- rank(市值) * zscore(ROE) # 组合操作符
```

### Alpha
- 定义：预测的残差收益（去除市场因子后的收益）
- 形式：向量，每个股票一个值
- 越大表示预测该股票表现越好

### 优化器方法
1. **均值方差优化（MVO）**：max E[R] - λ × Var[R]
2. **风险平价**：每个资产贡献相等风险
3. **Black-Litterman**：结合市场均衡观点

## 技术决策
| 决策 | 理由 |
|------|------|
| 数据源：Tushare/AKShare | 免费开源，适合入门和研究 |
| 存储：PostgreSQL | 关系型，适合结构化数据 |
| 目标：研究+实盘 | 先回测研究，后续扩展实盘 |
| 市场：A 股 | 用户需求 |
| 频率：日线 | 用户需求，适合中低频策略 |
| 语言：Python + Rust/C++ | Python 开发效率 + 性能模块加速 |
| 模型：逐步扩展 | 先跑通流程，再迭代优化 |
| 包结构：quant/ 顶层包 | 清晰的命名空间，避免与系统包冲突 |
| Python 版本：>= 3.12 | 使用最新稳定版本 |

## Stage 2 补充：项目骨架

### 数据库 Schema 设计
| 表名 | 用途 | 主要字段 |
|------|------|----------|
| stock_info | 股票基础信息 | ts_code, name, industry, list_date |
| index_info | 指数基础信息 | ts_code, name, market, base_date |
| daily_quote | 日线行情 | ts_code, trade_date, OHLCV, pct_chg |
| index_daily_quote | 指数日线 | ts_code, trade_date, OHLCV |
| trade_calendar | 交易日历 | exchange, cal_date, is_open |
| financial_indicator | 财务指标 | ts_code, end_date, ROE, EPS, PE, PB |
| daily_basic | 每日基本面 | ts_code, trade_date, PE, PB, 市值 |
| factor_definition | 因子定义 | factor_id, name, category, formula |
| factor_data | 因子数据 | factor_id, trade_date, ts_code, value |
| factor_statistics | 因子统计 | factor_id, trade_date, mean, std, IC |

### 配置系统
- 使用 pydantic-settings 管理配置
- 支持 .env 文件和环境变量
- 子配置：Database, Tushare, AKShare, Backtest, Risk

### CLI 工具
- 基于 typer + rich
- 命令：version, init, db, fetch, backtest

## 参考资源
- Tushare: https://tushare.pro/
- AKShare: https://akshare.akfamily.xyz/
- WorldQuant Alpha101: 经典因子表达式参考
- zipline: 回测框架参考
- vnpy: 实盘交易框架参考

---
*每2次查看/浏览器/搜索操作后更新此文件*
