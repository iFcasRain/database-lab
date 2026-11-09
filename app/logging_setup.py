"""日志配置：把定位信息写进后端日志，前端只看到友好提示。

每条日志包含：时间、级别、请求标识、用户名、角色、模块、内容。
按 2MB 滚动，最多保留 5 个文件，避免日志无限增长。
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import g, has_request_context

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-7s | req=%(request_id)s | "
    "user=%(user)s | role=%(role)s | %(name)s | %(message)s"
)


class RequestContextFilter(logging.Filter):
    """给每条日志补上请求标识与操作人，便于按请求追踪。"""

    def filter(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.user = getattr(g, "user_name", "-")
            record.role = getattr(g, "user_role", "-")
        else:
            record.request_id = "-"
            record.user = "-"
            record.role = "-"
        return True


def configure_logging(app):
    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)
    context_filter = RequestContextFilter()

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, "_dsh_app_handler", False):
            root.removeHandler(handler)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    file_handler.addFilter(context_filter)
    file_handler._dsh_app_handler = True

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    console_handler.addFilter(context_filter)
    console_handler._dsh_app_handler = True

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Flask 自带日志沿用同一套格式。
    app.logger.handlers = []
    app.logger.propagate = True
    app.logger.setLevel(level)
    return log_path
