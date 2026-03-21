.PHONY: install dev test lint format clean db-create db-reset

# 安装
install:
	pip install -e .

dev:
	pip install -e ".[dev]"

all:
	pip install -e ".[all]"

# 测试
test:
	pytest

test-cov:
	pytest --cov=quant --cov-report=html

# 代码质量
lint:
	ruff check .

format:
	black .

format-check:
	black --check .

type-check:
	mypy quant

# 数据库
db-create:
	python -c "from quant.cli import app; app(['db', 'create'])"

db-reset:
	python -c "from quant.cli import app; app(['db', 'drop'])"
	python -c "from quant.cli import app; app(['db', 'create'])"

# 清理
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf htmlcov/ .coverage
