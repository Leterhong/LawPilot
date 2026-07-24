"""生成证据中心 Step5 的样例导出文件（法院格式《证据目录》）。

直接调用 evidence_center_report 的 render_* 函数，用一份"民间借贷案"的
示例证据数据渲染 .docx / .pdf / .md，便于直观检查中文排版与导出效果。
不依赖数据库。
"""
from __future__ import annotations

from pathlib import Path

from app.services.evidence_center_report import render_docx, render_markdown, render_pdf

OUT = Path(__file__).resolve().parent.parent / "reports_sample"
OUT.mkdir(exist_ok=True)

# 示例证据（民间借贷案）
evidences = [
    {
        "name": "借条",
        "category": "书证 / 合同",
        "source": "原告出具",
        "pages": 1,
        "proof_point": "证明原被告之间存在 100,000 元借贷合意及还款期限。",
        "strength": 5,
    },
    {
        "name": "银行转账凭证",
        "category": "书证 / 支付",
        "source": "原告银行流水",
        "pages": 2,
        "proof_point": "证明原告已实际交付借款 100,000 元至被告账户。",
        "strength": 5,
    },
    {
        "name": "微信聊天记录",
        "category": "电子数据 / 聊天",
        "source": "原告手机导出",
        "pages": 3,
        "proof_point": "证明被告承认借款并承诺于 2024-12-31 前还款。",
        "strength": 4,
    },
    {
        "name": "催款录音",
        "category": "视听资料 / 音频",
        "source": "原告录制",
        "pages": 0,
        "proof_point": "证明原告于诉讼时效内主张权利，中断时效。",
        "strength": 3,
    },
]

blocks: list[dict] = [
    {"t": "title", "text": "证据目录"},
    {"t": "p", "text": "案由：民间借贷纠纷　原告：张三　被告：李四"},
    {"t": "h2", "text": "一、证据目录"},
    {
        "t": "table",
        "headers": ["序号", "证据名称", "证据种类", "来源", "页数", "证明对象"],
        "rows": [
            [str(i + 1), e["name"], e["category"], e["source"], str(e["pages"]), e["proof_point"]]
            for i, e in enumerate(evidences)
        ],
    },
    {"t": "h2", "text": "二、证明力评估"},
    {
        "t": "table",
        "headers": ["证据名称", "证明力（1-5★）", "说明"],
        "rows": [
            [e["name"], "★" * e["strength"], "核心证据" if e["strength"] >= 5 else "补强证据"]
            for e in evidences
        ],
    },
    {"t": "h2", "text": "三、证据链时间线"},
    {
        "t": "bullets",
        "items": [
            "2024-01-15　签署借条，约定借款 100,000 元、2024-12-31 前还款。",
            "2024-01-16　原告通过银行转账交付 100,000 元。",
            "2024-06-01　微信沟通，被告确认欠款并承诺按期归还。",
        ],
    },
    {"t": "h2", "text": "四、举证说明"},
    {"t": "p", "text": "上述证据已形成**完整证据链**：借条确立借贷合意，转账凭证证明款项交付，"
                       "聊天与录音印证被告自认及催款事实。建议补充被告身份信息材料以便立案。"},
    {"t": "divider"},
    {"t": "p", "text": "（本目录由 LawPilot 智能证据中心自动生成，供参考，请以法院要求为准。）"},
]

title = "证据目录（民间借贷纠纷）"
md = render_markdown(blocks)
docx = render_docx(blocks, title)
pdf = render_pdf(blocks, title)

(OUT / "sample_evidence_directory.md").write_text(md, encoding="utf-8")
(OUT / "sample_evidence_directory.docx").write_bytes(docx)
if pdf:
    (OUT / "sample_evidence_directory.pdf").write_bytes(pdf)

print("WROTE:")
for p in ["sample_evidence_directory.md", "sample_evidence_directory.docx", "sample_evidence_directory.pdf"]:
    fp = OUT / p
    print(f"  {p:<36} {fp.stat().st_size:>8} bytes")
