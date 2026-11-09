"""登录与角色判断。

说明：登录校验本身使用 app_auth 应用账号，只被授予 app_user 的查询与
最后登录时间更新权限；其余业务查询一律切换到对应角色的应用账号。
"""

import logging

from app.db import connection, user_dao
from app.errors import AuthFailedError, ForbiddenError, ValidationError
from app.security import role_label, verify_password

logger = logging.getLogger(__name__)


def authenticate(username, password):
    username = (username or "").strip()
    if not username or not password:
        raise ValidationError("请输入用户名和密码")

    with connection("AUTH") as conn:
        cursor = conn.cursor()
        try:
            record = user_dao.find_by_username(cursor, username)
        finally:
            cursor.close()

    if record is None or not verify_password(password, record["password_hash"]):
        logger.warning("登录失败：用户名或口令不正确，username=%s", username)
        raise AuthFailedError()

    if record["status"] != "ACTIVE":
        raise ForbiddenError("该账号已停用，请联系店长")

    with connection("AUTH") as conn:
        cursor = conn.cursor()
        try:
            user_dao.touch_last_login(cursor, record["user_id"])
        finally:
            cursor.close()

    logger.info("登录成功：%s（%s）", record["username"], role_label(record["role"]))
    return {
        "user_id": record["user_id"],
        "username": record["username"],
        "display_name": record["display_name"],
        "role": record["role"],
        "role_label": role_label(record["role"]),
        "employee_id": record["employee_id"],
        "member_id": record["member_id"],
    }
