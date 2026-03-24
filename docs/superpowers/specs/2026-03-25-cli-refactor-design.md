# CLI 模块化重构设计

## 背景

当前 `quant/cli.py` 文件约 493 行，包含多个命令的实现逻辑，随着项目发展会继续增长。为了提高可维护性和扩展性，需要将其拆分为模块化结构。

## 目标

1. **可维护性**：每个命令独立文件，修改互不影响
2. **可扩展性**：新增命令只需添加新文件
3. **可测试性**：每个命令可独立测试
4. **向后兼容**：保持现有 CLI 命令和入口点不变

## 目录结构

```
quant/cli/
├── __init__.py      # 主入口，注册所有命令
├── console.py       # 共享 Console 对象（避免循环导入）
├── fetch.py         # fetch 命令（数据获取）
├── scheduler.py     # scheduler 命令（调度器管理）
├── db.py            # db 命令（数据库操作）
├── init_data.py     # init-data 命令（历史数据初始化）
├── backtest.py      # backtest 命令（回测，待实现）
└── version.py       # version/init 命令（版本和初始化）
```

> **注意**：将 `console` 放在单独的 `console.py` 中是为了避免循环导入。子模块从 `quant.cli.console` 导入时，不会触发 `__init__.py` 的完整加载。

## 模块设计

### 1. `console.py` - 共享 Console 对象

```python
"""共享 Console 对象"""
from rich.console import Console

console = Console()
```

> **设计说明**：将 `console` 放在单独文件中是为了避免循环导入。子模块导入 `from quant.cli.console import console` 时不会触发 `__init__.py` 的加载。

### 2. `__init__.py` - 主入口

```python
"""CLI 主入口"""
import typer

from quant.cli import fetch, scheduler, db, init_data, backtest, version

# 主应用
app = typer.Typer(
    name="quant",
    help="A股量化交易框架",
    add_completion=False,
)

# 注册命令（使用 name= 参数处理命令名与函数名不一致的情况）
app.command()(version.version)
app.command()(version.init)
app.command()(db.db)
app.command(name="fetch")(fetch.fetch)
app.command()(scheduler.scheduler)
app.command(name="init-data")(init_data.init_data)
app.command()(backtest.backtest)

def main() -> None:
    """CLI 入口"""
    app()

if __name__ == "__main__":
    main()
```

### 3. `fetch.py` - 数据获取命令

提取内容：
- `fetch()` 命令函数
- `_run_fetch()` 核心逻辑

```python
"""数据获取命令"""
from typer import Argument, Option
from quant.cli.console import console

def fetch(
    data_type: str = Argument(..., help="数据类型"),
    start_date: str | None = Option(None, "--start", "-s"),
    end_date: str | None = Option(None, "--end", "-e"),
    source: str = Option("tushare", "--source", "-src"),
) -> None:
    """获取数据"""
    _run_fetch(data_type, start_date, end_date, source)

def _run_fetch(...) -> None:
    """执行数据获取逻辑"""
    # 从原 cli.py 迁移
```

> **导入说明**：所有子模块从 `quant.cli.console` 导入 `console`，而不是 `quant.cli`。

### 3. `scheduler.py` - 调度器管理命令

提取内容：
- `scheduler()` 命令函数
- `_run_scheduler()` 分发逻辑
- `_scheduler_start()` / `_scheduler_stop()` / `_scheduler_status()` / `_scheduler_run()` / `_scheduler_list()`
- `_is_process_running()` / `_get_scheduler_paths()` 辅助函数
- 常量 `_SCHEDULER_DIR`, `_PID_FILE`, `_LOG_FILE`, `_SCRIPT_FILE`

### 4. `db.py` - 数据库操作命令

提取内容：
- `db()` 命令函数

### 5. `init_data.py` - 历史数据初始化命令

提取内容：
- `init_data()` 命令函数
- 内部 `_init()` 异步函数

### 6. `version.py` - 版本和初始化命令

提取内容：
- `version()` 命令
- `init()` 命令

### 7. `backtest.py` - 回测命令（占位）

提取内容：
- `backtest()` 命令（当前为占位实现）

## 命令对照表

| 原命令 | 新模块 | 函数名 |
|--------|--------|--------|
| `version` | `version.py` | `version()` |
| `init` | `version.py` | `init()` |
| `db` | `db.py` | `db()` |
| `fetch` | `fetch.py` | `fetch()` |
| `scheduler` | `scheduler.py` | `scheduler()` |
| `init-data` | `init_data.py` | `init_data()` |
| `backtest` | `backtest.py` | `backtest()` |

## 共享资源

### `console` 对象

所有模块共享同一个 `Console` 实例。为了避免循环导入，`console` 定义在单独的 `console.py` 文件中：

```python
# 在子模块中导入
from quant.cli.console import console
```

> **重要**：不要从 `quant.cli` 或 `quant.cli.__init__` 导入 `console`，这会导致循环导入。

## 入口点兼容性

保持 `pyproject.toml` 中的入口点不变：

```toml
[project.scripts]
quant = "quant.cli:main"
```

Python 包的 `__init__.py` 会自动被解析，`quant.cli:main` 将指向 `quant/cli/__init__.py:main`。

## 迁移步骤

1. **创建目录**：创建 `quant/cli/` 目录
2. **创建 console.py**：提取共享的 `Console` 对象
3. **创建子模块**：迁移各命令代码到对应文件
   - `version.py` (~20 行)
   - `db.py` (~20 行)
   - `fetch.py` (~80 行)
   - `scheduler.py` (~200 行)
   - `init_data.py` (~30 行)
   - `backtest.py` (~10 行，占位)
4. **创建 __init__.py**：注册所有命令
5. **删除旧文件**：**必须删除** `quant/cli.py`，否则 Python 会优先导入文件而非包
6. **验证**：运行验证命令

### 验证命令

```bash
# 验证 CLI 正常工作
quant --help
quant version

# 运行测试
pytest

# 代码风格检查
black . && ruff check .
```

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 导入循环 | 使用延迟导入或重新组织模块 |
| 命令注册顺序 | 确保所有子模块在 `__init__.py` 中正确导入 |
| 测试覆盖 | 迁移后运行完整测试套件 |

## 验收标准

1. 所有现有 CLI 命令正常工作
2. `quant --help` 显示完整命令列表
3. 测试全部通过
4. 代码风格检查通过（black/ruff/mypy）

## 实现状态

**状态**: ✅ 已完成

**完成时间**: 2026-03-25

**实现文件**:
- `quant/cli/__init__.py` - 主入口
- `quant/cli/console.py` - 共享 Console
- `quant/cli/version.py` - 版本和初始化命令
- `quant/cli/db.py` - 数据库操作命令
- `quant/cli/fetch.py` - 数据获取命令
- `quant/cli/scheduler.py` - 调度器管理命令
- `quant/cli/init_data.py` - 历史数据初始化命令
- `quant/cli/backtest.py` - 回测命令（占位）
