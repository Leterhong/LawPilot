# =============================================================
# LawPilot 命令
# 开发用 dev 叠加（暴露端口 + 热重载）；生产用 prod 叠加（仅 Nginx 对外）。
# 用法：make <target>
# =============================================================
COMPOSE = docker compose
BASE_FILE = docker-compose.yml
DEV_FILE = docker-compose.dev.yml
PROD_FILE = docker-compose.prod.yml

DEV = $(COMPOSE) -f $(BASE_FILE) -f $(DEV_FILE)
PROD = $(COMPOSE) -f $(BASE_FILE) -f $(PROD_FILE)

.PHONY: help infra-up infra-down up dev down deploy deploy-down logs \
        migrate seed init test lint format clean

help: ## 显示可用命令
	@echo "LawPilot 命令："
	@echo "  make infra-up     启动基础设施（db + redis，开发叠加，暴露端口）"
	@echo "  make infra-down   停止基础设施"
	@echo "  make up           构建并启动完整开发环境（含端口与热重载）"
	@echo "  make dev          up 的别名"
	@echo "  make down         停止并移除开发环境"
	@echo "  make deploy       生产构建并启动（prod 叠加，仅 Nginx 对外）"
	@echo "  make deploy-down  停止生产环境（保留数据卷）"
	@echo "  make logs         查看开发环境日志"
	@echo "  make migrate      执行数据库迁移（Alembic）"
	@echo "  make seed         迁移 + 灌入知识库（部署后执行）"
	@echo "  make init         seed 的别名（首次部署一键初始化）"
	@echo "  make test         运行后端测试"
	@echo "  make lint         代码检查（ruff）"
	@echo "  make format       代码格式化（ruff）"
	@echo "  make clean        清理未使用镜像与卷"

infra-up: ## 仅启动数据库与 Redis（开发叠加）
	$(DEV) up -d db redis

infra-down: ## 停止基础设施
	$(COMPOSE) stop db redis

up: ## 启动完整开发环境（含端口与热重载）
	$(DEV) up --build

dev: up ## up 的别名

down: ## 停止并移除开发环境
	$(DEV) down

deploy: ## 生产部署（prod 叠加）
	$(PROD) up -d --build

deploy-down: ## 停止生产环境（保留数据卷）
	$(PROD) down

logs: ## 查看开发环境日志
	$(DEV) logs -f

migrate: ## 执行数据库迁移
	cd backend && alembic upgrade head

seed: ## 迁移数据库并灌入知识库（部署后执行）
	cd backend && alembic upgrade head
	cd backend && python scripts/ingest_knowledge.py

init: seed ## 首次部署一键初始化（迁移 + 灌库）

test: ## 运行后端测试
	cd backend && pytest -q

lint: ## 代码检查（ruff）
	cd backend && ruff check app

format: ## 代码格式化（ruff）
	cd backend && ruff format app

clean: ## 清理
	$(DEV) down -v
	docker system prune -f
