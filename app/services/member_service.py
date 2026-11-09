"""会员资料与积分查询业务。

顾客只能看到自己的会员资料与积分流水；
店员和店长可以按会员号、姓名或手机号查询会员，用于结算时识别会员。
"""

from app.db import connection, member_dao
from app.errors import ForbiddenError, NotFoundError
from app.security import require_user


def list_members(user, keyword=None):
    require_user("CASHIER", "MANAGER")
    with connection(user["role"]) as conn:
        cursor = conn.cursor()
        try:
            return member_dao.list_members(cursor, (keyword or "").strip() or None)
        finally:
            cursor.close()


def member_profile(user, member_id=None):
    role = user["role"]
    if role == "CUSTOMER":
        member_id = user["member_id"]
        if not member_id:
            raise ForbiddenError("当前账号没有关联会员资料")
    else:
        require_user("CASHIER", "MANAGER")

    if member_id is None:
        raise NotFoundError("请指定会员")

    with connection(role) as conn:
        cursor = conn.cursor()
        try:
            member = member_dao.get_member(cursor, member_id)
            if member is None:
                raise NotFoundError("会员不存在")
            history = member_dao.list_points_transactions(cursor, member_id)
        finally:
            cursor.close()

    member = dict(member)
    member["points_history"] = history
    return member
