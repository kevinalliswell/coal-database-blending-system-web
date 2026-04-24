#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""集中定义 Flask 扩展实例。"""

from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


# 统一在这里创建扩展实例，避免循环导入。
db = SQLAlchemy(session_options={"expire_on_commit": False})
migrate = Migrate(compare_type=True)
cors = CORS()
