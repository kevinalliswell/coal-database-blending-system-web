#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""页面和健康检查路由。"""

from flask import Blueprint, current_app, jsonify, render_template, send_from_directory


page_bp = Blueprint("pages", __name__)


@page_bp.get("/")
def index():
    """首页。"""
    return render_template("index.html")


@page_bp.get("/coal_management")
def coal_management():
    """煤种管理页面。"""
    return render_template("coal_management.html")


@page_bp.get("/smart_blending")
def smart_blending():
    """智能混煤页面。"""
    return render_template("smart_blending.html")


@page_bp.get("/replacement_ratio")
def replacement_ratio():
    """置换比计算页面。"""
    return render_template("replacement_ratio.html")


@page_bp.get("/optimization_history/blending")
def blending_optimization_history():
    """混煤优化历史页面。"""
    return render_template("optimization_history_blending.html")


@page_bp.get("/optimization_history/replacement_ratio")
def replacement_ratio_optimization_history():
    """置换比历史页面。"""
    return render_template("optimization_history_replacement_ratio.html")


@page_bp.get("/images/<path:filename>")
def serve_image(filename: str):
    """兼容历史 `/images/*` 路径，实际从静态图片目录读取文件。"""
    return send_from_directory(current_app.config["STATIC_IMAGES_DIR"], filename)


@page_bp.get("/favicon.ico")
def favicon():
    """Serve the project favicon from the static directory."""
    return current_app.send_static_file("favicon.ico")


@page_bp.get("/health")
def health_check():
    """健康检查接口。"""
    return jsonify(
        {
            "status": "ok",
            "app": current_app.config["APP_NAME"],
            "storage_mode": current_app.config["DATA_STORAGE_MODE"],
        }
    )
