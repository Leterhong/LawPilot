# LawPilot 后端

基于 FastAPI 的法律问题解决平台 API 服务。

## 本地运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

## 结构

- `app/core/`：配置、数据库、安全、日志
- `app/api/v1/`：REST 路由（Phase 3 充实）
- `app/models/`：SQLAlchemy ORM（Phase 2 充实）
- `app/schemas/`：Pydantic 模型
- `app/services/`：业务逻辑 / Agent / RAG
- `app/repositories/`：数据访问层
- `app/utils/`：工具函数

详见根目录 `README.md`。
