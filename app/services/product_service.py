"""商品维护业务。

业务规则：
1. 只有店长可以新增或修改商品，店员只能查询；
2. 商品编码固定为 P + 3 位数字，条码不得重复（与数据库检查约束一致）；
3. 新增商品时同时建立一条库存记录，避免出现“有商品没有库存”的孤立数据。
"""

import logging
from decimal import Decimal

from app.db import connection, product_dao, transaction
from app.errors import (
    ConstraintConflictError,
    NotFoundError,
    ValidationError,
)
from app.security import require_user
from app.services import validation as v

logger = logging.getLogger(__name__)

PRODUCT_CODE_PATTERN = r"^P[0-9]{3}$"
BARCODE_PATTERN = r"^[0-9]{8,32}$"
STATUS_CHOICES = ("ACTIVE", "INACTIVE")


def list_products(user, keyword=None, category_id=None, status=None):
    role = user["role"]
    with connection(role) as conn:
        cursor = conn.cursor()
        try:
            return product_dao.list_products(
                cursor,
                keyword=(keyword or "").strip() or None,
                category_id=category_id,
                status=status,
                only_active=(role == "CUSTOMER"),
            )
        finally:
            cursor.close()


def get_product(user, product_id):
    with connection(user["role"]) as conn:
        cursor = conn.cursor()
        try:
            product = product_dao.get_product(cursor, product_id)
        finally:
            cursor.close()
    if product is None:
        raise NotFoundError("商品不存在")
    return product


def list_categories(user):
    require_user("MANAGER", "CASHIER")
    with connection(user["role"]) as conn:
        cursor = conn.cursor()
        try:
            return product_dao.list_categories(cursor)
        finally:
            cursor.close()


def _validate_create_payload(payload):
    return {
        "product_code": v.as_text(
            payload.get("product_code"), "product_code", "商品编码",
            max_length=20, pattern=PRODUCT_CODE_PATTERN, pattern_hint="商品编码格式应为 P 加 3 位数字",
        ),
        "barcode": v.as_text(
            payload.get("barcode"), "barcode", "条码",
            max_length=32, pattern=BARCODE_PATTERN, pattern_hint="条码应为 8 至 32 位数字",
        ),
        "product_name": v.as_text(
            payload.get("product_name"), "product_name", "商品名称", max_length=100
        ),
        "category_id": v.as_int(payload.get("category_id"), "category_id", "商品分类", minimum=1),
        "unit": v.as_text(payload.get("unit"), "unit", "计量单位", max_length=10),
        "selling_price": v.as_money(payload.get("selling_price"), "selling_price", "销售单价"),
        "status": v.as_choice(payload.get("status") or "ACTIVE", STATUS_CHOICES, "status", "商品状态"),
        "quantity": v.as_int(payload.get("quantity") or 0, "quantity", "初始库存", minimum=0, maximum=1000000),
        "reorder_level": v.as_int(
            payload.get("reorder_level") or 10, "reorder_level", "补货预警值", minimum=0, maximum=1000000
        ),
    }


def create_product(user, payload):
    require_user("MANAGER")
    data = _validate_create_payload(payload)

    try:
        with transaction("MANAGER") as conn:
            cursor = conn.cursor()
            try:
                duplicate = product_dao.code_or_barcode_taken(
                    cursor, data["product_code"], data["barcode"]
                )
                if duplicate is not None:
                    raise ValidationError(
                        "商品编码或条码已被使用",
                        fields={"product_code": "已存在", "barcode": "已存在"},
                    )
                if product_dao.category_exists(cursor, data["category_id"]) is None:
                    raise ValidationError("所选分类不存在或已停用", fields={"category_id": "无效"})
                product_id = product_dao.insert_product(cursor, data)
                product_dao.insert_inventory(
                    cursor, product_id, data["quantity"], data["reorder_level"]
                )
            finally:
                cursor.close()
    except ConstraintConflictError as exc:
        logger.warning("新增商品触发数据库约束：%s", exc.log_detail)
        raise ValidationError("新增商品失败：商品编码、条码重复或分类不存在") from exc

    logger.info("新增商品成功：product_id=%s", product_id)
    return get_product(user, product_id)


def _validate_update_payload(payload):
    data = {}
    if "product_name" in payload:
        data["product_name"] = v.as_text(
            payload.get("product_name"), "product_name", "商品名称", max_length=100
        )
    if "category_id" in payload:
        data["category_id"] = v.as_int(
            payload.get("category_id"), "category_id", "商品分类", minimum=1
        )
    if "unit" in payload:
        data["unit"] = v.as_text(payload.get("unit"), "unit", "计量单位", max_length=10)
    if "selling_price" in payload:
        data["selling_price"] = v.as_money(
            payload.get("selling_price"), "selling_price", "销售单价"
        )
    if "status" in payload:
        data["status"] = v.as_choice(payload.get("status"), STATUS_CHOICES, "status", "商品状态")
    if not data:
        raise ValidationError("没有需要修改的内容")
    return data


def update_product(user, product_id, payload):
    require_user("MANAGER")
    data = _validate_update_payload(payload)

    try:
        with transaction("MANAGER") as conn:
            cursor = conn.cursor()
            try:
                if product_dao.get_product(cursor, product_id) is None:
                    raise NotFoundError("商品不存在")
                if "category_id" in data and product_dao.category_exists(
                    cursor, data["category_id"]
                ) is None:
                    raise ValidationError("所选分类不存在或已停用", fields={"category_id": "无效"})
                updated = product_dao.update_product(cursor, product_id, data)
                if updated == 0:
                    raise NotFoundError("商品不存在或未发生变化")
            finally:
                cursor.close()
    except ConstraintConflictError as exc:
        logger.warning("修改商品触发数据库约束：%s", exc.log_detail)
        raise ValidationError("修改失败：分类不存在或数据不满足约束") from exc

    logger.info("修改商品成功：product_id=%s，字段=%s", product_id, sorted(data))
    return get_product(user, product_id)


def price_for_order(product):
    """把数据库中的销售单价转换为订单计算使用的 Decimal。"""
    return Decimal(str(product["selling_price"])).quantize(Decimal("0.01"))
