"""AI Playground 端到端 API 冒烟（Step 2）。

用 ASGITransport 直接驱动 app，验证：
1. 模型选择器列表（/models）200
2. 单模型测试（/test）200 且优雅落库（演示 fake key → 不崩溃，status=error）
3. 历史（/history）200 且含该会话
4. 一键发布（/publish）超管 200；非超管 403
5. 路由规则（/routing）随发布更新
6. Prompt 收藏（/prompts）200（种子数据）
7. 数据集 + 评测（/datasets, /evaluate）200（fake key 下不崩溃）
"""
from __future__ import annotations

import asyncio
import httpx
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.user import User


async def main() -> None:
    # 准备：超管 + 普通用户
    async with AsyncSessionLocal() as db:
        admin = (await db.scalars(select(User).where(User.email == "admin@lawpilot.dev"))).first()
        admin_token = create_access_token(str(admin.id))
        nu = User(email="pg_normal@lawpilot.dev", hashed_password=hash_password("Test1234"),
                  display_name="normal", is_active=True, is_superuser=False)
        db.add(nu)
        await db.commit()
        await db.refresh(nu)
        normal_token = create_access_token(str(nu.id))

    admin_h = {"Authorization": f"Bearer {admin_token}"}
    normal_h = {"Authorization": f"Bearer {normal_token}"}
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        # 1) 模型列表
        r = await c.get("/api/playground/models", headers=admin_h)
        assert r.status_code == 200, r.text
        models = r.json()
        assert models, "模型列表为空"
        mid = models[0]["id"]
        print(f"[1] /models 200，模型数={len(models)}，取 {models[0]['name']}")

        # 2) 单模型测试（fake key 优雅失败）
        r = await c.post("/api/playground/test",
                         json={"model_id": mid, "user_prompt": "用一句话解释合同效力"},
                         headers=admin_h)
        assert r.status_code == 200, r.text
        sess = r.json()
        assert "id" in sess, "测试会话未返回 id"
        print(f"[2] /test 200，session.status={sess['status']}（fake key 预期 error，但无崩溃）✅")

        # 3) 历史
        r = await c.get("/api/playground/history", headers=admin_h)
        assert r.status_code == 200, r.text
        hist = r.json()
        assert any(h["id"] == sess["id"] for h in hist), "历史未包含刚创建的会话"
        print(f"[3] /history 200，条数={len(hist)}，含本次会话 ✅")

        # 4) 发布：超管 200
        r = await c.post("/api/playground/publish",
                         json={"feature": "legal_analysis", "model_id": mid, "note": "playground 自动发布"},
                         headers=admin_h)
        assert r.status_code == 200, r.text
        pub = r.json()
        print(f"[4a] 超管 /publish 200，feature={pub['feature']} → model={pub['to_model_id']} ✅")

        # 4b) 发布：非超管 403
        r = await c.post("/api/playground/publish",
                         json={"feature": "legal_analysis", "model_id": mid},
                         headers=normal_h)
        assert r.status_code == 403, r.text
        print("[4b] 非超管 /publish 403 ✅")

        # 5) 路由随发布更新
        r = await c.get("/api/playground/routing", headers=admin_h)
        assert r.status_code == 200, r.text
        routing = {x["feature"]: x["model_id"] for x in r.json()}
        assert routing.get("legal_analysis") == mid, "路由未更新"
        print(f"[5] /routing 200，legal_analysis 当前指向 {routing['legal_analysis']} ✅")

        # 6) Prompt 收藏
        r = await c.get("/api/playground/prompts", headers=admin_h)
        assert r.status_code == 200, r.text
        print(f"[6] /prompts 200，收藏数={len(r.json())} ✅")

        # 7) 数据集 + 评测（fake key 下不崩溃）
        ds = await c.post("/api/playground/datasets",
                          params={"name": "冒烟测试集", "category": "legal_analysis", "is_public": False},
                          json=[{"input": "什么是违约金？", "expected": "违约责任相关", "context": ""}],
                          headers=admin_h)
        assert ds.status_code == 201, ds.text
        dsid = ds.json()["id"]
        ev = await c.post("/api/playground/evaluate",
                          json={"name": "冒烟评测", "model_ids": [mid], "dataset_id": dsid,
                                "feature": "legal_analysis"},
                          headers=admin_h)
        assert ev.status_code == 200, ev.text
        task = ev.json()
        print(f"[7] /datasets 201 + /evaluate 200，task.status={task['status']}（fake key 下任务完成不崩溃）✅")

    print("\nALL GREEN ✅ AI Playground 后端 Step 2 端到端验证通过")


if __name__ == "__main__":
    asyncio.run(main())
