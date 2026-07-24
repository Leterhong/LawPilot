# 知识库种子数据

本目录存放 RAG 知识库的可入库数据集，配合 `scripts/ingest_knowledge.py` 使用。

## 数据格式（JSONL）

每行一条 JSON 记录，通过 `type` 字段区分两类：

### 1. 法律条文 `legal_reference`

```json
{
  "type": "legal_reference",
  "source": "law",
  "title": "《民法典》",
  "article": "第577条",
  "content": "当事人一方不履行合同义务……",
  "explanation": "违约责任的一般规定……",
  "jurisdiction": null,
  "effective_date": "2021-01-01",
  "extra": null
}
```

`source` 取值见 `LegalSourceEnum`：law / judicial_interpretation /
admin_regulation / local_regulation / guiding_case / typical_case / guide / policy。

### 2. 知识条目 `knowledge`

```json
{
  "type": "knowledge",
  "category": "guide",
  "title": "租房纠纷办事指南",
  "content": "租房纠纷常见类型包括……",
  "source_url": null,
  "tags": ["租房", "押金", "租赁"]
}
```

`category` 取值与 `LegalSourceEnum` 一致。

## 入库方式

```bash
# 默认入库 legal_seed.jsonl
python scripts/ingest_knowledge.py

# 指定文件
python scripts/ingest_knowledge.py path/to/data.jsonl
```

入库前需配置 `.env` 的 `DATABASE_URL` 与 `EMBEDDING_*`（BGE-M3），
并确保数据库已建表（含 pgvector 扩展）。

> 说明：种子数据中的法条内容摘自公开法律文本，仅用于平台演示与功能验证，
> 实际办案请以官方发布版本为准。
