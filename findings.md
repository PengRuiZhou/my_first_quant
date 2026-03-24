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

#### Stage 3 Phase 2 实现发现（ETL 清洗层）

**ETL 架构设计**：
- **基类**：`BaseCleaner`, `BaseTransformer`, `BaseFilter` - 抽象接口，支持管道组合
- **清洗器**：`MissingValueCleaner`, `DuplicateCleaner`, `OutlierCleaner` - 处理数据质量问题
- **复权**：`PriceAdjuster` - 支持前复权(qfq)/后复权(hfq)/不复权(none)
- **过滤**：`StockStatusFilter`, `TradeableFilter` - 排除 ST/停牌/退市股票
- **管道**：`ETLPipeline` - 链式调用，组合所有清洗步骤

**ETL 执行顺序**：
```
原始数据 → 去重 → 缺失值处理 → 异常值处理 → 复权 → 状态过滤 → 清洗后数据
```

**清洗器设计要点**：
1. **无状态设计**：清洗器只有配置参数，不保存状态，便于复用
2. **统计信息**：每个清洗器记录输入/输出行数、移除/修改的行数
3. **分组填充**：缺失值按股票分组填充，避免跨股票污染
4. **缩尾处理**：异常值使用 winsorize 方法，保留极值但压缩到边界
5. **链式调用**：`pipeline.add_cleaner().set_adjuster().set_filter()`

**复权计算**：
- 前复权(qfq): `adj_price = price * adj_factor / latest_adj_factor`
- 后复权(hfq): `adj_price = price * adj_factor`
- 需重算涨跌幅：`adj_pct_chg = (adj_close - prev_adj_close) / prev_adj_close * 100`

**状态过滤条件**：
- ST 股票：从股票名称判断（包含 ST、*ST、S*ST 等）
- 退市股票：`list_status` 为 D(退市) 或 P(暂停上市)
- 停牌股票：需要外部数据源提供
- 换手率/价格/成交量：支持阈值过滤

**预设管道**：
- `create_default_pipeline()`: 去重 + 缺失值填充 + 缩尾 + 前复权 + 状态过滤
- `create_minimal_pipeline()`: 仅去重 + 缺失值填充
- `create_strict_pipeline()`: 去重 + 删除缺失值 + 删除异常值 + 严格过滤

#### Stage 3 Phase 3 实现发现（存储层）

**DataRepository 设计**：
- **异步 ORM**：使用 SQLAlchemy 2.0 async (asyncpg 驱动)
- **批量插入**：PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` 实现 upsert
- **数据类型方法**：
  - `get_stock_list()`, `upsert_stock_info()`
  - `get_daily_quotes()`, `upsert_daily_quotes()`
  - `get_index_quotes()`, `upsert_index_quotes()`
  - `get_trade_dates()`, `get_latest_trade_date()`, `upsert_trade_calendar()`
  - `get_daily_basic()`, `upsert_daily_basic()`
  - `get_financial_indicator()`, `upsert_financial_indicator()`
  - `get_daily_quote_count()`, `get_stock_count()`

**DataScheduler 设计**：
- **调度器**：APScheduler AsyncIOScheduler
- **默认定时任务**：
  - 每日 18:00 更新日线行情
  - 每日 18:30 更新每日指标
  - 每周六 10:00 更新股票列表
  - 每周六 10:30 更新交易日历
- **手动触发**：`run_job(job_id)` 支持手动运行任务
- **历史初始化**：`init_historical_data(years)` 批量获取历史数据

**技术实现要点**：
1. **PostgreSQL Upsert**：使用 `insert().on_conflict_do_update()` 处理重复数据
2. **NaN 处理**：DataFrame 转 dict 时，将 `pd.NA`/`np.nan` 转为 `None`
3. **Pylance 类型问题**：`result.rowcount` 需用 `getattr(result, "rowcount", 0)` 访问
4. **会话管理**：使用 `async_sessionmaker` 创建异步会话，`expire_on_commit=False` 避免延迟加载问题

**存储层数据流**：
```
DataFrame → _bulk_insert() → records → PostgreSQL (upsert)
                                                    ↓
query → Result → scalars().all() → DataFrame
```

#### Stage 3 Phase 4 实现发现（CLI 扩展）

**CLI 命令设计**：
- **fetch 命令**：获取数据并存储到数据库
  - 支持 6 种数据类型：`stock_list`, `daily`, `index`, `basic`, `calendar`, `financial`
  - 选项：`--start`, `--end`, `--source`
  - 自动运行 ETL 管道（去重 + 缺失值填充）
- **scheduler 命令组**：管理定时任务
  - `start` - 后台启动调度器
  - `stop` - 停止调度器
  - `status` - 查看运行状态和最近日志
  - `run --job <id>` - 手动运行指定任务
  - `list` - 列出所有定时任务
- **init-data 命令**：初始化历史数据
  - `--years` 选项指定年数
  - 批量获取股票列表、交易日历、日线行情、每日指标、指数行情

**技术实现要点**：
1. **异步 CLI**：使用 `asyncio.run()` 包装异步函数
2. **后台进程**：scheduler start 使用 `nohup` 后台运行
3. **进程管理**：通过 PID 文件 (`.quant/scheduler/scheduler.pid`) 追踪调度器进程
4. **日志存储**：日志文件存储在项目目录 `.quant/scheduler/scheduler.log`
5. **跨平台兼容**：使用 `os.kill(pid, 0)` 检查进程状态（兼容 macOS/Linux）
6. **Rich 输出**：使用 `console.status()` 显示进度，`Table` 展示结果
7. **延迟导入**：CLI 命令内部导入模块，避免启动时加载所有依赖

**调度器任务配置**：
| 任务 ID | 描述 | Cron 表达式 |
|---------|------|-------------|
| update_daily_quotes | 每日行情更新 | 0 18 * * * |
| update_daily_basic | 每日指标更新 | 30 18 * * * |
| update_stock_list | 股票列表更新 | 0 10 * * 6 |
| update_trade_calendar | 交易日历更新 | 30 10 * * 6 |

**CLI 命令示例**：
```bash
# 获取数据
quant fetch stock_list
quant fetch daily -s 20230101 -e 20231231
quant fetch calendar

# 调度器管理
quant scheduler list
quant scheduler start
quant scheduler status
quant scheduler run --job update_daily_quotes
quant scheduler stop

# 初始化历史数据
quant init-data --years 3
```

#### Stage 3 Phase 5 实现发现（测试）

**测试架构设计**：
- **测试目录**：`tests/data/`
- **测试文件**：
  - `test_etl.py` - ETL 清洗器测试（~50 测试用例）
  - `test_sources.py` - 数据源测试 with mocks（~35 测试用例）
  - `test_repository.py` - 数据仓库 CRUD 测试（~25 测试用例）
  - `test_scheduler.py` - 调度器任务管理测试（~20 测试用例）
  - `test_integration.py` - 完整管道工作流测试（~15 测试用例）

**测试技术要点**：
1. **Mock 策略**：使用 `unittest.mock.AsyncMock` 模拟异步数据源和数据库操作
2. **Fixtures 设计**：按功能分组（sample_quotes, sample_stock_info, mock_session 等）
3. **异步测试**：使用 `pytest-asyncio` 的 `@pytest.mark.asyncio` 装饰器
4. **边缘情况覆盖**：空输入、单行数据、全 NaN 列、混合数据类型
5. **性能测试**：大数据集管道处理（10000 行）
6. **数据质量验证**：去重检查、价格约束（high >= low）、成交量非负

**测试结果**：
```
135 passed, 5 skipped, 8 warnings in 0.60s
```

**跳过的测试**：
- 需要 `asyncpg` 模块的数据库连接测试（CI 环境中验证）
- 需要运行中事件循环的调度器启动/停止测试（集成测试中验证）

**测试覆盖范围**：
| 模块 | 测试重点 |
|------|----------|
| ETL Cleaners | 缺失值填充策略、去重逻辑、异常值检测方法 |
| Price Adjuster | 前复权/后复权计算、涨跌幅重算 |
| Stock Status Filter | ST/停牌/退市识别、白名单/黑名单过滤 |
| ETL Pipeline | 链式调用、统计信息、管道工厂函数 |
| Data Validator | 双源交叉验证、数值/字符串字段合并、异常报告 |
| Data Repository | CRUD 操作、批量插入、NaN 处理 |
| Data Scheduler | 任务添加/移除/暂停/恢复、默认任务配置 |
| Integration | 完整工作流、数据一致性、边缘情况 |

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
| CLI 架构：模块化拆分 | 按命令拆分到 quant/cli/ 目录，提高可维护性和扩展性 |

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
