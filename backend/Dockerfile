# =============================================================
# LawPilot 后端 Dockerfile（多阶段）
# 阶段 build：安装依赖到虚拟环境
# 阶段 runtime：精简运行镜像
# =============================================================
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
# 使用 venv 隔离依赖，便于在 runtime 阶段整目录复制
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# -------------------------------
# 运行阶段
# -------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# 安装运行时需要的系统库（OCR 在后续阶段启用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tesseract-ocr libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制虚拟环境与项目代码
COPY --from=build /opt/venv /opt/venv
COPY ./app ./app
COPY ./scripts ./scripts
# 种子知识库（生产环境下 scripts/init.sh 在容器内执行入库）
COPY ./sample_data ./sample_data

# 上传目录（持久化卷挂载点）
RUN mkdir -p /app/uploads

EXPOSE 8000

# 健康检查由 docker-compose 的 healthcheck 负责
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
