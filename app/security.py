"""口令摘要、会话与角色守卫。

口令使用 PBKDF2-SHA256（200000 次迭代）加随机盐保存，数据库中不出现明文；
会话只保存身份标识与角色，不保存口令。
"""

import hashlib
import hmac
import logging
import os
from functools import wraps

from flask import flash, g, redirect, request, session, url_for

from app.errors import AuthRequiredError, ForbiddenError

logger = logging.getLogger(__name__)

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200000

ROLE_LABELS = {
    "CUSTOMER": "顾客",
    "CASHIER": "店员",
    "INVENTORY": "库存管理员",
    "MANAGER": "店长",
}


def role_label(role):
    """把数据库中的角色代码转换为界面显示的中文名称。"""
    return ROLE_LABELS.get(role, role)


def hash_password(password, *, iterations=ITERATIONS, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "%s$%d$%s$%s" % (ALGORITHM, iterations, salt.hex(), digest.hex())


def verify_password(password, stored):
    if not stored:
        return False
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def start_session(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user["user_id"]
    session["username"] = user["username"]
    session["display_name"] = user["display_name"]
    session["role"] = user["role"]
    session["role_label"] = user["role_label"]
    session["employee_id"] = user["employee_id"]
    session["member_id"] = user["member_id"]


def end_session():
    session.clear()


def current_user():
    """从会话读取当前用户；没有登录时返回 None。"""
    if "user" in g:
        return g.user
    user = None
    if session.get("user_id"):
        user = {
            "user_id": session.get("user_id"),
            "username": session.get("username"),
            "display_name": session.get("display_name"),
            "role": session.get("role"),
            "role_label": session.get("role_label"),
            "employee_id": session.get("employee_id"),
            "member_id": session.get("member_id"),
        }
    g.user = user
    if user:
        g.user_name = user["username"]
        g.user_role = user["role"]
    return user


def require_user(*allowed_roles):
    user = current_user()
    if user is None:
        raise AuthRequiredError()
    if allowed_roles and user["role"] not in allowed_roles:
        raise ForbiddenError(
            "当前角色（%s）无权执行该操作" % user.get("role_label", user["role"])
        )
    return user


def api_login_required(*allowed_roles):
    """接口用守卫：未登录返回 401 JSON，角色不符返回 403 JSON。"""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            require_user(*allowed_roles)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def page_login_required(*allowed_roles):
    """页面用守卫：未登录跳转登录页，角色不符显示 403 页面。"""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                flash("请先登录", "warning")
                return redirect(url_for("pages.login", next=request.path))
            if allowed_roles and user["role"] not in allowed_roles:
                raise ForbiddenError(
                    "当前角色（%s）无权访问该页面" % user.get("role_label", user["role"])
                )
            return view(*args, **kwargs)

        return wrapper

    return decorator
