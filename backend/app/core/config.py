"""应用配置中心。

集中管理所有环境变量与运行时配置。使用 pydantic-settings 从 .env 或
系统环境变量读取，保证类型安全与可验证。Phase 1 先建立通用配置骨架，
后续阶段（数据库、LLM、Embedding、安全）会在此追加相应字段。
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置对象。

    所有环境变量均带默认值，仅用于本地开发；生产环境必须通过 .env 或
    容器环境变量显式覆盖（尤其是 SECRET_KEY、数据库密码、LLM API Key）。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------
    # 通用
    # ---------------------------
    environment: Literal["development", "production", "test"] = "development"
    project_name: str = "LawPilot"
    api_v1_prefix: str = "/api/v1"

    # 是否对外暴露 /docs、/redoc 与 /openapi.json。
    # None = 自动策略（非生产开启、生产关闭）；显式设置则以此为准。
    # 生产环境如需保留文档，可设 EXPOSE_DOCS=true，但应在网关层加访问控制。
    expose_docs: bool | None = None

    # ---------------------------
    # 数据库
    # ---------------------------
    postgres_user: str = "lawpilot"
    postgres_password: str = "lawpilot_secret"
    postgres_db: str = "lawpilot"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: str = Field(
        default="postgresql+asyncpg://lawpilot:lawpilot_secret@db:5432/lawpilot"
    )

    # ---------------------------
    # Redis（预留）
    # ---------------------------
    # 说明：当前业务代码尚未接入 Redis，缓存与队列能力仍在规划中。
    # 编排文件保留该服务是为了后续引入异步任务（如批量 OCR、长报告生成）
    # 时无需改动部署形态。若追求最小部署面，可自行从 compose 中移除。
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: str = "redis://redis:6379/0"

    # ---------------------------
    # 后端服务
    # ---------------------------
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_workers: int = 1
    cors_origins: str = "http://localhost:3000,http://localhost:3100,http://localhost"

    # ---------------------------
    # 安全 / JWT
    # ---------------------------
    secret_key: str = "dev_secret_change_me"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"
    jwt_issuer: str = "lawpilot"
    jwt_audience: str = "lawpilot-client"

    # ---------------------------
    # AI 能力中心：API Key 加密密钥（Fernet）
    # 留空则基于 secret_key 派生（始终为合法的 32 字节 Fernet 密钥）
    # ---------------------------
    ai_encryption_key: str = ""

    # ---------------------------
    # 大模型（OpenAI Compatible）
    # ---------------------------
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = "sk-your-key-here"
    llm_model: str = "gpt-4o"
    llm_reasoning_model: str = "gpt-4o"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # ---------------------------
    # Embedding（BGE-M3）
    # ---------------------------
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = "sk-your-key-here"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # ---------------------------
    # Rerank（可选）
    # ---------------------------
    rerank_base_url: str = ""
    rerank_api_key: str = ""
    rerank_model: str = ""

    # ---------------------------
    # 向量检索参数
    # ---------------------------
    vector_similarity_top_k: int = 20
    keyword_top_k: int = 20
    rerank_top_k: int = 8

    # ---------------------------
    # 文件上传
    # ---------------------------
    max_upload_size_mb: int = 20
    upload_dir: str = "/app/uploads"
    allowed_extensions: str = ".pdf,.docx,.txt,.png,.jpg,.jpeg"

    # ---------------------------
    # 便捷属性
    # ---------------------------
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def docs_enabled(self) -> bool:
        """是否暴露交互式 API 文档。生产环境默认关闭，避免接口结构对外泄露。"""
        if self.expose_docs is not None:
            return self.expose_docs
        return not self.is_production

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的 CORS 来源解析为列表。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def ai_fernet_key(self) -> bytes:
        """返回合法的 32 字节 Fernet 密钥（URL-safe base64 编码）。

        优先使用 ``ai_encryption_key``；为空时基于 ``secret_key`` 派生。
        派生结果恒为 32 字节，符合 Fernet 要求。
        """
        raw = (self.ai_encryption_key or self.secret_key).encode("utf-8")
        return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())

    # ---------------------------
    # 生产环境自检
    # ---------------------------
    #: 已知的开发默认值，出现在生产环境中即为配置事故
    INSECURE_DEFAULTS: ClassVar[dict[str, str]] = {
        "secret_key": "dev_secret_change_me",
        "postgres_password": "lawpilot_secret",
    }

    def validate_for_production(self) -> list[str]:
        """返回生产环境下的致命配置问题列表（空列表表示通过）。

        这里只拦截"必然导致安全事故"的项，避免过度校验让部署变脆：
        - 使用文档里公开的开发默认密钥 / 密码；
        - SECRET_KEY 过短（HS256 下低于 32 字符不足以保证抗暴力破解）。
        """
        problems: list[str] = []
        if not self.is_production:
            return problems

        for field_name, insecure in self.INSECURE_DEFAULTS.items():
            if getattr(self, field_name) == insecure:
                problems.append(f"{field_name.upper()} 仍为开发默认值「{insecure}」，必须覆盖")

        if len(self.secret_key) < 32:
            problems.append("SECRET_KEY 长度不足 32 字符，请使用 openssl rand -hex 32 生成")

        if "*" in self.cors_origin_list:
            problems.append("CORS_ORIGINS 不允许配置通配符 *（与 allow_credentials 冲突且不安全）")

        return problems


@lru_cache
def get_settings() -> Settings:
    """返回全局配置单例（带缓存）。

    使用 lru_cache 保证配置只解析一次；测试环境下可通过清空缓存刷新。
    """
    return Settings()


# 全局可导入的配置实例
settings = get_settings()
