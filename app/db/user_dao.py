"""应用账号数据访问。"""

from app.db.base import execute, fetch_one

_SELECT_USER = """
SELECT
    user_id,
    username,
    password_hash,
    display_name,
    role,
    employee_id,
    member_id,
    status,
    last_login_at
FROM dbo.app_user
WHERE username = ?
"""


def find_by_username(cursor, username):
    return fetch_one(cursor, _SELECT_USER, (username,))


def find_by_id(cursor, user_id):
    return fetch_one(
        cursor,
        """
        SELECT user_id, username, display_name, role, employee_id, member_id, status
        FROM dbo.app_user
        WHERE user_id = ?
        """,
        (user_id,),
    )


def touch_last_login(cursor, user_id):
    return execute(
        cursor,
        "UPDATE dbo.app_user SET last_login_at = SYSDATETIME() WHERE user_id = ?",
        (user_id,),
    )
