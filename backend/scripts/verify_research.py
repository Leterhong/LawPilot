"""研究模块接口冒烟测试（in-process，使用 FastAPI TestClient，无需端口）。"""
from __future__ import annotations

import sys
import json

from fastapi.testclient import TestClient

from app.main import app

BASE = "/api/research"


def main() -> int:
    with TestClient(app) as client:
        # 1) 搜索
        print("=== GET /api/research/search?q=合同 ===")
        r = client.get(BASE + "/search", params={"q": "合同", "limit": 20})
        print("status:", r.status_code)
        if r.status_code != 200:
            print("BODY:", r.text[:2000])
            return 1
        data = r.json()
        print("total:", data.get("total"))
        print("parsed:", json.dumps(data.get("parsed"), ensure_ascii=False))
        items = data.get("items", [])
        for it in items[:5]:
            print(" -", it.get("doc_type"), "|", it.get("category_label"), "|", it.get("title"), "| score=", round(it.get("score", 0), 4))
        print("facets:", json.dumps(data.get("facets"), ensure_ascii=False)[:500])
        if not items:
            print("!! no items returned")
            return 1

        # 2) 详情（取第一个 id）
        doc_id = items[0]["id"]
        print("\n=== GET /api/research/document/" + doc_id + " ===")
        r = client.get(BASE + f"/document/{doc_id}")
        print("status:", r.status_code)
        if r.status_code != 200:
            print("BODY:", r.text[:2000])
            return 1
        det = r.json()
        print("title:", det.get("title"))
        print("doc_type:", det.get("doc_type"), "| category_label:", det.get("category_label"))
        print("is_current:", det.get("is_current"), "| source:", det.get("source"))
        print("full_text len:", len(det.get("full_text") or ""))
        print("ai_explanation present:", bool(det.get("ai_explanation")))
        print("ai_summary present:", bool(det.get("ai_summary")))
        print("related_docs count:", len(det.get("related_docs") or []))
        print("related_docs:", [d.get("title") for d in (det.get("related_docs") or [])][:5])

        # 3) 推荐（基于该文档）
        print("\n=== GET /api/research/recommend?doc_id=... ===")
        r = client.get(BASE + "/recommend", params={"doc_id": doc_id, "limit": 5})
        print("status:", r.status_code)
        if r.status_code != 200:
            print("BODY:", r.text[:2000])
            return 1
        rec = r.json()
        print("recommend total:", rec.get("total"))
        for it in rec.get("items", [])[:5]:
            print(" -", it.get("doc_type"), "|", it.get("title"))

        # 4) 高级检索过滤（按 category + is_current）
        print("\n=== GET /api/research/search 高级过滤 (is_current=true) ===")
        r = client.get(BASE + "/search", params={"q": "", "is_current": True, "limit": 10})
        print("status:", r.status_code)
        if r.status_code == 200:
            print("total(current):", r.json().get("total"))

        # 5) 布尔检索
        print("\n=== GET /api/research/search?q=合同 OR 离婚 ===")
        r = client.get(BASE + "/search", params={"q": "合同 OR 离婚", "limit": 20})
        print("status:", r.status_code)
        if r.status_code == 200:
            print("total(OR):", r.json().get("total"))

        print("\nALL OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
