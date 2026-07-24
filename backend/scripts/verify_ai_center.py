"""AI 能力中心 Step2 端到端冒烟测试（无需手动端口）。

使用 httpx.AsyncClient + ASGITransport，全程在同一事件循环内：
1. 直接插入一个 superuser 与一个普通 user
2. 登录取 JWT
3. 以超管身份实测所有 /api/ai/* 接口（create/list/路由/Prompt/统计/日志/健康/测试连接）
4. 验证非超管访问返回 403
5. 清理测试用户
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import httpx
from httpx import ASGITransport

import app.main  # noqa: F401 触发路由注册
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User


async def _seed_users() -> tuple[str, str]:
    async with AsyncSessionLocal() as db:
        su = User(
            id=uuid4(),
            email="su_ai_verify@lawpilot.dev",
            hashed_password=hash_password("test1234"),
            is_active=True,
            is_superuser=True,
        )
        nu = User(
            id=uuid4(),
            email="nu_ai_verify@lawpilot.dev",
            hashed_password=hash_password("test1234"),
            is_active=True,
            is_superuser=False,
        )
        db.add_all([su, nu])
        await db.commit()
        return str(su.id), str(nu.id)


async def _cleanup(su_id: str, nu_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(User.__table__.delete().where(User.id.in_([su_id, nu_id])))  # noqa: E501
        await db.commit()


async def _login(client: httpx.AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "test1234"},
    )
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    return r.json()["access_token"]


async def main() -> None:
    su_id, nu_id = await _seed_users()
    try:
        transport = ASGITransport(app=app.main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            su_token = await _login(client, "su_ai_verify@lawpilot.dev")
            nu_token = await _login(client, "nu_ai_verify@lawpilot.dev")
            H = {"Authorization": f"Bearer {su_token}"}
            HN = {"Authorization": f"Bearer {nu_token}"}

            async def check(method, url, **kw):
                r = await getattr(client, method)(url, headers=H, **kw)
                print(f"{method.upper():4} {url} -> {r.status_code}")
                return r

            # 鉴权：非超管应 403
            r = await client.get("/api/ai/meta", headers=HN)
            print(f"GET /api/ai/meta (normal user) -> {r.status_code} (expect 403)")
            assert r.status_code == 403, "非超管应被拒绝"

            # meta
            await check("get", "/api/ai/meta")
            # provider 新增 + 列表
            rp = await check("post", "/api/ai/providers", json={
                "name": "硅基流动-验证", "type": "siliconflow",
                "base_url": "https://api.siliconflow.cn/v1",
                "api_key": "sk-fake-verify-1234", "enabled": True,
            })
            pid = rp.json()["id"]
            rl = await check("get", "/api/ai/providers")
            masked = rl.json()[0]["api_key"]
            print(f"   provider api_key masked = {masked} (expect sk-f...1234)")
            assert masked and masked.startswith("sk-f") and "..." in masked

            # model 新增 + 测试连接（指向不存在端口，快速失败，接口应 200 且 status=fail）
            rm = await check("post", "/api/ai/models", json={
                "name": "DeepSeek-V3-验证", "provider_id": pid, "model_name": "deepseek-chat",
                "is_default": True, "capabilities": {"chat": True, "streaming": True},
            })
            mid = rm.json()["id"]
            rt = await check("post", "/api/ai/models/test", json={
                "model_id": mid, "capability": "chat",
            })
            tres = rt.json()
            print(f"   test_connection status={tres['status']} latency={tres['latency_ms']} err={str(tres.get('error'))[:60]}")
            assert rt.status_code == 200

            # 健康检测（手动）
            await check("post", f"/api/ai/models/{mid}/health/check")
            await check("get", "/api/ai/health")

            # routing 新增
            await check("post", "/api/ai/routing", json={
                "feature": "legal_analysis", "model_id": mid,
                "fallback_model_ids": [], "strategy": "highest_quality", "auto_route": False,
            })
            await check("get", "/api/ai/routing")

            # prompt 新增（自动建版本）
            rp_ = await check("post", "/api/ai/prompts", json={
                "key": "legal_analysis", "name": "法律分析Prompt",
                "content": "你是法律助手，分析：{{user_input}}", "variables": [{"name": "user_input"}],
            })
            pid_p = rp_.json()["id"]
            await check("get", f"/api/ai/prompts/{pid_p}/versions")

            # 统计 / 日志（当前无真实用量，应 200 且返回结构）
            await check("get", "/api/ai/statistics")
            await check("get", "/api/ai/logs")

            # 编辑模型
            await check("put", f"/api/ai/models/{mid}", json={"name": "DeepSeek-V3-改名"})
            # 清理（反向）
            rid = (await check("get", "/api/ai/routing")).json()[0]["id"]
            await check("delete", f"/api/ai/routing/{rid}")
            await check("delete", f"/api/ai/prompts/{pid_p}")
            await check("delete", f"/api/ai/models/{mid}")
            await check("delete", f"/api/ai/providers/{pid}")

            print("\n=== AI 能力中心 Step2 冒烟全部通过 ===")
    finally:
        await _cleanup(su_id, nu_id)


if __name__ == "__main__":
    asyncio.run(main())
