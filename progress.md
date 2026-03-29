# 进度日志

## 会话：2026-03-22

### 阶段 1：需求与探索
- **状态：** complete
- **开始时间：** 2026-03-22 00:00
- **完成时间：** 2026-03-22 00:30
- 已采取的行动：
  - 初始化规划文件系统（task_plan.md, findings.md, progress.md）
  - 收集用户需求，明确四大模块
  - 澄清 Verses 和 Lanetech 概念
  - 确定技术栈（市场、频率、数据源、存储、语言）
  - 确定回测指标和风控需求
  - 完成技术架构设计
- 创建/修改的文件：
  - CLAUDE.md（已存在）
  - task_plan.md（创建并更新）
  - findings.md（创建并更新）
  - progress.md（创建并更新）

### 阶段 2：项目骨架搭建
- **状态：** complete
- **开始时间：** 2026-03-22 01:37
- **完成时间：** 2026-03-22 02:55
- 已采取的行动：
  - 创建四大模块目录结构（data/strategy/backtest/execution）
  - 创建 pyproject.toml 依赖管理（含核心依赖、可选依赖、开发工具）
  - 设计数据库 Schema（10个表：股票/指数/行情/财务/因子）
  - 创建配置系统（pydantic-settings + .env.example）
  - 添加日志配置（loguru）
  - 创建 CLI 工具（typer + rich）
  - 创建 README.md, Makefile, conftest.py
  - 创建 .gitignore
  - **安装所有依赖**（pip install -e ".[all]"）
  - 修复 lightgbm 的 libomp 依赖（macOS 需要设置 DYLD_LIBRARY_PATH）
  - 修复 hatch 构建配置
  - **包结构重构**：创建 `quant/` 顶层包，解决命名空间问题
  - 更新 Python 版本要求为 3.12
- 创建/修改的文件：
  - pyproject.toml, .env.example, .gitignore
  - README.md, Makefile, CLAUDE.md
  - quant/__init__.py, quant/cli.py
  - quant/data/models/base.py, stock.py, market.py, financial.py, factor.py
  - quant/core/config.py, logging.py, __init__.py
  - quant/data/models/__init__.py
  - tests/conftest.py
  - 各模块 __init__.py（共19个）
- 包结构（重构后）：
  ```
  my_first_quant/          # 项目根目录
  ├── quant/               # Python 包（顶层命名空间）
  │   ├── data/
  │   ├── strategy/
  │   ├── backtest/
  │   ├── execution/
  │   └── core/
  └── tests/
  ```
- 已安装依赖：
  - 核心：pandas 3.0.1, numpy 2.4.3, scipy 1.17.1, sqlalchemy 2.0.48
  - 数据源：tushare 1.4.25, akshare 1.18.43
  - ML：scikit-learn 1.8.0, lightgbm 4.6.0, xgboost 3.2.0
  - DL：torch 2.10.0 (MPS 可用), stable-baselines3
  - 开发：pytest 9.0.2, black 26.3.1, ruff, mypy
  - 可视化：matplotlib 3.10.8, seaborn 0.13.2, plotly 6.6.0

### 阶段 3：数据支撑模块
- **状态：** complete
- **开始时间：** 2026-03-22 (当前会话)
- **完成时间：** 2026-03-24
- 已采取的行动：
  - Brainstorming 设计讨论
  - 确定数据源策略：双源并行，交叉验证
  - 确定调度方式：APScheduler
  - 确定 ETL 范围：基础清洗/异常值/复权/状态过滤
  - 确定初始数据：股票列表/指数行情/股票日线/每日指标/交易日历/财务指标
  - 确定架构方案：分层架构（sources/etl/storage 分离）
  - 编写设计文档 `docs/superpowers/specs/2026-03-22-data-module-design.md`
  - 编写实现计划 `docs/superpowers/plans/2026-03-22-stage3-implementation.md`
  - Spec 审查通过（无阻塞问题）
  - **Phase 1 数据源层实现完成**（2026-03-22）
  - **Phase 2 ETL 清洗层实现完成**（2026-03-22）
  - **Phase 3 存储层实现完成**（2026-03-22）
  - **Phase 4 CLI 扩展实现完成**（2026-03-23）
  - **Phase 5 单元测试和集成测试完成**（2026-03-24）
  - scheduler 日志路径从 `/tmp/` 改为项目目录 `.quant/scheduler/`
- 创建/修改的文件：
  - task_plan.md（更新阶段3任务清单）
  - findings.md（更新模块3设计决策和架构详情）
  - progress.md（更新进度）
  - docs/superpowers/specs/2026-03-22-data-module-design.md（设计文档）
  - docs/superpowers/plans/2026-03-22-stage3-implementation.md（实现计划）
  - **quant/data/sources/base.py**（数据源抽象接口）✅
  - **quant/data/sources/tushare_client.py**（Tushare 适配器）✅
  - **quant/data/sources/akshare_client.py**（AKShare 适配器）✅
  - **quant/data/sources/validator.py**（双源交叉验证器）✅
  - **quant/data/sources/__init__.py**（更新导出）✅
  - **quant/data/etl/base.py**（ETL 基类）✅
  - **quant/data/etl/cleaners.py**（基础清洗器）✅
  - **quant/data/etl/adjust.py**（复权处理器）✅
  - **quant/data/etl/filters.py**（状态过滤器）✅
  - **quant/data/etl/pipeline.py**（ETL 管道编排）✅
  - **quant/data/etl/__init__.py**（更新导出）✅
  - **quant/data/storage/repository.py**（数据仓库）✅
  - **quant/data/storage/scheduler.py**（数据调度器）✅
  - **quant/data/storage/__init__.py**（存储模块导出）✅
  - **quant/cli.py**（CLI 扩展：fetch/scheduler/init_data 命令）✅
  - **tests/data/__init__.py**（测试包）✅
  - **tests/data/test_etl.py**（ETL 清洗器测试）✅
  - **tests/data/test_sources.py**（数据源测试 with mocks）✅
  - **tests/data/test_repository.py**（数据仓库测试）✅
  - **tests/data/test_scheduler.py**（调度器测试）✅
  - **tests/data/test_integration.py**（集成测试）✅
- 测试结果：
  - **151 passed, 5 skipped, 8 warnings in 0.69s**
  - 测试覆盖：ETL 清洗器、数据源、数据仓库、调度器、集成流程
- 已完成文件：
  - ~~quant/data/sources/*~~ ✅
  - ~~quant/data/etl/*~~ ✅
  - ~~quant/data/storage/*~~ ✅
  - ~~quant/cli.py~~ ✅
  - ~~tests/data/*~~ ✅

### 阶段 4：策略模块
- **状态：** pending
- 已采取的行动：
  -
- 创建/修改的文件：
  -

### 阶段 5：回测模块
- **状态：** pending
- 已采取的行动：
  -
- 创建/修改的文件：
  -

### 阶段 6：交易模块
- **状态：** pending
- 已采取的行动：
  -
- 创建/修改的文件：
  -

### 阶段 7：集成与测试
- **状态：** pending
- 已采取的行动：
  -
- 创建/修改的文件：
  -

## 测试结果
| 测试 | 输入 | 预期结果 | 实际结果 | 状态 |
|------|------|---------|---------|------|
|      |      |         |         |      |

## 错误日志
| 时间戳 | 错误 | 尝试次数 | 解决方案 |
|--------|------|---------|---------|
| 2026-03-22 02:05 | hatchling 无法识别包结构 | 2 | 修改 pyproject.toml 添加 `[tool.hatch.build.targets.wheel] packages = [...]` |
| 2026-03-22 02:08 | lightgbm 找不到 libomp.dylib | 1 | libomp 已通过 brew 安装。设置 `DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib"` |
| 2026-03-22 02:50 | my_first_quant 包导入失败 | 1 | 包结构重构：创建 `quant/` 顶层包，导入方式改为 `from quant.xxx import ...` |
| 2026-03-22 (Phase1) | Pylance: `last_error` 可能为 None | 1 | tushare_client.py: 添加类型注解和 None 检查 |
| 2026-03-22 (Phase1) | Pylance: AKShare 属性不存在 | 1 | akshare_client.py: 使用 `getattr` 动态调用接口 |
| 2026-03-22 (Phase1) | Pylance: `df.get()` 返回类型问题 | 1 | akshare_client.py: 使用 `if col in df.columns` 判断替代 `.get()` |
| 2026-03-22 (Phase1) | Pylance: `self._report` 可能为 None | 2 | validator.py: 添加 `if self._report is not None` 检查 |
| 2026-03-22 Stage3 | Pylance: `last_error` 可能为 None | 1 | tushare_client.py: 添加类型注解和 None 检查 |
| 2026-03-22 Stage3 | Pylance: AKShare 属性不存在 | 1 | akshare_client.py: 使用 `getattr` 动态调用接口 |
| 2026-03-22 Stage3 | Pylance: `df.get()` 返回类型问题 | 1 | akshare_client.py: 改用 `if col in df.columns` 判断 |
| 2026-03-22 Stage3 | Pylance: `self._report` 可能为 None | 1 | validator.py: 添加 `if self._report is not None` 检查 |
| 2026-03-22 Stage3 Phase2 | ImportError: `get_logger` not found | 1 | pipeline.py: 改用 `from loguru import logger` 直接导入 |
| 2026-03-22 Stage3 Phase3 | Pylance: `result.rowcount` 属性不存在 | 1 | repository.py: 使用 `getattr(result, "rowcount", 0) or 0` 避免 Pylance 类型错误 |
| 2026-03-25 Stage3.2 | pydantic-settings 嵌套模型不加载 .env | 2 | 在 DatabaseConfig/TushareConfig 中添加 `env_file=".env"` 配置 |
| 2026-03-25 Stage3.2 | 数据库密码 `@` 符号破坏 URL 解析 | 1 | 使用 `urllib.parse.quote_plus()` 对密码进行 URL 编码 |
| 2026-03-25 Stage3.2.1 | Pylance: `_DataApi__http_url` 属性未知 | 1 | tushare_client.py: 使用 `setattr()` 代替直接属性访问 |
| 2026-03-25 Stage3.2.2 | `is_hs` 字段不在 StockInfo 模型中 | 1 | 从 STOCK_LIST_MAP 移除该字段 |
| 2026-03-25 Stage3.2.2 | asyncpg 参数数量超限 (32767) | 1 | `_bulk_insert` 分批插入 (batch_size=2000) |
| 2026-03-25 Stage3.2.2 | 日期字符串无法插入 DATE 列 | 1 | `pd.to_datetime().dt.date` 转换 |
| 2026-03-25 Stage3.2.2 | SQLAlchemy async 缺少 greenlet | 1 | `pip install greenlet` |
| 2026-03-28 Stage3.2.5 | upsert 覆盖 created_at 字段 | 1 | 在 `_bulk_insert` 中排除 `created_at` 列 |
| 2026-03-28 Stage3.2.5 | get_index_list 方法重复定义 | 1 | 删除第一个简单版本，保留增强版本 |
| 2026-03-28 Stage3.2.5 | INDEX_LIST_MAP 常量未使用 | 1 | 删除该常量 |

### 阶段 3.1：CLI 模块化重构
- **状态：** complete
- **开始时间：** 2026-03-25
- **完成时间：** 2026-03-25
- 已采取的行动：
  - 分析现有 CLI 结构（493 行代码）
  - 识别可提取的较大函数（fetch, scheduler, init_data 等）
  - 设计模块化目录结构（quant/cli/）
  - 编写设计文档 `docs/superpowers/specs/2026-03-25-cli-refactor-design.md`
  - **实现 8 个 CLI 模块**（使用 Subagent-Driven Development）
  - 删除原 `quant/cli.py` 文件
  - 验证所有 CLI 命令正常工作
- 创建/修改的文件：
  - `quant/cli/__init__.py` - 主入口，注册所有命令
  - `quant/cli/console.py` - 共享 Console 对象
  - `quant/cli/version.py` - version + init 命令
  - `quant/cli/db.py` - db 命令
  - `quant/cli/fetch.py` - fetch 命令
  - `quant/cli/scheduler.py` - scheduler 命令（~240行）
  - `quant/cli/init_data.py` - init-data 命令
  - `quant/cli/backtest.py` - backtest 命令（占位）
  - `docs/superpowers/specs/2026-03-25-cli-refactor-design.md`（设计文档）
- 提交记录：
  - `4735424` - feat(cli): add shared console module
  - `c3cca14` - feat(cli): add version and init commands
  - `66b55c1` - feat(cli): add db command
  - `3fad36b` - feat(cli): add fetch command
  - `10b9ca1` - feat(cli): add scheduler command
  - `766dd05` - feat(cli): add init-data command
  - `a9ba18f` - feat(cli): add backtest command
  - `1179123` - feat(cli): add main entry point
  - `ccc318f` - refactor(cli): remove old cli.py
  - `5e8ebdf` - docs(cli): mark design as completed
- 验证结果：
  - `quant --help` 显示 7 个命令 ✅
  - `quant version` 输出正确 ✅
  - 135 个测试用例通过 ✅
  - black + ruff 检查通过 ✅

### 阶段 3.2：开发环境配置
- **状态：** complete
- **开始时间：** 2026-03-25
- **完成时间：** 2026-03-25
- 已采取的行动：
  - 创建 `.env` 配置文件（`quant init`）
  - 安装 PostgreSQL 15 via Homebrew
  - 启动 PostgreSQL 服务（`brew services start postgresql@15`）
  - 创建 `quant` 数据库（`createdb quant`）
  - 设置数据库用户密码
  - 安装 `asyncpg` 异步 PostgreSQL 驱动
  - **修复 pydantic-settings 嵌套模型加载问题**（在 DatabaseConfig/TushareConfig 中添加 `env_file` 配置）
  - **修复数据库密码 URL 编码问题**（使用 `urllib.parse.quote_plus` 编码密码中的特殊字符）
  - 创建数据库表（`quant db create`，11 个表）
- 创建/修改的文件：
  - `.env` - 创建并配置
  - `quant/core/config.py` - 修复嵌套模型加载 + URL 编码
- 数据库表创建成功：
  - stock_info, stock_industry, index_info, daily_quote
  - index_daily_quote, trade_calendar, financial_indicator
  - daily_basic, factor_definition, factor_data, factor_statistics
- 待完成：
  - ~~用户注册 Tushare 并配置 Token~~ ✅ 已配置

### 阶段 3.2.1：Tushare API 配置
- **状态：** complete
- **开始时间：** 2026-03-25
- **完成时间：** 2026-03-25
- 已采取的行动：
  - 配置 Tushare Token 和自定义 API URL
  - 修改 TushareClient 支持自定义 API 地址
  - 使用 `setattr()` 设置私有属性避免 Pylance 类型警告
- 创建/修改的文件：
  - `.env` - 配置 TUSHARE_TOKEN 和 TUSHARE_API_URL
  - `quant/data/sources/tushare_client.py` - 新增 api_url 参数支持

### 阶段 3.2.2：数据初始化
- **状态：** complete
- **开始时间：** 2026-03-25
- **完成时间：** 2026-03-25
- 已采取的行动：
  - 安装 `greenlet` 依赖（SQLAlchemy async 需要）
  - 修复日期字符串转换问题（`pd.to_datetime().dt.date`）
  - 修复 asyncpg 参数数量限制（分批插入，batch_size=2000）
  - 移除 `is_hs` 字段（模型中不存在）
  - 成功初始化 3 年历史数据
- 创建/修改的文件：
  - `quant/data/sources/tushare_client.py` - 日期转换
  - `quant/data/storage/repository.py` - 分批插入
- 数据初始化结果：
  - stock_info: 5,493 条 ✅
  - trade_calendar: 1,096 条 ✅
  - daily_quote: 6,000 条 ✅

## 五问重启检查
| 问题 | 答案 |
|------|------|
| 我在哪里？ | 阶段 3 数据支撑模块 ✅ 完成，阶段 4 策略模块待开发 |
| 我要去哪里？ | 阶段 4：策略模块（Verses 因子库） |
| 目标是什么？ | 构建 A 股量化交易框架，支持因子研究、回测和实盘 |
| 我学到了什么？ | 见 findings.md（upsert 时间戳保留、CLI 批量更新、adj_factor 决策） |
| 我做了什么？ | CLI 增强 + 数据更新优化 + adj_factor 决策 |

---

### 阶段 3.2.3：DateConverter ETL 重构
- **状态：** complete
- **开始时间：** 2026-03-25
- **完成时间：** 2026-03-26
- 已采取的行动：
  - 探索现有 ETL 代码结构（cleaners.py, pipeline.py, base.py）
  - 识别 TushareClient 中的日期转换代码位置
  - 编写 DateConverter 实现计划（8 任务，21 步骤）
  - 通过计划审查（修复 2 个关键问题）
  - **使用 Subagent-Driven Development 执行计划**
  - 实现 DateConverter 清洗器（12 个单元测试）
  - 更新 ETL Pipeline（create_default/minimal/strict_pipeline）
  - 移除 TushareClient 日期转换代码
  - 更新 scheduler.py 使用 ETL 模块的 create_minimal_pipeline
  - 添加集成测试（4 个测试）
  - **改进 DateConverter**：
    - 添加 default_format 参数支持统一日期格式
    - 支持混合日期格式（YYYYMMDD, YYYY-MM-DD, YYYY/MM/DD）
    - 添加更多日期列后缀（datetime, timestamp）
    - 大小写不敏感匹配
    - 修复 pandas 3.0 混合格式解析问题
  - **性能优化**：
    - 批量解析优先（pandas 向量化）
    - 删除采样推断（避免偏差，简化流程）
    - 仅对失败行逐行回退
    - 性能：纯格式 7.3M rows/s，混合格式 729K rows/s
- 创建/修改的文件：
  - `quant/data/etl/cleaners.py` - 添加 DateConverter 类
  - `quant/data/etl/__init__.py` - 导出 DateConverter
  - `quant/data/etl/pipeline.py` - 更新 pipeline factory
  - `quant/data/sources/tushare_client.py` - 移除日期转换代码
  - `quant/data/storage/scheduler.py` - 使用 ETL 模块 pipeline
  - `tests/data/test_etl.py` - 添加 12 个 DateConverter 测试
  - `tests/data/test_integration.py` - 添加 4 个集成测试
  - `tests/data/test_scheduler.py` - 更新 cleaner 数量断言
- 提交记录：
  - `b51fa30` - refactor(etl): move date conversion from data sources to ETL layer
  - `ceba3e9` - feat(etl): improve DateConverter with better format handling
- 测试结果：
  - **151 passed, 5 skipped, 8 warnings in 0.69s**
- 架构改进：
  - 日期转换从数据源层移至 ETL 层
  - 数据源只负责获取原始数据
  - 类型转换统一在 ETL 层处理

### 阶段 3.2.4：数据模型增强 + 指数列表
- **状态：** complete
- **开始时间：** 2026-03-26
- **完成时间：** 2026-03-26
- 已采取的行动：
  - **DailyBasic 模型增强**：添加 `ps_ttm`（市销率TTM）和 `dv_ratio`（股息率）字段
  - **IndexInfo 模型增强**：添加 `index_type`、`category`、`exp_date` 字段
  - **TushareClient 增强**：
    - 添加 `COMMON_INDEX_CODES` 常量（50个常用指数）
    - 添加 `get_index_list()` 方法获取指数基本信息
    - 修复：`index_basic` API 不支持批量 ts_code，改为逐个获取
  - **scheduler.py 更新**：
    - `init_historical_data` 现在获取指数列表
    - 指数行情扩展为50个常用指数（宽基+行业+主题）
  - **数据库重建**：`quant db drop && quant db create`
  - **安装 TablePlus**：PostgreSQL GUI 工具
- 创建/修改的文件：
  - `quant/data/models/financial.py` - 添加 ps_ttm, dv_ratio 字段
  - `quant/data/models/stock.py` - 添加 index_type, category, exp_date 字段
  - `quant/data/sources/tushare_client.py` - 添加 get_index_list() + COMMON_INDEX_CODES
  - `quant/data/storage/scheduler.py` - 更新 init_historical_data
  - `progress.md`, `findings.md` - 更新文档
- 提交记录：
  - `c3cbb05` - feat(data): add index list support and enhance models
  - `49c1042` - fix(data): use single ts_code for index_basic API
- 数据初始化结果：
  | 表 | 记录数 |
  |---|-------|
  | stock_info | 5,493 |
  | index_info | 26 |
  | trade_calendar | 1,096 |
  | daily_quote | 6,000 |
  | daily_basic | 6,000 |
  | index_daily_quote | 18,852 |

### 阶段 3.2.4：数据模型增强 + 指数列表
- **状态：** complete
- **开始时间：** 2026-03-26
- **完成时间：** 2026-03-26
- 已采取的行动：
  - **DailyBasic 模型增强**：添加 `ps_ttm`（市销率TTM）和 `dv_ratio`（股息率）字段
  - **IndexInfo 模型增强**：添加 `index_type`、`category`、`exp_date` 字段
  - **TushareClient 增强**：
    - 添加 `COMMON_INDEX_CODES` 常量（约50个常用指数）
    - 添加 `get_index_list()` 方法获取指数基本信息
  - **scheduler.py 更新**：
    - `init_historical_data` 现在获取指数列表（约50个）
    - 指数行情扩展为50个常用指数（宽基+行业+主题）
  - **数据库重建**：`quant db drop && quant db create`
- 创建/修改的文件：
  - `quant/data/models/financial.py` - 添加 ps_ttm, dv_ratio 字段
  - `quant/data/models/stock.py` - 添加 index_type, category, exp_date 字段
  - `quant/data/models/market.py` - 删除重复的 IndexInfo
  - `quant/data/sources/tushare_client.py` - 添加 get_index_list() + COMMON_INDEX_CODES
  - `quant/data/storage/scheduler.py` - 更新 init_historical_data
- 指数覆盖范围（约50个）：
  - 宽基指数：上证综指、沪深300、上证50、中证500、中证1000、深证成指、创业板指等
  - 上证行业指数：能源、材料、工业、可选、消费、医药、金融、信息、电信、公用
  - 沪深300行业指数：10个行业分类
  - 中证行业指数：10个行业分类
  - 主题指数：科创50、创业板50、全指医药、中证银行等

### 阶段 3.2.5：CLI 增强 + 数据更新优化
- **状态：** complete
- **开始时间：** 2026-03-28
- **完成时间：** 2026-03-28
- 已采取的行动：
  - **修复 upsert 覆盖 created_at 问题**：在 `_bulk_insert` 中排除 `created_at` 列
  - **fetch 命令增强**：
    - 新增 `all` 数据类型，批量更新所有数据
    - 新增 `index_list` 数据类型
    - 支持类型：all/stock_list/index_list/daily/index/basic/calendar/financial
  - **init_data 增强**：添加 `financial`（财务指标）数据获取
  - **代码清理**：
    - 修复 `tushare_client.py` 中 `get_index_list` 重复定义
    - 删除未使用的 `INDEX_LIST_MAP` 常量
  - **adj_factor 决策**：暂不添加 `AdjFactor` 模型（详见 findings.md）
  - **财务指标并行获取实现**：
    - 添加 `--ts-code` 参数：按股票代码获取财务指标
    - 添加 `--max-workers` 参数：控制并行线程数（默认20，范围1-100）
    - 实现 `_fetch_financial_parallel` 纯同步函数，使用 ThreadPoolExecutor
    - 通过 `run_in_executor` 桥接同步/异步边界
    - 线程安全设计：每个线程创建独立的数据源客户端
- 创建/修改的文件：
  - `quant/data/storage/repository.py` - 修复 upsert 覆盖 created_at
  - `quant/cli/fetch.py` - 添加 all/index_list 支持 + --ts-code/--max-workers 参数 + 并行获取
  - `quant/data/storage/scheduler.py` - 添加 financial 到 init_historical_data
  - `quant/cli/init_data.py` - 更新文档
  - `quant/data/sources/tushare_client.py` - 删除重复方法
  - `findings.md`, `progress.md` - 更新文档
- CLI 使用示例：
  ```bash
  quant fetch all -s 20260101 -e 20260328  # 批量更新所有数据
  quant fetch all -s 20260101 -e 20260328 --max-workers 8  # 指定并行度
  quant fetch index_list                    # 获取指数列表
  quant fetch financial -s 20260101        # 获取财务指标
  quant fetch financial --ts-code 000001.SZ  # 获取指定股票的财务指标
  quant init-data --years 3                # 初始化3年数据（含财务指标）
  ```
- 提交记录：
  - `924df67` - feat(cli): add fetch all/index_list and fix upsert created_at
  - `docs: update CLI docs for financial parallel fetch`（本次提交）

### 阶段 3.2.7：Financial 单股票 ETL 修复
- **状态：** complete
- **开始时间：** 2026-03-29
- **完成时间：** 2026-03-29
- 已采取的行动：
  - **问题发现**：单股票获取分支（`--ts-code`）缺少 ETL 处理，导致日期字段未转换为 date 对象
  - **修复**：在单股票分支添加 DateConverter + DuplicateCleaner 处理
  - **重试失败股票**：成功获取 002067.SZ (11条) 和 000050.SZ (12条)
  - **增加 retry 次数**：从 2 次改为 3 次，递增等待 1s → 1.5s → 2s → 2.5s
- 创建/修改的文件：
  - `quant/cli/fetch.py` - 修复单股票 ETL + retry 次数改为 3

### 阶段 3.2.6：Financial 并行获取内存优化
- **状态：** complete
- **开始时间：** 2026-03-29
- **完成时间：** 2026-03-29
- 已采取的行动：
  - **问题分析**：原实现将所有股票的 df 合并成大 DataFrame 再写入，内存峰值高
  - **方案选择**：采用逐个 df 直接 upsert 方案（DB 调用 = max_workers，默认 10 次）
  - **实现优化**：
    - `_fetch_financial_parallel` 返回 `list[pd.DataFrame]` 而非合并后的 DataFrame
    - 调用方遍历列表逐个 upsert
    - 移除最终的 `pd.concat` 操作
    - 添加 ETL Pipeline 处理（DateConverter + DuplicateCleaner）
    - 添加单 df 失败容错处理（继续处理下一个）
    - **添加 retry 机制**：限流时最多重试 3 次，递增等待（1s → 1.5s → 2s → 2.5s）
    - **调整默认并发**：从 20 降到 10（范围 1-50）
  - **测试验证**：
    - 20 线程无 retry：15% 限流失败，写入中断
    - 10 线程无 retry：~85% 成功率
    - 10 线程 + retry(2次)：**0.036% 失败率（2/5494）**，显著改善
    - 10 线程 + retry(3次)：更稳定的配置
    - 最终入库：58,927 条记录
  - **最终测试结果**（2026-03-29 20:37）：
    - 总股票数：5494
    - ✓ 成功：5345 (97.3%)
    - ○ 空数据：147 (2.7%)
    - ✗ 失败：2 (0.036%) - 本地代理网络问题，非限流
    - **结论**：10 线程 + retry 机制稳定性达标
- 创建/修改的文件：
  - `quant/cli/fetch.py` - 优化 financial 批量获取的内存使用 + retry + 容错
  - `CLAUDE.md` - 添加内存优化说明
  - `README.md` - 更新 CLI 命令示例
  - `docs/superpowers/plans/2026-03-28-financial-parallel-fetch.md` - 标记优化已实现
- 优化效果：
  - 内存峰值从 `~2x总数据量` 降到 `~max_workers个df`
  - DB 调用次数：10 次（默认值）
  - 每个 df 独立 upsert，失败不影响其他
  - 限流自动重试，成功率从 ~85% 提升到 ~99%

---
*完成每个阶段或遇到错误后更新*
