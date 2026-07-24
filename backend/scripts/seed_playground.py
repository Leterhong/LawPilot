"""AI Playground 种子数据（幂等）。

- 为已启用的演示模型写入 ``model_pricing`` 单价（使「预计成本」开箱可用）。
- 写入几条示例法律 Prompt 到 ``prompt_library``（供 Prompt 测试 / 收藏演示）。
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.ai_center import AIModel
from app.models.playground import ModelPricing, PromptLibrary


SAMPLE_PRICING = {
    # model_name 后缀匹配；找不到则跳过
    "deepseek": (Decimal("0.00014"), Decimal("0.00028")),
    "gpt": (Decimal("0.01"), Decimal("0.03")),
    "claude": (Decimal("0.008"), Decimal("0.024")),
    "glm": (Decimal("0.0005"), Decimal("0.0005")),
    "qwen": (Decimal("0.0004"), Decimal("0.0004")),
    "kimi": (Decimal("0.0006"), Decimal("0.0006")),
    "gemini": (Decimal("0.0005"), Decimal("0.0015")),
}

SAMPLE_PROMPTS = [
    {
        "name": "法律分析通用模板",
        "category": "legal_analysis",
        "prompt": (
            "你是一位资深法律顾问。请对以下案件进行专业分析：\n\n"
            "【案情】\n{{case}}\n\n"
            "【相关法条】\n{{law}}\n\n"
            "【补充上下文】\n{{context}}\n\n"
            "请输出：争议焦点、法律适用、可能结果与建议。"
        ),
        "variables": [
            {"name": "case", "default": "", "desc": "案件描述"},
            {"name": "law", "default": "", "desc": "相关法条"},
            {"name": "context", "default": "", "desc": "补充上下文"},
        ],
        "tags": ["legal_analysis", "示例"],
    },
    {
        "name": "合同条款审查模板",
        "category": "contract_review",
        "prompt": (
            "请审查以下合同，识别风险条款并给出修改建议：\n\n"
            "【合同文本】\n{{document}}\n\n"
            "【审查重点】\n{{context}}"
        ),
        "variables": [
            {"name": "document", "default": "", "desc": "合同原文"},
            {"name": "context", "default": "", "desc": "审查重点"},
        ],
        "tags": ["contract_review", "示例"],
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # 1) 模型单价
        models = (await db.scalars(select(AIModel).where(AIModel.is_enabled == True))).all()  # noqa: E712
        pricing_count = 0
        for m in models:
            existing = (
                await db.scalars(select(ModelPricing).where(ModelPricing.model_id == m.id))
            ).first()
            if existing is not None:
                continue
            lower = (m.name or "").lower()
            price = None
            for key, (pin, pout) in SAMPLE_PRICING.items():
                if key in lower:
                    price = (pin, pout)
                    break
            if price is None:
                price = (Decimal("0.001"), Decimal("0.002"))  # 默认占位单价
            db.add(
                ModelPricing(
                    model_id=m.id,
                    price_in_per_1k=price[0],
                    price_out_per_1k=price[1],
                    currency="USD",
                    note="seed 占位单价，请在 AI 能力中心核对真实价格",
                )
            )
            pricing_count += 1
        await db.flush()

        # 2) 示例 Prompt 收藏
        prompt_count = 0
        for sp in SAMPLE_PROMPTS:
            exists = (
                await db.scalars(select(PromptLibrary).where(PromptLibrary.name == sp["name"]))
            ).first()
            if exists is not None:
                continue
            db.add(PromptLibrary(user_id=None, **sp))
            prompt_count += 1
        await db.commit()
        print(f"playground seed 完成：新增 model_pricing={pricing_count}，新增 prompt_library={prompt_count}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed())
