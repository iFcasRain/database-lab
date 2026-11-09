"""会员与积分数据访问。"""

from app.db.base import execute, fetch_all, fetch_one


def get_member(cursor, member_id):
    return fetch_one(
        cursor,
        """
        SELECT member_id, member_no, member_name, phone, points_balance,
               registered_at, status, remark
        FROM dbo.member
        WHERE member_id = ?
        """,
        (member_id,),
    )


def find_by_member_no(cursor, member_no):
    return fetch_one(
        cursor,
        """
        SELECT member_id, member_no, member_name, phone, points_balance, status
        FROM dbo.member
        WHERE member_no = ?
        """,
        (member_no,),
    )


def list_members(cursor, keyword=None):
    sql = """
        SELECT member_id, member_no, member_name, phone, points_balance,
               registered_at, status
        FROM dbo.member
        WHERE 1 = 1
    """
    params = []
    if keyword:
        like = "%" + keyword + "%"
        sql += " AND (member_no LIKE ? OR member_name LIKE ? OR phone LIKE ?)"
        params.extend([like, like, like])
    sql += " ORDER BY member_id"
    return fetch_all(cursor, sql, tuple(params))


def update_points(cursor, member_id, new_balance):
    return execute(
        cursor,
        "UPDATE dbo.member SET points_balance = ? WHERE member_id = ?",
        (new_balance, member_id),
    )


def insert_points_transaction(cursor, record):
    return execute(
        cursor,
        """
        INSERT INTO dbo.points_transaction
            (transaction_no, member_id, order_id, change_type,
             points_change, balance_after, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["transaction_no"],
            record["member_id"],
            record.get("order_id"),
            record["change_type"],
            record["points_change"],
            record["balance_after"],
            record.get("remark"),
        ),
    )


def list_points_transactions(cursor, member_id, limit=20):
    return fetch_all(
        cursor,
        """
        SELECT TOP (%d)
            transaction_no, order_id, change_type, points_change,
            balance_after, occurred_at, remark
        FROM dbo.points_transaction
        WHERE member_id = ?
        ORDER BY points_transaction_id DESC
        """ % int(limit),
        (member_id,),
    )


def count_members(cursor):
    row = fetch_one(cursor, "SELECT COUNT(*) AS total FROM dbo.member")
    return row["total"] if row else 0
