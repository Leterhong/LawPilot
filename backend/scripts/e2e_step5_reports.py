"""Step5 端到端验证（真实 uvicorn + httpx）：报告生成 + 导出 + 列表/详情。"""
from __future__ import annotations

import time
import uuid

import httpx

BASE_URL = "http://127.0.0.1:8015"
BASE = "/api/v1"

EMAIL = f"ev5_{uuid.uuid4().hex[:8]}@lawpilot.dev"
PASSWORD = "Test1234!"


def section(t: str) -> None:
    print("\n=== " + t + " ===")


# 等待服务就绪
section("等待服务就绪")
for _ in range(40):
    try:
        if httpx.get(BASE_URL + "/docs", timeout=2).status_code == 200:
            break
    except Exception:
        pass
    time.sleep(0.5)
else:
    raise SystemExit("uvicorn 未在 8015 就绪")


with httpx.Client(base_url=BASE_URL, timeout=30) as cli:
    # 1) 注册 + 登录
    section("注册 + 登录")
    r = cli.post(f"{BASE}/auth/register", json={
        "email": EMAIL, "password": PASSWORD, "display_name": "Step5Tester",
    })
    print("register", r.status_code)
    assert r.status_code in (200, 201), r.text
    tok = cli.post(
        f"{BASE}/auth/login", data={"username": EMAIL, "password": PASSWORD}
    ).json()["access_token"]
    H = {"Authorization": f"Bearer {tok}"}

    # 2) 建借贷案件
    section("建案件(loan)")
    r = cli.post(f"{BASE}/cases", json={
        "title": "张三诉李四民间借贷纠纷", "case_type": "loan",
        "description": "2024年借款10万元未还",
    }, headers=H)
    print("create case", r.status_code)
    assert r.status_code == 201, r.text
    case_id = r.json()["id"]
    print("case_id", case_id)

    # 3) 上传 3 证据
    section("上传 3 证据")
    ev_files = [
        ("contract.txt",
         "借款合同\n甲方张三乙方李四\n借款金额：人民币100000元\n签订日期：2024-01-15\n"
         "约定2024-12-31前归还。", "text/plain"),
        ("payment.txt",
         "银行转账凭证\n2024-01-16 通过工商银行向李四转账人民币100000元，附言：借款。",
         "text/plain"),
        ("chat.txt",
         "微信聊天记录\n2024-06-01 张三：请尽快还款。\n李四：最近手头紧，下月还。",
         "text/plain"),
    ]
    ev_ids = []
    for name, content, ctype in ev_files:
        r = cli.post(
            f"{BASE}/evidence-center/upload?case_id={case_id}",
            files=[("files", (name, content.encode("utf-8"), ctype))],
            headers=H,
        )
        print("upload", name, r.status_code)
        assert r.status_code == 201, r.text
        ev_ids.extend(it["file"]["id"] for it in r.json()["items"])
    print("evidence_ids", len(ev_ids))

    # 4) 分析
    section("批量分析")
    r = cli.post(f"{BASE}/evidence-center/analyze",
                 json={"evidence_ids": ev_ids, "force_reparse": False}, headers=H)
    print("analyze", r.status_code, "succeeded", r.json().get("succeeded"))
    assert r.status_code == 200 and r.json()["succeeded"] == 3, r.text

    # 5) 生成 5 类报告
    section("生成 5 类报告")
    TYPES = ["directory", "score", "missing", "strategy", "full"]
    report_ids = {}
    for t in TYPES:
        r = cli.post(f"{BASE}/evidence-center/reports",
                     json={"case_id": case_id, "report_type": t, "regenerate": False},
                     headers=H)
        print(f"generate {t}", r.status_code)
        assert r.status_code == 201, r.text
        body = r.json()
        report_ids[t] = body["id"]
        c = body.get("content") or {}
        print("  evidence_count", c.get("evidence_count"), "analyzed",
              c.get("analyzed_count"), "ai_assisted", c.get("ai_assisted"),
              "md_len", len(c.get("markdown", "")))
        assert c.get("markdown") and c.get("blocks")

    # 6) 缓存命中
    section("缓存命中")
    r = cli.post(f"{BASE}/evidence-center/reports",
                 json={"case_id": case_id, "report_type": "directory", "regenerate": False},
                 headers=H)
    assert r.status_code == 201 and r.json()["id"] == report_ids["directory"]
    print("cache hit OK, same id")

    # 7) 导出校验
    section("导出 word/pdf/markdown")
    for t in TYPES:
        rid = report_ids[t]
        for fmt in ["word", "pdf", "markdown"]:
            r = cli.get(f"{BASE}/evidence-center/reports/{rid}/download?fmt={fmt}", headers=H)
            assert r.status_code == 200, (fmt, t, r.status_code, r.text[:200])
            data = r.content
            if fmt == "word":
                assert data[:4] == b"PK\x03\x04", "docx magic"
                print(f"  {t}/word OK ({len(data)}B)")
            elif fmt == "pdf":
                assert data[:4] == b"%PDF", "pdf magic"
                print(f"  {t}/pdf OK ({len(data)}B)")
            else:
                assert b"#" in data
                print(f"  {t}/markdown OK ({len(data)}B)")

    # 8) 列表 + 详情
    section("列表 + 详情")
    r = cli.get(f"{BASE}/evidence-center/reports?case_id={case_id}", headers=H)
    print("list", r.status_code, "count", len(r.json()))
    assert r.status_code == 200 and len(r.json()) >= 5
    r = cli.get(f"{BASE}/evidence-center/reports/{report_ids['full']}", headers=H)
    print("detail full", r.status_code, r.json().get("title"))
    assert r.status_code == 200

    # 9) 缺失分析内容校验
    section("缺失分析内容校验")
    c = cli.post(f"{BASE}/evidence-center/reports",
                 json={"case_id": case_id, "report_type": "missing", "regenerate": True},
                 headers=H).json()["content"]
    md = c["markdown"]
    print("missing contains 身份证明:", "身份证明" in md)
    assert "身份证明" in md

    # 10) 未关联案件的证据集合生成（evidence_ids 路径）
    section("evidence_ids 路径（无案件）")
    r = cli.post(f"{BASE}/evidence-center/reports",
                 json={"evidence_ids": ev_ids, "report_type": "directory", "regenerate": True},
                 headers=H)
    print("adhoc generate", r.status_code)
    assert r.status_code == 201
    rid = r.json()["id"]
    r = cli.get(f"{BASE}/evidence-center/reports/{rid}", headers=H)
    print("adhoc detail", r.status_code, "case_id", r.json().get("case_id"))
    assert r.status_code == 200 and r.json().get("case_id") is None

print("\n>>> Step5 端到端全部通过 ✅")
