#!/usr/bin/env bash
# =============================================================
# LawPilot 一键生产部署脚本
# -------------------------------------------------------------
# 职责：
#   1. 以生产形态启动 db / redis / backend
#   2. 等待数据库就绪
#   3. 执行 Alembic 迁移（建表）
#   4. 灌入法律种子知识库（在 backend 容器内执行）
#   5. 启动 frontend 与 nginx 网关
#
# 前置：
#   - 已安装 Docker 与 Docker Compose 插件
#   - 已准备 .env（参考 .env.example，关键：SECRET_KEY / 数据库密码 /
#     CORS_ORIGINS / NEXT_PUBLIC_API_BASE_URL / ENVIRONMENT=production）
#
# 用法：
#   ./scripts/init.sh
# =============================================================
set -euo pipefail

# 切换到项目根目录（脚本位于 <root>/scripts/）
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

PG_USER="${POSTGRES_USER:-lawpilot}"
PG_DB="${POSTGRES_DB:-lawpilot}"

echo "==> [1/5] 启动基础设施与后端（生产形态）"
$COMPOSE up -d --build db redis backend

echo "==> [2/5] 等待数据库就绪…"
until $COMPOSE exec -T db pg_isready -U "$PG_USER" -d "$PG_DB" >/dev/null 2>&1; do
  echo "    数据库尚未就绪，2s 后重试…"
  sleep 2
done
echo "    数据库已就绪"

echo "==> [3/5] 执行数据库迁移（Alembic）"
$COMPOSE exec -T backend alembic upgrade head

echo "==> [4/5] 灌入法律种子知识库"
$COMPOSE exec -T backend python scripts/ingest_knowledge.py

echo "==> [5/5] 启动前端与网关"
$COMPOSE up -d --build frontend nginx

echo ""
echo "==> 部署完成！访问 http://localhost （生产请将域名解析至此主机）"
echo "    查看日志： make logs"
echo "    停止服务： make deploy-down"
