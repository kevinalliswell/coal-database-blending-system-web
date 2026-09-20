# syntax=docker/dockerfile:1
#
# 全栈单镜像：构建 Vite/React 单页应用，并由 Flask + Gunicorn 一体托管
# （API 走 /api，其余路径回退到 SPA）。docker run 即整套「煤粉数据库管理及配煤优化控制台」。

# ---------- stage 1: 构建前端 SPA ----------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
# Keep the reviewed lockfile authoritative, including platform optional modules.
RUN npm ci --include=optional --no-audit --no-fund
COPY frontend/ ./
COPY docs /docs
COPY CHANGELOG.md /CHANGELOG.md
# 生产构建（.env.production 关闭演示数据，直连同源 /api）
RUN VITE_USE_MOCK=false npm run build

# ---------- stage 2: Python 运行时 ----------
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_CONFIG=production \
    DATA_STORAGE_MODE=sqlite \
    PORT=5000
WORKDIR /app

# scipy 运行时依赖 OpenMP
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 后端源码与数据
COPY app ./app
COPY backend ./backend
COPY migrations ./migrations
COPY data/test_coal_datas.csv ./data/test_coal_datas.csv
COPY static ./static
COPY run.py wsgi.py pyproject.toml ./
COPY --chmod=755 scripts/container-entrypoint.sh /usr/local/bin/cbos-entrypoint
COPY docs ./docs
COPY CHANGELOG.md ./
ARG BUILD_COMMIT=unknown
ARG BUILD_TIME=unknown
ENV CBOS_BUILD_SHA=$BUILD_COMMIT CBOS_BUILD_TIME=$BUILD_TIME
LABEL org.opencontainers.image.revision=$BUILD_COMMIT
ENTRYPOINT ["cbos-entrypoint"]

# 构建产物 → 由 Flask 托管（SPA_DIST_DIR = /app/frontend/dist）
COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 5000

# 健康检查命中 /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health').status==200 else 1)" || exit 1

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "180", "wsgi:app"]
