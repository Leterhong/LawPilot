"""Focused E2E for Step6 reminder center: verify upcoming query returns the
within-window reminder BEFORE it is marked done."""
import asyncio
import os
import tempfile
from datetime import date, timedelta

from starlette.testclient import TestClient

os.environ.setdefault("PYTHONPATH", "F:/falv/backend")

from app.main import app  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app import models as _models  # noqa: E402  (register all models onto Base.metadata)


async def main():
    # tables are created by alembic migrations; do NOT call create_all here
    # (sharing the engine with the app's pool triggers asyncpg protocol errors)

    with TestClient(app) as client:
        # login admin
        r = client.post(
            "/api/v1/auth/login",
            data={"username": "admin@lawpilot.dev", "password": "admin1234"},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        H = {"Authorization": f"Bearer {token}"}

        # create a small text contract file
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("租赁合同：甲方出租房屋给乙方，租期一年，月租金5000元。")
            path = f.name
        with open(path, "rb") as fh:
            up = client.post(
                "/api/contracts/upload",
                headers=H,
                files={"file": ("lease.txt", fh, "text/plain")},
                data={"title": "E2E提醒测试合同"},
            )
        os.unlink(path)
        assert up.status_code == 201, up.text
        cid = up.json()["contract"]["id"]
        print("UPLOAD", up.status_code, cid[:8])

        # create a reminder due in 10 days
        due = (date.today() + timedelta(days=10)).isoformat()
        c1 = client.post(
            f"/api/contracts/{cid}/tasks",
            headers=H,
            json={
                "type": "reminder",
                "title": "支付第二季度租金",
                "category": "payment",
                "due_date": due,
                "remind_before_days": 7,
                "priority": "high",
            },
        )
        assert c1.status_code == 201, c1.text
        tid = c1.json()["id"]
        print("CREATE reminder", c1.status_code, tid[:8], "due", due)

        # create a far reminder (should be excluded)
        far = (date.today() + timedelta(days=400)).isoformat()
        c2 = client.post(
            f"/api/contracts/{cid}/tasks",
            headers=H,
            json={
                "type": "reminder",
                "title": "续租评估",
                "due_date": far,
            },
        )
        assert c2.status_code == 201, c2.text
        print("CREATE far", c2.status_code)

        # >>> upcoming BEFORE done <<<
        u1 = client.get("/api/contracts/tasks/upcoming?days=30", headers=H)
        print("UPCOMING_BEFORE count=", len(u1.json()), "titles=", [t["title"] for t in u1.json()])
        assert u1.status_code == 200
        assert len(u1.json()) == 1, f"expected 1 upcoming, got {len(u1.json())}"
        assert u1.json()[0]["title"] == "支付第二季度租金"
        assert u1.json()[0]["contract_title"] == "E2E提醒测试合同"

        # now mark done
        p = client.patch(
            f"/api/contracts/{cid}/tasks/{tid}",
            headers=H,
            json={"done": True},
        )
        print("PATCH", p.status_code, "done=", p.json().get("done"))
        assert p.status_code == 200

        # >>> upcoming AFTER done <<<
        u2 = client.get("/api/contracts/tasks/upcoming?days=30", headers=H)
        print("UPCOMING_AFTER count=", len(u2.json()), "titles=", [t["title"] for t in u2.json()])
        assert len(u2.json()) == 0

        # overdue test: a reminder due 5 days ago
        past = (date.today() - timedelta(days=5)).isoformat()
        c3 = client.post(
            f"/api/contracts/{cid}/tasks",
            headers=H,
            json={
                "type": "reminder",
                "title": "逾期缴费",
                "due_date": past,
                "priority": "urgent",
            },
        )
        assert c3.status_code == 201, c3.text
        u3 = client.get("/api/contracts/tasks/upcoming?days=30", headers=H)
        print("UPCOMING_OVERDUE count=", len(u3.json()), "titles=", [t["title"] for t in u3.json()])
        assert any(t["title"] == "逾期缴费" for t in u3.json()), "overdue should appear"

        # cleanup
        d = client.delete(f"/api/contracts/{cid}", headers=H)
        print("DELETE contract", d.status_code)
        g = client.get(f"/api/contracts/{cid}", headers=H)
        print("GET_AFTER_DELETE", g.status_code)

        print("E2E_STEP6_FOCUSED_DONE")


asyncio.run(main())
