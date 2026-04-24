#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""历史入口兼容层，统一转发到新的 `app/` 工厂。"""

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config.get("DEBUG", False),
    )
