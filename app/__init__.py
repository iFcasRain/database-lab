"""小卖部经营管理 Web 应用（v1.0）。

分层：页面层（web） → 业务层（services） → 数据访问层（db） → SQL Server。
本文件只负责组装应用、注册蓝图和统一异常处理。
"""

import logging
import time
import uuid

from flask import Flask, g, jsonify, render_template, request

from app.config import Config, build_app_user_map
from app.errors import AppError
from app.logging_setup import configure_logging
from app.security import current_user, role_label

logger = logging.getLogger(__name__)

NAV_ITEMS = [
    {"endpoint": "pages.dashboard", "label": "工作台", "roles": None},
    {"endpoint": "pages.products", "label": "商品", "roles": None},
    {"endpoint": "pages.inventory", "label": "库存", "roles": {"CASHIER", "INVENTORY", "MANAGER"}},
    {"endpoint": "pages.orders", "label": "订单", "roles": None},
    {"endpoint": "pages.members", "label": "会员", "roles": {"CASHIER", "MANAGER"}},
    {"endpoint": "pages.reports", "label": "经营分析", "roles": {"MANAGER"}},
]


def _wants_json():
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def create_app(config_object=Config):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object)
    app.config["DB_APP_USER_MAP"] = build_app_user_map(app.config)
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    configure_logging(app)

    from app.web.api import bp as api_bp
    from app.web.pages import bp as pages_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(pages_bp)

    @app.before_request
    def _start_request():
        g.request_id = uuid.uuid4().hex[:12]
        g.user_name = "-"
        g.user_role = "-"
        g.start_time = time.perf_counter()

    @app.after_request
    def _finish_request(response):
        elapsed = (time.perf_counter() - g.get("start_time", time.perf_counter())) * 1000
        response.headers["X-Request-Id"] = g.get("request_id", "-")
        if request.path.startswith("/api/") or response.status_code >= 400:
            logger.info(
                "请求完成：%s %s -> %s（%.1f ms）",
                request.method,
                request.path,
                response.status_code,
                elapsed,
            )
        return response

    @app.context_processor
    def _inject_layout():
        user = current_user()
        nav = [
            item
            for item in NAV_ITEMS
            if item["roles"] is None or (user and user["role"] in item["roles"])
        ]
        return {
            "current_user": user,
            "nav_items": nav,
            "role_label": role_label,
        }

    @app.errorhandler(AppError)
    def _handle_app_error(error):
        logger.warning(
            "业务异常：code=%s，path=%s，message=%s，detail=%s",
            error.code,
            request.path,
            error.message,
            error.log_detail or "-",
        )
        if _wants_json():
            return (
                jsonify(
                    {
                        "success": False,
                        "error": error.to_payload(),
                        "request_id": g.get("request_id"),
                    }
                ),
                error.http_status,
            )
        return (
            render_template(
                "error.html",
                error=error.to_payload(),
                status_code=error.http_status,
                request_id=g.get("request_id"),
            ),
            error.http_status,
        )

    @app.errorhandler(404)
    def _handle_404(_error):
        if _wants_json():
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {"code": "NOT_FOUND", "message": "请求的地址不存在"},
                        "request_id": g.get("request_id"),
                    }
                ),
                404,
            )
        return (
            render_template(
                "error.html",
                error={"code": "NOT_FOUND", "message": "页面不存在"},
                status_code=404,
                request_id=g.get("request_id"),
            ),
            404,
        )

    @app.errorhandler(405)
    def _handle_405(_error):
        payload = {"code": "METHOD_NOT_ALLOWED", "message": "请求方式不被支持"}
        if _wants_json():
            return (
                jsonify({"success": False, "error": payload, "request_id": g.get("request_id")}),
                405,
            )
        return render_template("error.html", error=payload, status_code=405,
                               request_id=g.get("request_id")), 405

    @app.errorhandler(Exception)
    def _handle_unexpected(error):
        # 未预期异常：完整堆栈只写日志，返回前端统一提示。
        logger.exception("未处理异常：%s %s", request.method, request.path)
        payload = {
            "code": "INTERNAL_ERROR",
            "message": "系统暂时无法完成操作，请稍后再试",
        }
        if _wants_json():
            return (
                jsonify({"success": False, "error": payload, "request_id": g.get("request_id")}),
                500,
            )
        return render_template("error.html", error=payload, status_code=500,
                               request_id=g.get("request_id")), 500

    @app.teardown_request
    def _teardown(_exc):  # pragma: no cover - 仅用于清理
        g.pop("start_time", None)

    return app
