#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""单页应用（SPA）托管与健康检查路由。

前端已整体重构为 Vite + React 单页应用（源码见 `frontend/`），
构建产物位于 `frontend/dist`。此蓝图负责：

- `/health`：健康检查（JSON）
- `/favicon.ico`：站点图标
- 其余非 `/api` 路径：交给 SPA（history 模式），静态资源直出、路由回退到 index.html

当 `frontend/dist` 尚未构建时（例如 CI 仅跑后端测试），返回一个轻量占位页，
保证页面路由仍以 200 响应。
"""

import os

from flask import Blueprint, abort, current_app, jsonify, send_from_directory


page_bp = Blueprint("pages", __name__)


_PLACEHOLDER = (
    "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
    "<title>煤粉数据库管理及配煤优化控制台</title></head>"
    "<body style='font-family:system-ui;background:#0b0b0e;color:#f4f0e6;"
    "display:grid;place-items:center;height:100vh;margin:0'>"
    "<div id='root' style='text-align:center'>"
    "<h1 style='color:#ff7a1a'>煤粉数据库管理及配煤优化控制台</h1>"
    "<p>前端尚未构建。请在 <code>frontend/</code> 执行 "
    "<code>npm install &amp;&amp; npm run build</code>，或直接运行 Docker 镜像。</p>"
    "</div></body></html>"
)


def _spa_dir() -> str:
    return current_app.config["SPA_DIST_DIR"]


@page_bp.get("/health")
def health_check():
    """健康检查接口。"""
    from app.models import Coal

    return jsonify(
        {
            "status": "ok",
            "app": current_app.config["APP_NAME"],
            "storage_mode": current_app.config["DATA_STORAGE_MODE"],
            "coal_count": Coal.query.count(),
        }
    )


@page_bp.get("/favicon.ico")
def favicon():
    """站点图标：优先取构建产物，退回历史静态文件。"""
    spa_dir = _spa_dir()
    for name in ("favicon.ico", "furnace.svg"):
        if os.path.isfile(os.path.join(spa_dir, name)):
            return send_from_directory(spa_dir, name)
    return current_app.send_static_file("favicon.ico")


@page_bp.get("/")
@page_bp.get("/<path:path>")
def spa(path: str = ""):
    """托管单页应用：静态资源直出，其余路径回退到 index.html。"""
    # 未匹配到的 /api/* 一律按接口 404 处理，避免被 SPA 吞掉。
    if path.startswith("api/") or path == "api":
        abort(404)

    spa_dir = _spa_dir()

    if path:
        candidate = os.path.normpath(os.path.join(spa_dir, path))
        # 防目录穿越，并且仅在文件真实存在时直出。
        if candidate.startswith(os.path.normpath(spa_dir)) and os.path.isfile(candidate):
            rel = os.path.relpath(candidate, spa_dir).replace("\\", "/")
            return send_from_directory(spa_dir, rel)

    index_path = os.path.join(spa_dir, "index.html")
    if os.path.isfile(index_path):
        return send_from_directory(spa_dir, "index.html")

    return _PLACEHOLDER, 200
