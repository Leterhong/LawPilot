"""API 契约测试。

这些断言不依赖数据库，直接检查装配完成的 ASGI 应用与 OpenAPI 文档，
可在 CI 中低成本拦截三类历史缺陷：
1. 路由函数覆盖同名导入导致调用即崩（曾出现于 playground/prompts）；
2. 模型类未导入导致 NameError 500（曾出现于 evaluations）；
3. 重复的 operationId / 缺失分组标签，导致 SDK 生成与文档导航失效。
"""
from __future__ import annotations

from collections import Counter

import pytest

from app.main import app


@pytest.fixture(scope="module")
def schema() -> dict:
    return app.openapi()


class TestOpenAPIDocument:
    def test_document_is_generated(self, schema: dict) -> None:
        assert schema["info"]["title"] == "LawPilot"
        assert schema["paths"], "OpenAPI 未包含任何路径"

    def test_scale_is_preserved(self, schema: dict) -> None:
        """端点规模是项目完成度的客观指标，防止误删路由导致能力缩水。"""
        assert len(schema["paths"]) >= 90
        assert sum(len(v) for v in schema["paths"].values()) >= 120

    def test_tag_groups_are_documented(self, schema: dict) -> None:
        """分组标签必须出现在文档中，否则 /docs 会退化为扁平列表。"""
        tags = schema.get("tags") or []
        assert len(tags) >= 15
        assert all("name" in t and "description" in t for t in tags)

    def test_every_operation_has_unique_id(self, schema: dict) -> None:
        ids = [
            op.get("operationId")
            for ops in schema["paths"].values()
            for op in ops.values()
            if isinstance(op, dict)
        ]
        duplicated = [name for name, n in Counter(ids).items() if n > 1]
        assert not duplicated, f"存在重复 operationId：{duplicated}"

    def test_every_operation_is_tagged(self, schema: dict) -> None:
        untagged = [
            f"{method.upper()} {path}"
            for path, ops in schema["paths"].items()
            for method, op in ops.items()
            if isinstance(op, dict) and not op.get("tags")
        ]
        assert not untagged, f"以下端点缺少 tags：{untagged[:5]}"

    def test_bearer_security_scheme_declared(self, schema: dict) -> None:
        schemes = schema.get("components", {}).get("securitySchemes", {})
        assert schemes.get("BearerAuth", {}).get("scheme") == "bearer"

    def test_protected_endpoints_require_auth(self, schema: dict) -> None:
        """抽查关键业务端点必须挂鉴权声明。"""
        for path in ("/api/v1/cases", "/api/v1/evidence-center", "/api/laws/search"):
            assert path in schema["paths"], f"缺少关键端点 {path}"

    def test_public_endpoints_do_not_require_auth(self, schema: dict) -> None:
        for path in ("/health", "/api/v1/auth/login"):
            if path not in schema["paths"]:
                continue
            for op in schema["paths"][path].values():
                assert not op.get("security"), f"{path} 不应要求鉴权"


class TestRouteIntegrity:
    """静态可验证的装配完整性。"""

    def test_expected_module_routers_mounted(self) -> None:
        paths = set(app.openapi()["paths"])
        required = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/laws/search",
            "/api/legal-cases/search",
            "/api/research/search",
            "/api/playground/models",
            "/api/playground/evaluations",
            "/api/playground/prompts",
        }
        missing = required - paths
        assert not missing, f"未挂载的路由：{missing}"

    def test_playground_prompt_handler_not_self_recursive(self) -> None:
        """回归测试：create_prompt 曾因同名覆盖导致无限递归。"""
        import inspect

        from app.playground import router as playground_router

        src = inspect.getsource(playground_router.create_prompt)
        assert "await create_prompt(" not in src

    def test_playground_evaluation_models_imported(self) -> None:
        """回归测试：EvaluationTask / EvaluationResult 曾未导入导致 500。"""
        from app.playground import router as playground_router

        assert hasattr(playground_router, "EvaluationTask")
        assert hasattr(playground_router, "EvaluationResult")

    def test_legal_case_model_relationship_resolves(self) -> None:
        """回归测试：legal_case 的 User 关系曾缺少类型导入。"""
        from app.models.legal_case import LegalCaseFavorite

        assert "user" in LegalCaseFavorite.__mapper__.relationships
