"""AI 能力中心初始化种子（幂等）。

默认**不再灌入任何演示 Provider / 模型**——用户应到 AI 能力中心自行配置真实大模型
（填入真实 API Key 后，`/api/ai/status` 才会返回 ``ai_configured=true``，前端才显示 AI
结果；否则仅提示「去配置模型」）。这与「不放入虚拟数据」的原则一致。

仅当库中已存在至少一个模型时，才补建：
- 18 条 AI 功能路由规则（按 feature 幂等，绑定到已有模型）；
- 2 个示例 Prompt 模板（绑定到已有模型）。

如需恢复旧演示数据（不推荐），设环境变量 ``SEED_DEMO=1`` 后再运行本脚本。

用法：
  PYTHONPATH=F:/falv/backend .venv_clean/Scripts/python.exe scripts/seed_ai_center.py
"""
import asyncio
import os

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.ai_center import (
    Provider,
    AIModel,
    RoutingRule,
    PromptTemplate,
    AI_FEATURES,
)
from app.services.ai_center_service import AICenterService
from app.schemas.ai_center import (
    ProviderCreate,
    AIModelCreate,
    RoutingRuleCreate,
    PromptTemplateCreate,
)

# 默认 False：不灌入演示 Provider/模型；设 SEED_DEMO=1 可恢复旧行为（不推荐）。
SEED_DEMO = os.environ.get("SEED_DEMO", "0") == "1"


async def _seed_demo(db, svc) -> None:
    """旧行为：建 1 个演示 Provider + 1 个演示模型（仅在 SEED_DEMO=1 时调用）。"""
    provider = await db.scalar(select(Provider).where(Provider.name == "硅基流动"))
    if provider is None:
        provider = await svc.create_provider(
            ProviderCreate(
                name="硅基流动",
                type="siliconflow",
                base_url="https://api.siliconflow.cn/v1",
                api_key=None,
                enabled=True,
                description="演示用 Provider 框架，请到 AI 能力中心填入真实 Key 后启用 AI 分析",
            )
        )
        print("创建 Provider:", provider.name)
    else:
        print("已存在 Provider:", provider.name)

    model = await db.scalar(select(AIModel).where(AIModel.name == "DeepSeek V3"))
    if model is None:
        model = await svc.create_model(
            AIModelCreate(
                name="DeepSeek V3",
                provider_id=provider.id,
                model_name="deepseek-chat",
                api_key=None,
                embedding_model="BAAI/bge-m3",
                vision_model="deepseek-vl",
                reranker_model="BAAI/bge-reranker-v2-m3",
                embedding_dim=1024,
                temperature=0.3,
                top_p=1.0,
                timeout=60,
                is_default=True,
                is_enabled=True,
                capabilities={
                    "chat": True,
                    "embedding": True,
                    "vision": True,
                    "streaming": True,
                    "json_mode": True,
                    "function_calling": True,
                    "web_search": False,
                    "reasoning": True,
                },
                advanced={"auto_retry": 3, "max_concurrency": 4, "rate_limit_rpm": 0, "rate_limit_tpm": 0},
            )
        )
        print("创建模型:", model.name)
    else:
        print("已存在模型:", model.name)
    return model


async def main() -> None:
    async with AsyncSessionLocal() as db:
        svc = AICenterService(db)

        if SEED_DEMO:
            model = await _seed_demo(db, svc)
        else:
            # 默认：不灌入演示 Provider/模型。若库里已无任何模型，则路由/Prompt 也无需建。
            model = await db.scalar(select(AIModel)) or await db.scalar(
                select(AIModel).where(AIModel.is_default == True)  # noqa: E712
            )
            if model is None:
                print(
                    "未检测到任何模型，跳过路由规则 / Prompt 模板种子。"
                    "请到 AI 能力中心添加真实 Provider 与模型后，再运行本脚本补齐路由与模板。"
                )
                return

        # 18 条路由规则（按 feature 幂等，绑定到 model）
        created = 0
        for feat in AI_FEATURES:
            existing = await db.scalar(
                select(RoutingRule).where(RoutingRule.feature == feat)
            )
            if existing is None:
                await svc.create_routing(
                    RoutingRuleCreate(
                        feature=feat,
                        model_id=model.id,
                        fallback_model_ids=[],
                        strategy="balanced",
                        auto_route=False,
                        enabled=True,
                    )
                )
                created += 1
        print(f"路由规则：新建 {created} 条（共 {len(AI_FEATURES)} 个功能）")

        # 示例 Prompt（按 key 幂等）
        demos = [
            ("legal_analysis", "法律分析", "你是一名专业律师，请分析以下案件：\n{case}\n\n给出：事实梳理、法律依据、风险评估。"),
            ("document_generation", "法律文书生成", "根据以下信息生成{doctype}：\n{info}\n要求结构完整、用语规范。"),
        ]
        pc = 0
        for key, name, content in demos:
            ex = await db.scalar(select(PromptTemplate).where(PromptTemplate.key == key))
            if ex is None:
                await svc.create_prompt(
                    PromptTemplateCreate(
                        key=key,
                        name=name,
                        content=content,
                        variables=[{"name": "case" if key == "legal_analysis" else "info", "desc": "输入内容"}],
                        enabled=True,
                        model_id=model.id,
                    ),
                    user=None,
                )
                pc += 1
        print(f"Prompt 模板：新建 {pc} 个")

        print("AI 能力中心初始化完成。")


if __name__ == "__main__":
    asyncio.run(main())
