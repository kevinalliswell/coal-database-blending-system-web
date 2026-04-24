#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""上传文件记录模型。"""

from app.extensions import db


class UploadFile(db.Model):
    """上传文件元数据表，对应历史项目中的 `upload_files`。"""

    __tablename__ = "upload_files"

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    saved_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    upload_time = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    processed = db.Column(db.Boolean, nullable=False, server_default=db.false())
