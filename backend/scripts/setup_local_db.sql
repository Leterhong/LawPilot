-- =============================================================
-- LawPilot 本地 PostgreSQL 初始化（非 Docker 方式）
-- 用法：用 Navicat（或 psql）以 postgres 超级用户连接，新建查询窗口，
--       粘贴本文件全部内容并执行一次。
-- 作用：创建项目所需的角色与数据库（用户名/密码/库名与 .env 保持一致）。
--       pgvector 向量扩展由 Alembic 迁移自动创建，此处不重复建。
-- 说明：若提示「已存在」类错误，忽略即可（可重复执行）。
-- =============================================================

-- 1) 创建应用角色（与 .env 中 POSTGRES_USER / POSTGRES_PASSWORD 一致）
DO $$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lawpilot') THEN
      CREATE ROLE lawpilot WITH LOGIN PASSWORD 'lawpilot_secret' CREATEDB;
   END IF;
END
$$;

-- 2) 创建数据库（与 .env 中 POSTGRES_DB 一致），归属 lawpilot
--    注意：CREATE DATABASE 不能在 DO 块内执行，单独运行下面这句；若已存在报
--    错，直接忽略。
CREATE DATABASE lawpilot OWNER lawpilot;

-- 3) 验证 pgvector 是否已安装（可选，但强烈建议）：
--    在 Navicat 里「断开当前连接 → 新建连接」连到 lawpilot 库，再执行：
--        CREATE EXTENSION IF NOT EXISTS vector;
--    若成功，说明 pgvector 编译安装无误；若报「could not open extension
--    control file」，说明 pgvector 尚未编译安装，请先完成 pgvector 编译步骤。
