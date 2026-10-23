"""pytest 全局配置与共享夹具。

设计原则
--------
1. **不依赖外部服务**：单元测试在无 PostgreSQL / Redis / LLM 密钥的环境下也必须
   全量通过，保证 CI 与本地可重复执行。
2. **环境先于导入**：``app.core.config.settings`` 在模块导入时即实例化，因此必须
   在导入任何 ``app.*`` 模块之前设置环境变量，否则测试会读到开发机上的真实配置。
3. **确定性**：所有断言不依赖当前时间、随机数或网络。
"""
from __future__ import annotations

import os

# --- 必须在导入 app 之前完成环境准备 ---------------------------------------
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-0123456789")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000, http://localhost:3100")
# 显式清空真实模型密钥，确保测试永不发起真实计费调用
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("EMBEDDING_API_KEY", "")

import pytest  # noqa: E402
from app.core.config import settings  # noqa: E402


@pytest.fixture(scope="session")
def test_settings():
    """暴露一份已加载的配置单例，供断言环境隔离是否生效。"""
    return settings


@pytest.fixture
def sample_case():
    """构造一个内存中的 Case 对象（不落库），用于纯函数测试。"""
    from app.models.case import Case
    from app.models.enums import CaseTypeEnum

    return Case(
        title="房东无故扣押金",
        case_type=CaseTypeEnum.RENT,
        description="租期届满后房东以房屋有污渍为由拒退 8000 元押金，有租赁合同和转账记录。",
    )
