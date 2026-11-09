"""页面层（Web 接口）。

本模块只做三件事：接收参数、调用业务层、返回统一响应结构。
不出现任何 SQL，也不直接使用数据库驱动。
"""

import logging

from flask import Blueprint, g, jsonify, request

from app.db import check_health
from app.errors import ValidationError
from app.security import api_login_required, end_session, start_session
from app.services import (
    auth_service,
    inventory_service,
    member_service,
    order_service,
    product_service,
    report_service,
)

logger = logging.getLogger(__name__)

bp = Blueprint("api", __name__, url_prefix="/api")


def ok(data=None, message=None):
    payload = {"success": True, "request_id": g.get("request_id")}
    if data is not None:
        payload["data"] = data
    if message:
        payload["message"] = message
    return jsonify(payload)


def read_body():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form.to_dict(flat=True)
    if not isinstance(payload, dict):
        raise ValidationError("请求内容格式不正确")
    return payload


# ---------------------------------------------------------------- 健康检查与登录


@bp.get("/health")
def health():
    check_health()
    return ok({"status": "ok"})


@bp.post("/auth/login")
def login():
    payload = read_body()
    user = auth_service.authenticate(payload.get("username"), payload.get("password"))
    start_session(user)
    return ok(user, "登录成功")


@bp.post("/auth/logout")
def logout():
    end_session()
    return ok(message="已退出登录")


@bp.get("/auth/me")
@api_login_required()
def me():
    return ok(g.user)


# ---------------------------------------------------------------- 商品


@bp.get("/categories")
@api_login_required("MANAGER", "CASHIER")
def categories():
    return ok(product_service.list_categories(g.user))


@bp.get("/products")
@api_login_required()
def products():
    return ok(
        product_service.list_products(
            g.user,
            keyword=request.args.get("keyword"),
            category_id=_optional_int(request.args.get("category_id")),
            status=request.args.get("status"),
        )
    )


@bp.get("/products/<int:product_id>")
@api_login_required()
def product_detail(product_id):
    return ok(product_service.get_product(g.user, product_id))


@bp.post("/products")
@api_login_required("MANAGER")
def product_create():
    return ok(product_service.create_product(g.user, read_body()), "商品已创建"), 201


@bp.put("/products/<int:product_id>")
@api_login_required("MANAGER")
def product_update(product_id):
    return ok(product_service.update_product(g.user, product_id, read_body()), "商品已更新")


# ---------------------------------------------------------------- 库存


@bp.get("/inventory")
@api_login_required("CASHIER", "INVENTORY", "MANAGER")
def inventory():
    return ok(
        inventory_service.list_inventory(
            g.user,
            low_only=request.args.get("low_only") in ("1", "true", "yes"),
            keyword=request.args.get("keyword"),
        )
    )


@bp.post("/inventory/adjust")
@api_login_required("INVENTORY", "MANAGER")
def inventory_adjust():
    return ok(inventory_service.adjust_stock(g.user, read_body()), "库存已调整")


# ---------------------------------------------------------------- 订单


@bp.get("/orders")
@api_login_required()
def orders():
    return ok(
        order_service.list_orders(
            g.user,
            status=request.args.get("status"),
            keyword=request.args.get("keyword"),
        )
    )


@bp.get("/orders/<int:order_id>")
@api_login_required()
def order_detail(order_id):
    return ok(order_service.get_order_detail(g.user, order_id))


@bp.post("/orders")
@api_login_required("CASHIER", "MANAGER", "CUSTOMER")
def order_create():
    return ok(order_service.create_order(g.user, read_body()), "订单已创建"), 201


@bp.post("/orders/<int:order_id>/confirm")
@api_login_required("CASHIER", "MANAGER")
def order_confirm(order_id):
    return ok(order_service.confirm_order(g.user, order_id, read_body()), "订单已完成收款")


@bp.post("/orders/<int:order_id>/cancel")
@api_login_required("CASHIER", "MANAGER", "CUSTOMER")
def order_cancel(order_id):
    return ok(order_service.cancel_order(g.user, order_id), "订单已取消")


# ---------------------------------------------------------------- 会员与统计


@bp.get("/members")
@api_login_required("CASHIER", "MANAGER")
def members():
    return ok(member_service.list_members(g.user, request.args.get("keyword")))


@bp.get("/members/me")
@api_login_required()
def member_me():
    return ok(member_service.member_profile(g.user))


@bp.get("/members/<int:member_id>")
@api_login_required("CASHIER", "MANAGER")
def member_detail(member_id):
    return ok(member_service.member_profile(g.user, member_id))


@bp.get("/reports/summary")
@api_login_required("MANAGER")
def report_summary():
    return ok(report_service.summary(g.user))


@bp.get("/meta/options")
@api_login_required()
def options():
    return ok(
        {
            "payment_methods": order_service.payment_options(),
            "order_statuses": order_service.order_status_options(),
            "product_statuses": [
                {"value": "ACTIVE", "label": "在售"},
                {"value": "INACTIVE", "label": "停用"},
            ],
        }
    )


def _optional_int(value):
    if value in (None, "", "0"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
