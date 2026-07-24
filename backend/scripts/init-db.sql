-- =============================================================
-- LawPilot 数据库初始化脚本
-- 由 docker-compose 在首次启动 PostgreSQL 时自动执行。
-- 作用：启用 pgvector 扩展（向量检索所需）。
-- 其余表结构由 Alembic 迁移（Phase 2）管理，不在此创建。
-- =============================================================

-- 启用 pgvector 向量扩展（用于 legal_reference / knowledge 的 embedding 列）
CREATE EXTENSION IF NOT EXISTS vector;

-- 说明：users / cases 等业务表将在 Phase 2 通过 Alembic 迁移创建，
-- 不在此处手写 DDL，以保证单一可信来源（migration）。
