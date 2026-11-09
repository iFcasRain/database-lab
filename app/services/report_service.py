"""经营分析业务：只对店长开放，数据来自已完成订单与库存视图。"""

from app.db import connection, inventory_dao, member_dao, order_dao, product_dao
from app.security import require_user


def summary(user):
    require_user("MANAGER")
    with connection("MANAGER") as conn:
        cursor = conn.cursor()
        try:
            today = order_dao.count_orders_today(cursor)
            total = order_dao.count_completed_orders(cursor)
            low_stock = inventory_dao.list_inventory(cursor, low_only=True)
            top = order_dao.top_products(cursor, limit=5)
            member_total = member_dao.count_members(cursor)
            product_total = product_dao.count_products(cursor)
        finally:
            cursor.close()

    return {
        "today": today,
        "total": total,
        "low_stock": low_stock,
        "low_stock_count": len(low_stock),
        "top_products": top,
        "member_count": member_total,
        "product_count": product_total,
    }
