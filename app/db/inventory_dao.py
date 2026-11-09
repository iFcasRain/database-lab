"""库存数据访问。

库存数量与库存流水必须在同一事务中修改：前者是当前结果，后者是变化依据。
"""

from app.db.base import execute, fetch_all, fetch_one

_INVENTORY_COLUMNS = """
    product_id,
    product_code,
    product_name,
    category_name,
    unit,
    selling_price,
    quantity,
    reorder_level,
    low_stock_flag,
    updated_at,
    product_status
"""


def list_inventory(cursor, low_only=False, keyword=None):
    sql = "SELECT " + _INVENTORY_COLUMNS + " FROM dbo.vw_product_catalog WHERE product_status = 'ACTIVE'"
    params = []
    if low_only:
        sql += " AND low_stock_flag = 1"
    if keyword:
        like = "%" + keyword + "%"
        sql += " AND (product_name LIKE ? OR product_code LIKE ?)"
        params.extend([like, like])
    sql += " ORDER BY low_stock_flag DESC, product_code"
    return fetch_all(cursor, sql, tuple(params))


def lock_quantity(cursor, product_id):
    """加更新锁读取当前库存，防止并发下单造成超卖。"""
    return fetch_one(
        cursor,
        "SELECT quantity FROM dbo.inventory WITH (UPDLOCK, ROWLOCK) WHERE product_id = ?",
        (product_id,),
    )


def get_quantity(cursor, product_id):
    return fetch_one(
        cursor,
        "SELECT quantity FROM dbo.inventory WHERE product_id = ?",
        (product_id,),
    )


def decrease_quantity(cursor, product_id, amount):
    return execute(
        cursor,
        """
        UPDATE dbo.inventory
        SET quantity = quantity - ?, updated_at = SYSDATETIME()
        WHERE product_id = ?
        """,
        (amount, product_id),
    )


def set_quantity(cursor, product_id, quantity):
    return execute(
        cursor,
        """
        UPDATE dbo.inventory
        SET quantity = ?, updated_at = SYSDATETIME()
        WHERE product_id = ?
        """,
        (quantity, product_id),
    )


def insert_transaction(cursor, record):
    return execute(
        cursor,
        """
        INSERT INTO dbo.inventory_transaction
            (transaction_no, product_id, transaction_type, quantity_change,
             sales_order_id, purchase_order_id, operator_id, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["transaction_no"],
            record["product_id"],
            record["transaction_type"],
            record["quantity_change"],
            record.get("sales_order_id"),
            record.get("purchase_order_id"),
            record["operator_id"],
            record.get("remark"),
        ),
    )
