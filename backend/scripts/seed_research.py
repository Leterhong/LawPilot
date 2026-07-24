"""法律研究中心（Legal Research Center）示例数据种子脚本。

使用方法（在 backend 目录下，使用项目虚拟环境）：
    .venv_clean/Scripts/python.exe scripts/seed_research.py

说明：
- 仅插入示例数据，便于前端联调与演示；可重复执行（已存在则跳过）。
- embedding 与 AI 字段（ai_explanation / ai_summary 等）留空，
  由检索/推荐服务在用户请求时按需调用 LLM 懒生成（graceful degradation）。
- 语义检索在 embedding 为空时回退到 tsvector 全文检索 + 词法 reranker。
"""
from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.research import (
    LegalDocument,
    JudicialInterpretation,
    DepartmentRule,
    LocalRegulation,
    Guideline,
    Policy,
)

# (model, kwargs) —— kwargs 不含 id（UUIDMixin 自动生成）
SEED: list[tuple[type, dict]] = [
    # ---------------- legal_documents：覆盖 法律 / 行政法规 / 指导性案例 / 典型案例 ----------------
    (
        LegalDocument,
        dict(
            title="中华人民共和国民法典",
            doc_number="主席令第四十五号",
            category="法律",
            full_text=(
                "第一条 为了保护民事主体的合法权益，调整民事关系，维护社会和经济秩序，"
                "适应中国特色社会主义发展要求，弘扬社会主义核心价值观，根据宪法，制定本法。\n"
                "第四百六十四条 合同是民事主体之间设立、变更、终止民事法律关系的协议。\n"
                "第一千零六十四条 夫妻双方共同签名或者夫妻一方事后追认等共同意思表示所负的债务，"
                "以及夫妻一方在婚姻关系存续期间以个人名义为家庭日常生活需要所负的债务，属于夫妻共同债务。"
            ),
            summary_one_line="调整平等主体之间人身关系和财产关系的基础性法律。",
            core_points=["确立民事主体平等原则", "系统整合原有民事单行法", "强化对人格权与产权的保护"],
            scope="中华人民共和国境内所有平等主体之间的民事活动。",
            common_misconceptions=["以为民法典只管合同", "误以为婚姻法已独立存在（已并入）"],
            publish_date=date(2020, 5, 28),
            effective_date=date(2021, 1, 1),
            expiry_date=None,
            is_current=True,
            source="全国人民代表大会",
            level="法律",
            region=None,
            issuing_authority="全国人民代表大会",
            keywords=["民法典", "民事", "合同", "人格权", "产权"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    (
        LegalDocument,
        dict(
            title="中华人民共和国劳动合同法",
            doc_number="主席令第六十五号",
            category="法律",
            full_text=(
                "第一条 为了完善劳动合同制度，明确劳动合同双方当事人的权利和义务，"
                "保护劳动者的合法权益，构建和发展和谐稳定的劳动关系，制定本法。\n"
                "第十条 建立劳动关系，应当订立书面劳动合同。已建立劳动关系，未同时订立书面劳动合同的，"
                "应当自用工之日起一个月内订立书面劳动合同。"
            ),
            summary_one_line="规范用人单位与劳动者之间劳动合同关系的基本法律。",
            core_points=["书面劳动合同强制", "经济补偿金制度", "试用期与解雇保护"],
            scope="中华人民共和国境内企业、个体经济组织、民办非企业单位等组织与劳动者。",
            common_misconceptions=["试用期可以不签合同", "辞职无需提前通知"],
            publish_date=date(2007, 6, 29),
            effective_date=date(2008, 1, 1),
            expiry_date=None,
            is_current=True,
            source="全国人民代表大会",
            level="法律",
            region=None,
            issuing_authority="全国人民代表大会",
            keywords=["劳动合同", "劳动者", "试用期", "经济补偿"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    (
        LegalDocument,
        dict(
            title="安全生产许可证条例",
            doc_number="国务院令第397号",
            category="行政法规",
            full_text=(
                "第一条 为了严格规范安全生产条件，进一步加强安全生产监督管理，"
                "防止和减少生产安全事故，根据《中华人民共和国安全生产法》的有关规定，制定本条例。\n"
                "第二条 国家对矿山企业、建筑施工企业和危险化学品、烟花爆竹、民用爆炸物品生产企业"
                "（以下统称企业）实行安全生产许可制度。"
            ),
            summary_one_line="对高危行业实行安全生产许可制度的行政法规。",
            core_points=["高危行业许可前置", "未取得许可证不得从事生产", "许可证有效期管理"],
            scope="全国范围内矿山、建筑施工、危险化学品等高危生产企业。",
            common_misconceptions=["以为所有企业都要办安全生产许可证", "许可证长期有效无需续期"],
            publish_date=date(2004, 1, 13),
            effective_date=date(2004, 1, 13),
            expiry_date=None,
            is_current=True,
            source="国务院",
            level="行政法规",
            region=None,
            issuing_authority="国务院",
            keywords=["安全生产", "许可", "高危行业", "行政法规"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    (
        LegalDocument,
        dict(
            title="指导案例24号：荣宝英诉王阳、永诚财产保险股份有限公司江阴支公司机动车交通事故责任纠纷案",
            doc_number="指导性案例24号",
            category="指导性案例",
            full_text=(
                "关键词：民事 交通事故 过错责任 比例因果关系\n"
                "裁判要点：交通事故的受害人没有过错，其体质状况对损害后果的影响不属于可以减轻侵权人"
                "责任的法定情形。侵权人主张受害人自身体质状况（如骨质疏松）减轻责任的，人民法院不予支持。"
            ),
            summary_one_line="明确“受害人特殊体质不减轻侵权人责任”的裁判规则。",
            core_points=["个人体质不属于过错", "损害参与度的鉴定意见不当然减轻赔偿", "适用过错责任原则"],
            scope="机动车交通事故责任纠纷审理参考。",
            common_misconceptions=["以为老人/体弱者获赔应打折", "以为鉴定意见的“参与度”直接定责"],
            publish_date=date(2014, 1, 26),
            effective_date=date(2014, 1, 26),
            expiry_date=None,
            is_current=True,
            source="最高人民法院",
            level="指导性案例",
            region=None,
            issuing_authority="最高人民法院",
            keywords=["指导案例", "交通事故", "过错责任", "损害赔偿"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    (
        LegalDocument,
        dict(
            title="典型案例：某网络购物合同纠纷案（格式条款提示义务）",
            doc_number="典型案例-网购-001",
            category="典型案例",
            full_text=(
                "基本案情：消费者在某平台购买商品，经营者以“一经售出概不退换”的格式条款拒绝退货。\n"
                "裁判要旨：经营者未尽到格式条款提示、说明义务的，该条款不成为合同内容；"
                "消费者依法享有七日无理由退货权利。"
            ),
            summary_one_line="明确经营者未提示格式条款不生效、消费者享无理由退货。",
            core_points=["格式条款提示义务", "七日无理由退货", "不公平条款无效"],
            scope="网络购物消费纠纷参考。",
            common_misconceptions=["以为“概不退换”字样绝对有效", "以为定制商品一律不适用无理由退货"],
            publish_date=date(2023, 3, 15),
            effective_date=date(2023, 3, 15),
            expiry_date=None,
            is_current=True,
            source="最高人民法院",
            level="典型案例",
            region=None,
            issuing_authority="最高人民法院",
            keywords=["典型案例", "网购", "格式条款", "消费者权益"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    # ---------------- judicial_interpretations ----------------
    (
        JudicialInterpretation,
        dict(
            title="最高人民法院关于适用《中华人民共和国民法典》总则编若干问题的解释",
            doc_number="法释〔2022〕6号",
            category="司法解释",
            full_text=(
                "第一条 民法所称的“以上”“以下”“以内”“届满”，包括本数；所称的“不满”“超过”“以外”，不包括本数。\n"
                "第二条 民事法律行为有效应当具备相应民事行为能力、意思表示真实、不违反法律行政法规的强制性规定"
                "和公序良俗。"
            ),
            summary_one_line="对民法典总则编基本概念与法律行为效力规则的细化解释。",
            core_points=["期间与数量术语解释", "法律行为效力要件", "习惯的法源地位"],
            scope="全国法院审理民事案件适用。",
            common_misconceptions=["以为“以上”不含本数", "以为所有强制性规定均导致合同无效"],
            publish_date=date(2022, 2, 24),
            effective_date=date(2022, 3, 1),
            expiry_date=None,
            is_current=True,
            source="最高人民法院",
            level="司法解释",
            region=None,
            issuing_authority="最高人民法院",
            keywords=["民法典", "总则", "司法解释", "法律行为"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    (
        JudicialInterpretation,
        dict(
            title="最高人民法院关于审理劳动争议案件适用法律问题的解释（一）",
            doc_number="法释〔2020〕26号",
            category="司法解释",
            full_text=(
                "第一条 劳动者与用人单位之间发生的下列纠纷，属于劳动争议：\n"
                "（一）确认劳动关系；（二）订立、履行、变更、解除和终止劳动合同……\n"
                "第四十四条 因用人单位作出的开除、除名、辞退、解除劳动合同、减少劳动报酬、计算劳动者"
                "工作年限等决定而发生的劳动争议，用人单位负举证责任。"
            ),
            summary_one_line="系统整合劳动争议案件审理规则，明确举证分配。",
            core_points=["劳动争议受案范围", "用人单位举证责任倒置", "仲裁与诉讼衔接"],
            scope="全国法院劳动争议案件审理。",
            common_misconceptions=["以为所有劳动纠纷都可直接起诉（需先仲裁）", "以为劳动者对一切事实举证"],
            publish_date=date(2020, 12, 29),
            effective_date=date(2021, 1, 1),
            expiry_date=None,
            is_current=True,
            source="最高人民法院",
            level="司法解释",
            region=None,
            issuing_authority="最高人民法院",
            keywords=["劳动争议", "司法解释", "举证责任", "仲裁"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    # ---------------- department_rules ----------------
    (
        DepartmentRule,
        dict(
            title="市场监督管理行政处罚程序规定",
            doc_number="国家市场监督管理总局令第2号",
            category="部门规章",
            full_text=(
                "第一条 为了规范市场监督管理行政处罚行为，保障市场监管部门依法实施行政处罚，"
                "保护自然人、法人和其他组织的合法权益，根据行政处罚法等法律、行政法规，制定本规定。\n"
                "第二十条 办案人员应当依法收集证据，严禁以非法手段收集证据。"
            ),
            summary_one_line="规范市场监管部门行政处罚办案程序的部门规章。",
            core_points=["管辖与立案", "调查取证规范", "告知与听证程序"],
            scope="各级市场监督管理部门行政处罚办案。",
            common_misconceptions=["以为简易程序无需告知", "以为所有案件都需听证"],
            publish_date=date(2018, 12, 21),
            effective_date=date(2019, 4, 1),
            expiry_date=None,
            is_current=True,
            source="国家市场监督管理总局",
            level="部门规章",
            region=None,
            issuing_authority="国家市场监督管理总局",
            keywords=["行政处罚", "市场监管", "部门规章", "程序"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    # ---------------- local_regulations ----------------
    (
        LocalRegulation,
        dict(
            title="上海市生活垃圾管理条例",
            doc_number="上海市人民代表大会公告第11号",
            category="地方性法规",
            full_text=(
                "第一条 为了加强生活垃圾管理，改善人居环境，维护生态安全，保障经济社会可持续发展，"
                "根据《中华人民共和国固体废物污染环境防治法》等法律、行政法规，结合本市实际，制定本条例。\n"
                "第二十四条 产生生活垃圾的单位和个人是生活垃圾分类投放的责任主体，应当将生活垃圾分别投放"
                "至相应的收集容器。"
            ),
            summary_one_line="全国首部强制垃圾分类的地方性法规。",
            core_points=["强制分类投放", "单位和个人责任", "不分类可处罚"],
            scope="上海市行政区域。",
            common_misconceptions=["以为只有上海有垃圾分类法规", "以为单位无需分类"],
            publish_date=date(2019, 1, 31),
            effective_date=date(2019, 7, 1),
            expiry_date=None,
            is_current=True,
            source="上海市人民代表大会",
            level="地方性法规",
            region="上海市",
            issuing_authority="上海市人民代表大会常务委员会",
            keywords=["垃圾分类", "上海", "地方立法", "环保"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    # ---------------- guidelines ----------------
    (
        Guideline,
        dict(
            title="商标注册申请办事指南",
            doc_number="商标办事指南-001",
            category="办事指南",
            full_text=(
                "一、申请条件：自然人、法人或其他组织在生产经营活动中，对其商品或者服务需要取得商标专用权的，"
                "应当向商标局申请商标注册。\n"
                "二、所需材料：商标注册申请书、申请人身份证明、商标图样、商品/服务分类清单。\n"
                "三、办理渠道：中国商标网网上服务系统或商标业务受理窗口。\n"
                "四、审查周期：形式审查约1个月，实质审查约4—6个月。"
            ),
            summary_one_line="商标注册申请的材料、渠道与流程指引。",
            core_points=["申请主体与条件", "材料清单", "网办与窗口办理", "审查周期"],
            scope="拟申请商标注册的自然人、法人、其他组织。",
            common_misconceptions=["以为个人不能注册商标（可，但需经营资质）", "以为注册即永久有效（需续展）"],
            publish_date=date(2023, 1, 1),
            effective_date=date(2023, 1, 1),
            expiry_date=None,
            is_current=True,
            source="国家知识产权局商标局",
            level="办事指南",
            region=None,
            issuing_authority="国家知识产权局",
            keywords=["商标", "注册", "办事指南", "知识产权"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    (
        Guideline,
        dict(
            title="不动产登记办事指南（转移登记）",
            doc_number="不动产办事指南-002",
            category="办事指南",
            full_text=(
                "一、适用情形：买卖、赠与、继承、互换等导致不动产权利转移的，办理转移登记。\n"
                "二、所需材料：不动产登记申请书、申请人身份证明、不动产权属证书、"
                "不动产权属转移证明材料（如买卖合同、公证书）。\n"
                "三、办理时限：受理后30个工作日内办结。"
            ),
            summary_one_line="不动产转移登记的材料与办理时限说明。",
            core_points=["适用情形", "权属证明", "办理时限", "税费缴纳"],
            scope="需办理不动产转移登记的权利人。",
            common_misconceptions=["以为签合同即取得物权（需登记）", "以为继承无需登记即可处分"],
            publish_date=date(2022, 6, 1),
            effective_date=date(2022, 6, 1),
            expiry_date=None,
            is_current=True,
            source="自然资源部",
            level="办事指南",
            region=None,
            issuing_authority="自然资源部",
            keywords=["不动产", "登记", "办事指南", "转移登记"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
    # ---------------- policies ----------------
    (
        Policy,
        dict(
            title="关于促进中小企业健康发展的指导意见",
            doc_number="中办发〔2019〕24号",
            category="政策文件",
            full_text=(
                "总体要求：坚持和完善社会主义基本经济制度，坚持“两个毫不动摇”，毫不动摇巩固和发展公有制经济，"
                "毫不动摇鼓励、支持、引导非公有制经济发展。\n"
                "主要措施：营造良好发展环境、破解融资难融资贵、提升创新发展能力、改进服务保障。"
            ),
            summary_one_line="支持中小企业创新与融资的综合性政策文件。",
            core_points=["营商环境优化", "缓解融资难", "财税与政府采购支持", "公共服务体系"],
            scope="全国中小企业及相关服务机构。",
            common_misconceptions=["以为仅针对科技型企业", "以为政策不含政府采购倾斜"],
            publish_date=date(2019, 4, 7),
            effective_date=date(2019, 4, 7),
            expiry_date=None,
            is_current=True,
            source="中共中央办公厅、国务院办公厅",
            level="政策文件",
            region=None,
            issuing_authority="中共中央办公厅、国务院办公厅",
            keywords=["中小企业", "政策", "融资", "营商环境"],
            related_law_ids=[],
            related_case_ids=[],
            related_interpretation_ids=[],
        ),
    ),
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        inserted = 0
        for model, kwargs in SEED:
            # 简单幂等：按 (title) 去重
            existing = await session.scalar(
                select(model.id).where(model.title == kwargs["title"]).limit(1)
            )
            if existing is not None:
                continue
            obj = model(**kwargs)
            session.add(obj)
            inserted += 1
        await session.commit()
        print(f"已插入 {inserted} 条示例数据（共 {len(SEED)} 条，已存在则跳过）。")


if __name__ == "__main__":
    asyncio.run(seed())
