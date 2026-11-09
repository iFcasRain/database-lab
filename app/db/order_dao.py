"""订单与订单明细数据访问。"""

from app.db.base import execute, fetch_all, fetch_one, insert_returning

_SUMMARY_COLUMNS = """
    order_id,
    order_no,
    member_id,
    member_no,
    customer_name,
    cashier_id,
    cashier_name,
    order_time,
    order_status,
    payment_method,
    original_amount,
    discount_amount,
    paid_amount,
    item_count
"""


def list_orders(cursor, member_id=None, status=None, keyword=None, limit=200):
    sql = "SELECT TOP (%d) " % int(limit) + _SUMMARY_COLUMNS
    sql += " FROM dbo.vw_order_summary WHERE 1 = 1"
    params = []
    if member_id is not None:
        sql += " AND member_id = ?"
        params.append(member_id)
    if status:
        sql += " AND order_status = ?"
        params.append(status)
    if keyword:
        like = "%" + keyword + "%"
        sql += " AND (order_no LIKE ? OR customer_name LIKE ?)"
        params.extend([like, like])
    sql += " ORDER BY order_time DESC, order_id DESC"
    return fetch_all(cursor, sql, tuple(params))


def get_order(cursor, order_id, member_id=None):
    sql = "SELECT " + _SUMMARY_COLUMNS + " FROM dbo.vw_order_summary WHERE order_id = ?"
    params = [order_id]
    if member_id is not None:
        sql += " AND member_id = ?"
        params.append(member_id)
    return fetch_one(cursor, sql, tuple(params))


def list_items(cursor, order_id):
    return fetch_all(
        cursor,
        """
        SELECT
            order_id,
            order_no,
            product_code,
            product_name,
            quantity,
            unit_price,
            line_amount
        FROM dbo.vw_order_detail
        WHERE order_id = ?
        ORDER BY product_code
        """,
        (order_id,),
    )


def list_item_prices(cursor, order_id):
    """确认收款时用于扣减库存，需要 product_id。"""
    return fetch_all(
        cursor,
        """
        SELECT order_item_id, product_id, quantity, unit_price
        FROM dbo.sales_order_item
        WHERE order_id = ?
        ORDER BY order_item_id
        """,
        (order_id,),
    )


def pick_on_duty_cashier(cursor):
    """顾客线上下单时，由业务层指派一名当班收银员作为经办人。"""
    return fetch_one(
        cursor,
        """
        SELECT TOP (1) employee_id, employee_no, employee_name
        FROM dbo.vw_active_cashier
        ORDER BY employee_id
        """,
    )


def next_order_sequence(cursor, order_no_prefix):
    row = fetch_one(
        cursor,
        "SELECT MAX(order_no) AS max_no FROM dbo.sales_order WHERE order_no LIKE ?",
        (order_no_prefix + "%",),
    )
    max_no = row["max_no"] if row else None
    if not max_no:
        return 1
    try:
        return int(max_no[len(order_no_prefix):]) + 1
    except (TypeError, ValueError):
        return 1


def insert_order(cursor, data):
    return insert_returning(
        cursor,
        """
        INSERT INTO dbo.sales_order
            (order_no, member_id, cashier_id, order_status, payment_method,
             original_amount, discount_amount, paid_amount)
        OUTPUT INSERTED.order_id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["order_no"],
            data.get("member_id"),
            data["cashier_id"],
            data["order_status"],
            data.get("payment_method"),
            data["original_amount"],
            data["discount_amount"],
            data["paid_amount"],
        ),
    )


def insert_item(cursor, order_id, product_id, quantity, unit_price):
    return insert_returning(
        cursor,
        """
        INSERT INTO dbo.sales_order_item (order_id, product_id, quantity, unit_price)
        OUTPUT INSERTED.order_item_id
        VALUES (?, ?, ?, ?)
        """,
        (order_id, product_id, quantity, unit_price),
    )


def complete_order(cursor, order_id, payment_method, paid_amount, discount_amount):
    """把待支付订单置为已完成。带状态条件，避免重复确认。"""
    return execute(
        cursor,
        """
        UPDATE dbo.sales_order
        SET order_status = 'COMPLETED',
            payment_method = ?,
            paid_amount = ?,
            discount_amount = ?
        WHERE order_id = ? AND order_status = 'PENDING'
        """,
        (payment_method, paid_amount, discount_amount, order_id),
    )


def cancel_order(cursor, order_id):
    return execute(
        cursor,
        """
        UPDATE dbo.sales_order
        SET order_status = 'CANCELLED'
        WHERE order_id = ? AND order_status = 'PENDING'
        """,
        (order_id,),
    )


def count_orders_today(cursor):
    row = fetch_one(
        cursor,
        """
        SELECT COUNT(*) AS total, COALESCE(SUM(paid_amount), 0) AS amount
        FROM dbo.sales_order
        WHERE order_status = 'COMPLETED'
          AND CAST(order_time AS DATE) = CAST(SYSDATETIME() AS DATE)
        """,
    )
    return row or {"total": 0, "amount": 0}


def count_completed_orders(cursor):
    row = fetch_one(
        cursor,
        """
        SELECT COUNT(*) AS total, COALESCE(SUM(paid_amount), 0) AS amount
        FROM dbo.sales_order
        WHERE order_status = 'COMPLETED'
        """,
    )
    return row or {"total": 0, "amount": 0}


def top_products(cursor, limit=5):
    return fetch_all(
        cursor,
        """
        SELECT TOP (%d)
            p.product_code,
            p.product_name,
            SUM(oi.quantity) AS quantity_sold,
            CAST(SUM(oi.quantity * oi.unit_price) AS DECIMAL(10, 2)) AS sales_amount
        FROM dbo.sales_order_item AS oi
        JOIN dbo.sales_order AS o ON o.order_id = oi.order_id AND o.order_status = 'COMPLETED'
        JOIN dbo.product AS p ON p.product_id = oi.product_id
        GROUP BY p.product_code, p.product_name
        ORDER BY sales_amount DESC, p.product_code
        """ % int(limit),
    )
