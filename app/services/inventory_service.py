"""库存查询与盘点调整业务。

业务规则：
1. 库存查询开放给店员、库存管理员和店长；顾客只能通过商品目录看到数量；
2. 库存调整只允许库存管理员和店长执行；
3. 调整数量时必须同时写入一条库存流水（盘盈 COUNT_GAIN / 盘亏 COUNT_LOSS），
   两者在同一事务中提交，保证“当前库存”和“变化依据”一致。
"""

import logging

from app.db import connection, inventory_dao, product_dao, transaction
from app.errors import BusinessRuleError, NotFoundError
from app.security import require_user
from app.services import validation as v
from app.services.serial import make_serial

logger = logging.getLogger(__name__)


def list_inventory(user, low_only=False, keyword=None):
    require_user("CASHIER", "INVENTORY", "MANAGER")
    with connection(user["role"]) as conn:
        cursor = conn.cursor()
        try:
            return inventory_dao.list_inventory(
                cursor,
                low_only=bool(low_only),
                keyword=(keyword or "").strip() or None,
            )
        finally:
            cursor.close()


def adjust_stock(user, payload):
    require_user("INVENTORY", "MANAGER")
    product_id = v.as_int(payload.get("product_id"), "product_id", "商品", minimum=1)
    new_quantity = v.as_int(
        payload.get("quantity"), "quantity", "盘点后数量", minimum=0, maximum=1000000
    )
    reason = v.as_text(
        payload.get("reason") or "库存盘点调整", "reason", "调整原因", max_length=200
    )

    with transaction(user["role"]) as conn:
        cursor = conn.cursor()
        try:
            product = product_dao.get_product(cursor, product_id)
            if product is None:
                raise NotFoundError("商品不存在")

            current = inventory_dao.lock_quantity(cursor, product_id)
            if current is None:
                raise NotFoundError("该商品没有库存记录")

            delta = new_quantity - current["quantity"]
            if delta == 0:
                raise BusinessRuleError("盘点数量与原库存相同，无需调整")

            inventory_dao.set_quantity(cursor, product_id, new_quantity)
            inventory_dao.insert_transaction(
                cursor,
                {
                    "transaction_no": make_serial("IT"),
                    "product_id": product_id,
                    "transaction_type": "COUNT_GAIN" if delta > 0 else "COUNT_LOSS",
                    "quantity_change": delta,
                    "sales_order_id": None,
                    "purchase_order_id": None,
                    "operator_id": user["employee_id"],
                    "remark": reason,
                },
            )
        finally:
            cursor.close()

    logger.info(
        "库存调整成功：product_id=%s，%s -> %s（变化 %s）",
        product_id,
        current["quantity"],
        new_quantity,
        delta,
    )
    return {
        "product_id": product_id,
        "product_name": product["product_name"],
        "before_quantity": current["quantity"],
        "after_quantity": new_quantity,
        "change": delta,
    }


def low_stock_products(user):
    require_user("CASHIER", "INVENTORY", "MANAGER")
    with connection(user["role"]) as conn:
        cursor = conn.cursor()
        try:
            return inventory_dao.list_inventory(cursor, low_only=True)
        finally:
            cursor.close()
