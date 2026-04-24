#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""历史配置兼容层，统一转发到新的 `app.config`。"""

from app.config import Config, DevelopmentConfig, ProductionConfig, config

__all__ = ["Config", "DevelopmentConfig", "ProductionConfig", "config"]
