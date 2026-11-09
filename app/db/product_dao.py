"""商品与分类数据访问。"""

from app.db.base import execute, fetch_all, fetch_one, insert_returning

_CATALOG_COLUMNS = """
    product_id,
    product_code,
    barcode,
    product_name,
    category_id,
    category_name,
    unit,
    selling_price,
    product_status,
    quantity,
    reorder_level,
    updated_at,
    low_stock_flag
"""


def list_products(cursor, keyword=None, category_id=None, status=None, only_active=False):
    sql = "SELECT " + _CATALOG_COLUMNS + " FROM dbo.vw_product_catalog WHERE 1 = 1"
    params = []
    if keyword:
        like = "%" + keyword + "%"
        sql += " AND (product_name LIKE ? OR product_code LIKE ? OR barcode LIKE ?)"
        params.extend([like, like, like])
    if category_id:
        sql += " AND category_id = ?"
        params.append(category_id)
    if status:
        sql += " AND product_status = ?"
        params.append(status)
    if only_active:
        sql += " AND product_status = 'ACTIVE'"
    sql += " ORDER BY product_code"
    return fetch_all(cursor, sql, tuple(params))


def get_product(cursor, product_id):
    return fetch_one(
        cursor,
        "SELECT " + _CATALOG_COLUMNS + " FROM dbo.vw_product_catalog WHERE product_id = ?",
        (product_id,),
    )


def list_categories(cursor):
    return fetch_all(
        cursor,
        """
        SELECT category_id, category_code, category_name, status
        FROM dbo.category
        ORDER BY category_id
        """,
    )


def category_exists(cursor, category_id):
    return fetch_one(
        cursor,
        "SELECT category_id FROM dbo.category WHERE category_id = ? AND status = 'ACTIVE'",
        (category_id,),
    )


def code_or_barcode_taken(cursor, product_code, barcode):
    return fetch_one(
        cursor,
        """
        SELECT product_code, barcode
        FROM dbo.product
        WHERE product_code = ? OR barcode = ?
        """,
        (product_code, barcode),
    )


def insert_product(cursor, data):
    return insert_returning(
        cursor,
        """
        INSERT INTO dbo.product
            (product_code, barcode, product_name, category_id, unit, selling_price, status)
        OUTPUT INSERTED.product_id
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["product_code"],
            data["barcode"],
            data["product_name"],
            data["category_id"],
            data["unit"],
            data["selling_price"],
            data["status"],
        ),
    )


def insert_inventory(cursor, product_id, quantity, reorder_level):
    return execute(
        cursor,
        """
        INSERT INTO dbo.inventory (product_id, quantity, reorder_level)
        VALUES (?, ?, ?)
        """,
        (product_id, quantity, reorder_level),
    )


def update_product(cursor, product_id, data):
    assignments = []
    params = []
    for column in ("product_name", "category_id", "unit", "selling_price", "status"):
        if column in data:
            assignments.append(column + " = ?")
            params.append(data[column])
    if not assignments:
        return 0
    params.append(product_id)
    return execute(
        cursor,
        "UPDATE dbo.product SET " + ", ".join(assignments) + " WHERE product_id = ?",
        tuple(params),
    )


def count_products(cursor):
    row = fetch_one(cursor, "SELECT COUNT(*) AS total FROM dbo.product")
    return row["total"] if row else 0
