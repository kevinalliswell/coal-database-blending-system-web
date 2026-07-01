#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""统一错误处理。

前端为单页应用：非 /api 的路径由 SPA 路由兜底（见 pages.py），
因此错误处理只对 /api 或显式要求 JSON 的请求返回结构化错误，
其余情况返回极简文本，不再依赖 Jinja 模板。
"""

from flask import jsonify, request


def _wants_json_response() -> bool:
    """根据请求路径和 Accept 头判断是否优先返回 JSON。"""
    return request.path.startswith("/api") or request.accept_mimetypes.best == "application/json"


def register_error_handlers(app) -> None:
    """注册全局错误处理器。"""

    @app.errorhandler(400)
    def bad_request(error):
        if _wants_json_response():
            return jsonify({"status": "error", "message": "请求格式错误"}), 400
        return "请求格式错误", 400

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json_response():
            return jsonify({"status": "error", "message": "请求的资源不存在"}), 404
        return "资源不存在", 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.exception("服务器内部错误: %s", error)
        if _wants_json_response():
            return jsonify({"status": "error", "message": "服务器内部错误"}), 500
        return "服务器内部错误", 500
