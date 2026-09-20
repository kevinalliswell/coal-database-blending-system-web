#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""煤种管理 API。"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO

import pandas as pd
from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.services import coal_data_service
from app.utils.excel_utils import create_coal_template
from app.utils.file_utils import read_uploaded_file, save_uploaded_file, validate_coal_data_format
from app.utils.validation import validate_coal_data

logger = logging.getLogger(__name__)

coal_bp = Blueprint("coal_management", __name__)


@coal_bp.before_request
def reject_legacy_writes():
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and request.path != '/api/coals/export':
        return jsonify(status='error', code='api_upgrade_required',
                       message='2.0 录入接口已升级，请使用煤种主档、到货批次与化验修订；旧接口不再修改数据'), 410


@coal_bp.route("/coals", methods=["GET"])
def get_coals():
    """获取煤种数据，支持分页、搜索和类型过滤。"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
        search = request.args.get("search", "").strip()
        coal_type = request.args.get("type", "").strip()

        result = coal_data_service.list_coals(
            page=page,
            page_size=page_size,
            search=search,
            coal_type=coal_type,
        )
        return jsonify({"status": "success", **result})
    except Exception as exc:
        logger.exception("获取煤种数据失败")
        return jsonify({"status": "error", "message": f"获取煤种数据失败: {exc}"}), 500


@coal_bp.route("/coals/<int:coal_id>", methods=["GET"])
def get_coal(coal_id):
    """获取单个煤种详情。"""
    try:
        coal = coal_data_service.get_coal(coal_id)
        if coal is None:
            return jsonify({"status": "error", "message": "煤种不存在"}), 404

        return jsonify({"status": "success", "data": coal_data_service.coal_to_api_dict(coal)})
    except Exception as exc:
        logger.exception("获取煤种详情失败")
        return jsonify({"status": "error", "message": f"获取煤种详情失败: {exc}"}), 500


@coal_bp.route("/coals/types", methods=["GET"])
def get_coal_types():
    """获取煤种类型列表。"""
    try:
        return jsonify({"status": "success", "data": coal_data_service.get_coal_types()})
    except Exception as exc:
        logger.exception("获取煤种类型失败")
        return jsonify({"status": "error", "message": f"获取煤种类型失败: {exc}"}), 500


@coal_bp.route("/coals/upload", methods=["POST"])
def upload_coal_data():
    """上传煤种数据文件并导入 SQLite。"""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "没有文件部分"}), 400

    file = request.files["file"]

    try:
        file_path, saved_filename = save_uploaded_file(file, current_app.config['UPLOAD_FOLDER'])
        df = read_uploaded_file(file_path)
        validate_coal_data_format(df)

        summary = coal_data_service.import_dataframe(
            df,
            preserve_ids=False,
            update_existing=True,
        )
        message_parts = [
            f"新增 {summary.created_count} 条",
            f"更新 {summary.updated_count} 条",
            f"跳过 {summary.skipped_count} 条",
        ]
        message = "，".join(message_parts)
        if summary.errors:
            message += "。前几条问题：" + "；".join(summary.errors[:5])

        status = "success" if summary.affected_count > 0 or summary.skipped_count == 0 else "error"
        return jsonify(
            {
                "status": status,
                "message": f"文件上传完成，{message}",
                "filename": saved_filename,
                "coal_count": summary.affected_count,
                "created_count": summary.created_count,
                "updated_count": summary.updated_count,
                "skipped_count": summary.skipped_count,
                "errors": list(summary.errors[:20]),
            }
        )
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        logger.exception("处理上传文件失败")
        return jsonify({"status": "error", "message": f"处理文件失败: {exc}"}), 500


@coal_bp.route("/coals", methods=["POST"])
def add_coal():
    """添加煤种。"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "请求数据为空"}), 400

        is_valid, errors = validate_coal_data(data)
        if not is_valid:
            return jsonify({"status": "error", "message": "; ".join(errors)}), 400

        coal = coal_data_service.create_coal(data)
        return jsonify(
            {
                "status": "success",
                "message": "煤种添加成功",
                "coal_id": coal.id,
                "data": coal_data_service.coal_to_api_dict(coal),
            }
        )
    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "error", "message": "煤种名称已存在"}), 409
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        logger.exception("添加煤种失败")
        return jsonify({"status": "error", "message": f"添加煤种失败: {exc}"}), 500


@coal_bp.route("/coals/<int:coal_id>", methods=["PUT"])
def update_coal(coal_id):
    """更新煤种。"""
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "请求数据为空"}), 400

        is_valid, errors = validate_coal_data(data)
        if not is_valid:
            return jsonify({"status": "error", "message": "; ".join(errors)}), 400

        coal = coal_data_service.update_coal(coal_id, data)
        if coal is None:
            return jsonify({"status": "error", "message": "煤种不存在"}), 404

        return jsonify(
            {
                "status": "success",
                "message": "煤种更新成功",
                "data": coal_data_service.coal_to_api_dict(coal),
            }
        )
    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "error", "message": "煤种名称已存在"}), 409
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        logger.exception("更新煤种失败")
        return jsonify({"status": "error", "message": f"更新煤种失败: {exc}"}), 500


@coal_bp.route("/coals/<int:coal_id>", methods=["DELETE"])
def delete_coal(coal_id):
    """删除煤种。"""
    try:
        if not coal_data_service.delete_coal(coal_id):
            return jsonify({"status": "error", "message": "煤种不存在"}), 404

        return jsonify({"status": "success", "message": "煤种删除成功"})
    except Exception as exc:
        db.session.rollback()
        logger.exception("删除煤种失败")
        return jsonify({"status": "error", "message": f"删除煤种失败: {exc}"}), 500


@coal_bp.route("/coals/batch_delete", methods=["POST"])
def batch_delete_coals():
    """批量删除煤种。"""
    try:
        data = request.json or {}
        coal_ids = data.get("coal_ids", [])
        if not coal_ids:
            return jsonify({"status": "error", "message": "请选择要删除的煤种"}), 400

        deleted_count = coal_data_service.delete_coals(coal_ids)
        return jsonify({"status": "success", "message": f"成功删除 {deleted_count} 条煤种记录"})
    except Exception as exc:
        db.session.rollback()
        logger.exception("批量删除煤种失败")
        return jsonify({"status": "error", "message": f"批量删除煤种失败: {exc}"}), 500


@coal_bp.route("/coals/export", methods=["POST"])
def export_coals():
    """从 SQLite 导出煤种数据。"""
    try:
        data = request.json or {}
        coal_ids = data.get("coal_ids", [])
        export_all = data.get("export_all", False)

        if export_all:
            coals = coal_data_service.get_coals_by_ids(
                [item["id"] for item in coal_data_service.list_coals(page_size=0)["data"]]
            )
        elif coal_ids:
            coals = coal_data_service.get_coals_by_ids(coal_ids)
        else:
            return jsonify({"status": "error", "message": "没有选择要导出的数据"}), 400

        if not coals:
            return jsonify({"status": "error", "message": "没有要导出的数据"}), 400

        output = BytesIO()
        df = coal_data_service.coals_to_export_dataframe(coals)
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="煤种数据", index=False)

        output.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"煤种数据导出_{timestamp}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        logger.exception("导出煤种数据失败")
        return jsonify({"status": "error", "message": f"导出失败: {exc}"}), 500


@coal_bp.route("/coals/template", methods=["GET"])
def download_coal_template():
    """下载导入模板。"""
    try:
        output = create_coal_template()
        return send_file(
            output,
            as_attachment=True,
            download_name="煤种数据导入模板.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as exc:
        logger.exception("下载模板失败")
        return jsonify({"status": "error", "message": f"下载模板失败: {exc}"}), 500
