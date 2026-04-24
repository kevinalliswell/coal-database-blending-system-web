#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""本地开发入口。"""

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=app.config.get("DEBUG", False),
        threaded=True,
    )
