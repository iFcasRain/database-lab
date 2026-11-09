"""页面层（服务端渲染）。

每个路由只做：读取查询参数 → 调用业务层 → 交给模板渲染。
页面上的按钮按角色显示，但真正的权限判断在业务层和数据库里再次执行。
"""

import logging

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from app.errors import AuthFailedError, ValidationError
from app.security import (
    current_user,
    end_session,
    page_login_required,
    start_session,
)
from app.services import (
    auth_service,
    inventory_service,
    member_service,
    order_service,
    product_service,
    report_service,
)

logger = logging.getLogger(__name__)

bp = Blueprint("pages", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None and request.method == "GET":
        return redirect(url_for("pages.dashboard"))

    if request.method == "POST":
        try:
            user = auth_service.authenticate(
                request.form.get("username"), request.form.get("password")
            )
        except (AuthFailedError, ValidationError) as error:
            logger.info("登录失败：%s", error.message)
            return (
                render_template("login.html", username=request.form.get("username"), error=error.message),
                401,
            )
        start_session(user)
        target = request.args.get("next") or request.form.get("next")
        if target and target.startswith("/"):
            return redirect(target)
        return redirect(url_for("pages.dashboard"))

    return render_template("login.html", username="", error=None)


@bp.get("/logout")
def logout():
    end_session()
    flash("已退出登录", "success")
    return redirect(url_for("pages.login"))


@bp.get("/")
@page_login_required()
def dashboard():
    user = current_user()
    context = {"summary": None, "orders": [], "low_stock": [], "profile": None}

    if user["role"] == "MANAGER":
        context["summary"] = report_service.summary(user)
        context["orders"] = order_service.list_orders(user)[:8]
        context["low_stock"] = context["summary"]["low_stock"]
    elif user["role"] == "INVENTORY":
        context["low_stock"] = inventory_service.low_stock_products(user)
    elif user["role"] == "CASHIER":
        context["orders"] = order_service.list_orders(user, status="PENDING")[:8]
        context["low_stock"] = inventory_service.low_stock_products(user)
    else:  # CUSTOMER
        context["profile"] = member_service.member_profile(user)
        context["orders"] = order_service.list_orders(user)[:8]

    return render_template("dashboard.html", **context)


@bp.get("/products")
@page_login_required()
def products():
    user = current_user()
    keyword = (request.args.get("keyword") or "").strip()
    status = (request.args.get("status") or "").strip() or None
    rows = product_service.list_products(user, keyword=keyword or None, status=status)
    categories = (
        product_service.list_categories(user) if user["role"] in ("MANAGER", "CASHIER") else []
    )
    return render_template(
        "products.html",
        products=rows,
        categories=categories,
        keyword=keyword,
        status=status or "",
    )


@bp.get("/inventory")
@page_login_required("CASHIER", "INVENTORY", "MANAGER")
def inventory():
    user = current_user()
    low_only = request.args.get("low_only") in ("1", "true", "yes")
    keyword = (request.args.get("keyword") or "").strip()
    rows = inventory_service.list_inventory(user, low_only=low_only, keyword=keyword or None)
    return render_template("inventory.html", rows=rows, low_only=low_only, keyword=keyword)


@bp.get("/orders")
@page_login_required("CASHIER", "MANAGER", "CUSTOMER")
def orders():
    user = current_user()
    status = (request.args.get("status") or "").strip() or None
    keyword = (request.args.get("keyword") or "").strip()
    rows = order_service.list_orders(user, status=status, keyword=keyword or None)
    products = product_service.list_products(user)
    return render_template(
        "orders.html",
        orders=rows,
        products=products,
        status=status or "",
        keyword=keyword,
        status_options=order_service.order_status_options(),
        payment_options=order_service.payment_options(),
    )


@bp.get("/orders/<int:order_id>")
@page_login_required("CASHIER", "MANAGER", "CUSTOMER")
def order_detail(order_id):
    user = current_user()
    order = order_service.get_order_detail(user, order_id)
    return render_template(
        "order_detail.html",
        order=order,
        payment_options=order_service.payment_options(),
    )


@bp.get("/members")
@page_login_required("CASHIER", "MANAGER")
def members():
    user = current_user()
    keyword = (request.args.get("keyword") or "").strip()
    rows = member_service.list_members(user, keyword=keyword or None)
    return render_template("members.html", members=rows, keyword=keyword)


@bp.get("/members/<int:member_id>")
@page_login_required("CASHIER", "MANAGER", "CUSTOMER")
def member_detail(member_id):
    user = current_user()
    if user["role"] == "CUSTOMER":
        member = member_service.member_profile(user)
    else:
        member = member_service.member_profile(user, member_id)
    return render_template("member_detail.html", member=member)


@bp.get("/reports")
@page_login_required("MANAGER")
def reports():
    user = current_user()
    return render_template("reports.html", summary=report_service.summary(user))
