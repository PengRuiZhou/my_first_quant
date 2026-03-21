"""Pytest 配置"""

import pytest
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def test_settings():
    """测试用配置"""
    from quant.core.config import Settings

    return Settings(
        env="testing",
        debug=True,
        db__database="quant_test",
    )


@pytest.fixture(scope="session")
def test_db(test_settings):
    """测试数据库"""
    from quant.data.models import Base, get_engine

    engine = get_engine(test_settings.db.url)

    # 创建所有表
    Base.metadata.create_all(engine)

    yield engine

    # 清理
    Base.metadata.drop_all(engine)
