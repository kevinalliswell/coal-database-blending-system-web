#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""WSGI 入口，供 Gunicorn 等生产服务器加载。"""

from app import create_app


app = create_app()
