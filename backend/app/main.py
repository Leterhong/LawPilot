"""LawPilot 后端应用入口（ASGI）。

职责：
- 创建 FastAPI 应用实例
- 配置 CORS、生命周期（启动/关闭）
- 装配 API 路由（/api/v1）并补全 OpenAPI 安全方案（Bearer JWT）
- 提供根路径与全局健康检查
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api.ai_center import router as ai_center_router
from app.api.case_center import router as case_center_router
from app.api.laws import router as laws_router
from app.api.legal_cases import router as legal_cases_router
from app.api.research import router as research_router
from app.api.v1 import api_router
from app.contract.router import router as contract_router
from app.core.config import settings
from app.core.database import init_db
from app.playground.router import router as playground_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lawpilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动：生产环境先做配置自检（不安全则拒绝启动），开发环境自动建表。
    关闭：释放引擎连接池。
    """
    logger.info("LawPilot 后端启动中… 环境=%s", settings.environment)

    problems = settings.validate_for_production()
    if problems:
        detail = "；".join(problems)
        logger.error("生产环境配置自检未通过，拒绝启动：%s", detail)
        raise RuntimeError(f"生产环境配置不安全：{detail}")

    if settings.environment == "development":
        try:
            await init_db()
            logger.info("开发环境数据库表已就绪")
        except Exception as exc:  # noqa: BLE001
            logger.warning("自动建表跳过：%s", exc)
    yield
    logger.info("LawPilot 后端正在关闭…")
    from app.core.database import engine

    await engine.dispose()


# OpenAPI 标签描述
TAGS_METADATA = [
    {"name": "auth", "description": "注册与登录，获取 JWT"},
    {"name": "users", "description": "当前用户资料"},
    {"name": "cases", "description": "案件 CRUD 与案件内消息"},
    {"name": "evidence", "description": "证据上传（OCR）与规划证据"},
    {"name": "documents", "description": "法律文书生成"},
    {"name": "roadmaps", "description": "办理路线图与步骤"},
    {"name": "tasks", "description": "待办任务"},
    {"name": "history", "description": "案件时间线"},
    {"name": "legal", "description": "法律检索（Phase 5 增强为混合检索）"},
    {"name": "laws", "description": "法律搜索引擎（Law Search）：搜索 / 详情 / 推荐 / 历史"},
    {"name": "cases-center", "description": "案件中心（Case Center）：案件卡片 / 分析 / 证据 / 文书 / 任务 / 时间线 / 备注"},
    {"name": "legal-cases", "description": "案例智能搜索（Legal Case Search）：搜索 / 过滤 / 详情 / 相似案例 / 收藏"},
    {"name": "research", "description": "法律研究中心（Legal Research Center）：检索 / 详情 / 推荐（法规·司法解释·部门规章·地方性法规·办事指南·政策文件）"},
    {"name": "ai-center", "description": "AI 能力中心（AI Capability Center）：Provider / 模型 / 路由 / Prompt / Token 统计 / 日志 / 健康检测（仅超级管理员）"},
    {"name": "playground", "description": "AI Playground（AI 模型测试中心）：单模型测试 / 多模型对比 / Prompt 测试 / 模型评测 / AI 路由测试 / 历史 / 收藏 / 一键发布（仅登录用户，发布限超管）"},
    {"name": "contracts", "description": "合同智能中心（Contract Intelligence Center）：合同上传（OCR/文本提取）/ 自动分类 / 列表 / 详情 / 删除（Step2）；AI 分析 / 报告 / 提醒 / 模板 等后续步骤追加"},
    {"name": "evidence-center", "description": "智能证据中心（Evidence Intelligence Center）：证据上传（批量/落盘）/ 列表 / 详情 / 取回原件 / 删除（Step2）；OCR 与 AI 分析 / 证据链 / 报告 等后续步骤追加"},
    {"name": "health", "description": "健康检查"},
]

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description=(
        "让每个人都拥有自己的 AI 法律办事助手 —— LawPilot 后端 API。"
        "提供认证、案件管理、证据上传、文书生成、办理路线图与法律检索。"
    ),
    lifespan=lifespan,
    openapi_tags=TAGS_METADATA,
    # 生产环境默认不暴露文档（见 Settings.docs_enabled），
    # 如需开启请显式设置 EXPOSE_DOCS=true 并在网关层做访问控制。
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)


def custom_openapi() -> dict:
    """定制 OpenAPI：加入 Bearer JWT 安全方案，并对受保护路由标注。"""
    if getattr(app, "openapi_schema", None):
        return app.openapi_schema  # type: ignore[return-value]
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=TAGS_METADATA,
    )
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    # 登录/注册/健康检查/根路径/法律检索无需鉴权
    public_paths = {
        "/",
        "/health",
        "/api/v1/health",
        "/api/v1/legal",
        "/api/laws/search",
        "/api/laws/detail/{law_id}",
        "/api/laws/recommend",
        "/api/legal-cases/search",
        "/api/legal-cases/filter",
        "/api/legal-cases/{case_id}",
        "/api/research/search",
        "/api/research/document/{doc_id}",
        "/api/research/recommend",
    }
    for path, operations in schema["paths"].items():
        if path.startswith("/api/v1/auth") or path in public_paths:
            continue
        for operation in operations.values():
            operation.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


# ---------------------------
# CORS 配置
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# 路由挂载
# ---------------------------
app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(laws_router)
app.include_router(case_center_router)
app.include_router(legal_cases_router)
app.include_router(research_router)
app.include_router(ai_center_router)
app.include_router(playground_router)
app.include_router(contract_router)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """根路径欢迎信息。"""
    return {
        "product": settings.project_name,
        "tagline": "你的AI法律办事助手",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """全局健康检查（无需前缀，供网关探活）。"""
    return {"status": "ok", "service": "lawpilot-backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.environment == "development",
    )
