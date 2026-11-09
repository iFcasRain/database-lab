"""订单业务：下单、确认收款、取消与查询。

事务边界（第 7—9 周的重点）：
1. 门店结算下单：写订单 + 写订单明细 + 扣减库存 + 写库存流水 + 结算积分，
   全部在同一个事务中提交；任何一步失败都整体回滚。
2. 顾客线上下单：只写订单与明细，状态为 PENDING，不扣库存、不结算积分。
3. 店员确认收款：PENDING → COMPLETED，此时才扣库存并结算积分。
4. 取消订单：只有 PENDING 订单可以取消，取消不产生任何库存或积分变化。
"""

import logging
from decimal import Decimal

from flask import current_app

from app.db import connection, inventory_dao, member_dao, order_dao, product_dao, transaction
from app.errors import (
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.security import require_user
from app.services import validation as v
from app.services.serial import make_order_no, make_serial

logger = logging.getLogger(__name__)

PAYMENT_METHODS = ("CASH", "MOBILE", "CARD")
PAYMENT_LABELS = {"CASH": "现金", "MOBILE": "移动支付", "CARD": "银行卡"}
ORDER_STATUS_LABELS = {
    "PENDING": "待支付",
    "COMPLETED": "已完成",
    "CANCELLED": "已取消",
}
MAX_ITEMS = 50
MAX_QUANTITY = 999


def _role_key(user):
    return user["role"]


def list_orders(user, status=None, keyword=None):
    role = user["role"]
    if role == "INVENTORY":
        raise ForbiddenError("库存管理员不能查看销售订单")

    member_id = user["member_id"] if role == "CUSTOMER" else None
    with connection(role) as conn:
        cursor = conn.cursor()
        try:
            rows = order_dao.list_orders(
                cursor,
                member_id=member_id,
                status=(status or "").strip() or None,
                keyword=(keyword or "").strip() or None,
            )
        finally:
            cursor.close()
    return [_decorate_order(row) for row in rows]


def _decorate_order(row):
    row = dict(row)
    row["status_label"] = ORDER_STATUS_LABELS.get(row.get("order_status"), row.get("order_status"))
    row["payment_label"] = PAYMENT_LABELS.get(row.get("payment_method"), row.get("payment_method") or "")
    return row


def get_order_detail(user, order_id):
    role = user["role"]
    if role == "INVENTORY":
        raise ForbiddenError("库存管理员不能查看销售订单")

    member_id = user["member_id"] if role == "CUSTOMER" else None
    with connection(role) as conn:
        cursor = conn.cursor()
        try:
            order = order_dao.get_order(cursor, order_id, member_id=member_id)
            if order is None:
                raise NotFoundError("订单不存在或不属于当前账号")
            items = order_dao.list_items(cursor, order_id)
        finally:
            cursor.close()

    order = _decorate_order(order)
    order["items"] = items
    order["can_confirm"] = (
        order["order_status"] == "PENDING" and role in ("CASHIER", "MANAGER")
    )
    order["can_cancel"] = order["order_status"] == "PENDING" and (
        role in ("CASHIER", "MANAGER") or (role == "CUSTOMER" and member_id is not None)
    )
    return order


def _parse_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items:
        raise ValidationError("请至少选择一件商品", fields={"items": "至少一件"})
    if len(raw_items) > MAX_ITEMS:
        raise ValidationError("一张订单最多包含 %d 种商品" % MAX_ITEMS, fields={"items": "超出上限"})

    merged = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValidationError("订单明细格式不正确")
        product_id = v.as_int(raw.get("product_id"), "items", "商品", minimum=1)
        quantity = v.as_int(
            raw.get("quantity"), "items", "购买数量", minimum=1, maximum=MAX_QUANTITY
        )
        merged[product_id] = merged.get(product_id, 0) + quantity
    return merged


def _collect_lines(cursor, merged_items, *, check_stock, lock_stock=True):
    """按数据库中的当前价格计算明细与金额，不信任前端传来的价格。

    lock_stock=True 时会加更新锁读取库存，用于真正扣减库存的结算流程；
    顾客线上下单不扣库存，直接读取商品目录里的当前数量即可。
    """
    lines = []
    total = Decimal("0.00")
    for product_id, quantity in merged_items.items():
        product = product_dao.get_product(cursor, product_id)
        if product is None:
            raise NotFoundError("商品不存在或已下架")
        if product["product_status"] != "ACTIVE":
            raise BusinessRuleError("「%s」已停用，不能销售" % product["product_name"])

        if check_stock:
            if lock_stock:
                stock = inventory_dao.lock_quantity(cursor, product_id)
                available = stock["quantity"] if stock else 0
            else:
                available = product["quantity"]
            if available < quantity:
                raise BusinessRuleError(
                    "「%s」库存不足，当前可售 %d 件" % (product["product_name"], available),
                    fields={"items": "库存不足"},
                )

        unit_price = Decimal(str(product["selling_price"])).quantize(Decimal("0.01"))
        line_amount = (unit_price * quantity).quantize(Decimal("0.01"))
        total += line_amount
        lines.append(
            {
                "product_id": product_id,
                "product_code": product["product_code"],
                "product_name": product["product_name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "line_amount": line_amount,
            }
        )
    return lines, total


def _resolve_member(cursor, member_no):
    member_no = (member_no or "").strip()
    if not member_no:
        return None
    member = member_dao.find_by_member_no(cursor, member_no)
    if member is None:
        raise NotFoundError("会员号不存在：%s" % member_no)
    if member["status"] != "ACTIVE":
        raise BusinessRuleError("该会员已停用，不能参与本次交易")
    return member


def _points_plan(member, redeem_points, total):
    """计算积分抵扣与累积，返回 (discount, paid, redeem, earn)。"""
    config = current_app.config
    yuan_per_step = max(1, config["POINTS_PER_DISCOUNT_YUAN"])
    points_per_yuan = max(0, config["POINTS_PER_YUAN"])

    if member is None:
        if redeem_points:
            raise ValidationError("非会员订单不能使用积分抵扣", fields={"redeem_points": "不可用"})
        return Decimal("0.00"), total, 0, 0

    balance = int(member["points_balance"] or 0)
    discount = Decimal("0.00")
    if redeem_points:
        if redeem_points % yuan_per_step != 0:
            raise ValidationError(
                "积分抵扣需为 %d 的整数倍" % yuan_per_step,
                fields={"redeem_points": "必须为整数倍"},
            )
        if redeem_points > balance:
            raise BusinessRuleError(
                "会员积分不足，当前可用 %d 分" % balance, fields={"redeem_points": "积分不足"}
            )
        discount = (Decimal(redeem_points) / Decimal(yuan_per_step)).quantize(Decimal("0.01"))
        if discount > total:
            raise BusinessRuleError("抵扣金额不能超过订单金额", fields={"redeem_points": "超出订单金额"})

    paid = (total - discount).quantize(Decimal("0.01"))
    earn = int(paid) * points_per_yuan if points_per_yuan else 0
    return discount, paid, redeem_points, earn


def _write_points(cursor, member, order_id, redeem_points, earn_points):
    balance = int(member["points_balance"] or 0)
    if redeem_points:
        balance -= redeem_points
        member_dao.insert_points_transaction(
            cursor,
            {
                "transaction_no": make_serial("PT"),
                "member_id": member["member_id"],
                "order_id": order_id,
                "change_type": "REDEEM",
                "points_change": -redeem_points,
                "balance_after": balance,
                "remark": "订单积分抵扣",
            },
        )
    if earn_points:
        balance += earn_points
        member_dao.insert_points_transaction(
            cursor,
            {
                "transaction_no": make_serial("PT"),
                "member_id": member["member_id"],
                "order_id": order_id,
                "change_type": "EARN",
                "points_change": earn_points,
                "balance_after": balance,
                "remark": "完成订单获得积分",
            },
        )
    member_dao.update_points(cursor, member["member_id"], balance)
    return balance


def _write_sale_out(cursor, order_id, lines, operator_id):
    for line in lines:
        inventory_dao.decrease_quantity(cursor, line["product_id"], line["quantity"])
        inventory_dao.insert_transaction(
            cursor,
            {
                "transaction_no": make_serial("IT"),
                "product_id": line["product_id"],
                "transaction_type": "SALE_OUT",
                "quantity_change": -line["quantity"],
                "sales_order_id": order_id,
                "purchase_order_id": None,
                "operator_id": operator_id,
                "remark": "订单销售出库",
            },
        )


def create_order(user, payload):
    """创建订单。店员/店长直接结算完成；顾客为线上下单（待支付）。"""
    role = user["role"]
    if role in ("CASHIER", "MANAGER"):
        return _create_store_order(user, payload)
    if role == "CUSTOMER":
        return _create_online_order(user, payload)
    raise ForbiddenError("当前角色不能创建订单")


def _create_store_order(user, payload):
    merged = _parse_items(payload.get("items"))
    payment_method = v.as_choice(
        payload.get("payment_method"), PAYMENT_METHODS, "payment_method", "支付方式"
    )
    redeem_points = v.as_int(
        payload.get("redeem_points") or 0, "redeem_points", "抵扣积分", minimum=0, maximum=1000000
    )
    cashier_id = user["employee_id"]
    if not cashier_id:
        raise ForbiddenError("当前账号没有关联员工，不能作为经办人")

    with transaction(_role_key(user)) as conn:
        cursor = conn.cursor()
        try:
            lines, total = _collect_lines(cursor, merged, check_stock=True)
            member = _resolve_member(cursor, payload.get("member_no"))
            discount, paid, redeem, earn = _points_plan(member, redeem_points, total)

            sequence = order_dao.next_order_sequence(cursor, make_order_no(0)[:-4])
            order_no = make_order_no(sequence)
            order_id = order_dao.insert_order(
                cursor,
                {
                    "order_no": order_no,
                    "member_id": member["member_id"] if member else None,
                    "cashier_id": cashier_id,
                    "order_status": "COMPLETED",
                    "payment_method": payment_method,
                    "original_amount": total,
                    "discount_amount": discount,
                    "paid_amount": paid,
                },
            )
            for line in lines:
                order_dao.insert_item(
                    cursor, order_id, line["product_id"], line["quantity"], line["unit_price"]
                )
            _write_sale_out(cursor, order_id, lines, cashier_id)
            if member:
                _write_points(cursor, member, order_id, redeem, earn)
        finally:
            cursor.close()

    logger.info(
        "门店下单成功：order_no=%s，金额=%s，明细=%d 项，经办=%s",
        order_no, paid, len(lines), cashier_id,
    )
    return get_order_detail(user, order_id)


def _create_online_order(user, payload):
    member_id = user["member_id"]
    if not member_id:
        raise ForbiddenError("当前顾客账号没有关联会员，不能下单")

    merged = _parse_items(payload.get("items"))

    with transaction("CUSTOMER") as conn:
        cursor = conn.cursor()
        try:
            cashier = order_dao.pick_on_duty_cashier(cursor)
            if cashier is None:
                raise BusinessRuleError("当前没有在职收银员，暂时无法接单")
            lines, total = _collect_lines(cursor, merged, check_stock=True, lock_stock=False)

            sequence = order_dao.next_order_sequence(cursor, make_order_no(0)[:-4])
            order_no = make_order_no(sequence)
            order_id = order_dao.insert_order(
                cursor,
                {
                    "order_no": order_no,
                    "member_id": member_id,
                    "cashier_id": cashier["employee_id"],
                    "order_status": "PENDING",
                    "payment_method": None,
                    "original_amount": total,
                    "discount_amount": Decimal("0.00"),
                    "paid_amount": Decimal("0.00"),
                },
            )
            for line in lines:
                order_dao.insert_item(
                    cursor, order_id, line["product_id"], line["quantity"], line["unit_price"]
                )
        finally:
            cursor.close()

    logger.info(
        "顾客线上下单成功：order_no=%s，金额=%s，经办收银员=%s",
        order_no, total, cashier["employee_id"],
    )
    return get_order_detail(user, order_id)


def confirm_order(user, order_id, payload):
    """店员确认收款：待支付订单转为已完成，并在此刻扣减库存、结算积分。"""
    require_user("CASHIER", "MANAGER")
    payment_method = v.as_choice(
        payload.get("payment_method") or "CASH", PAYMENT_METHODS, "payment_method", "支付方式"
    )
    redeem_points = v.as_int(
        payload.get("redeem_points") or 0, "redeem_points", "抵扣积分", minimum=0, maximum=1000000
    )
    operator_id = user["employee_id"]

    with transaction(user["role"]) as conn:
        cursor = conn.cursor()
        try:
            order = order_dao.get_order(cursor, order_id)
            if order is None:
                raise NotFoundError("订单不存在")
            if order["order_status"] != "PENDING":
                raise BusinessRuleError(
                    "订单当前状态为「%s」，不能确认收款"
                    % ORDER_STATUS_LABELS.get(order["order_status"], order["order_status"])
                )

            items = order_dao.list_item_prices(cursor, order_id)
            if not items:
                raise BusinessRuleError("订单没有任何明细，不能确认收款")

            lines = []
            for item in items:
                product = product_dao.get_product(cursor, item["product_id"])
                if product is None or product["product_status"] != "ACTIVE":
                    raise BusinessRuleError("订单中的商品已停用或不存在，不能确认收款")
                stock = inventory_dao.lock_quantity(cursor, item["product_id"])
                available = stock["quantity"] if stock else 0
                if available < item["quantity"]:
                    raise BusinessRuleError(
                        "「%s」库存不足，当前可售 %d 件" % (product["product_name"], available)
                    )
                lines.append(
                    {
                        "product_id": item["product_id"],
                        "quantity": item["quantity"],
                        "unit_price": item["unit_price"],
                    }
                )

            total = Decimal(str(order["original_amount"])).quantize(Decimal("0.01"))
            member = (
                member_dao.get_member(cursor, order["member_id"])
                if order["member_id"]
                else None
            )
            discount, paid, redeem, earn = _points_plan(member, redeem_points, total)

            updated = order_dao.complete_order(cursor, order_id, payment_method, paid, discount)
            if updated == 0:
                raise BusinessRuleError("订单状态已被其他操作改变，请刷新后重试")

            _write_sale_out(cursor, order_id, lines, operator_id)
            if member:
                _write_points(cursor, member, order_id, redeem, earn)
        finally:
            cursor.close()

    logger.info("确认收款成功：order_id=%s，实付=%s", order_id, paid)
    return get_order_detail(user, order_id)


def cancel_order(user, order_id):
    role = user["role"]
    member_id = user["member_id"] if role == "CUSTOMER" else None
    if role not in ("CASHIER", "MANAGER", "CUSTOMER"):
        raise ForbiddenError("当前角色不能取消订单")

    with transaction(role) as conn:
        cursor = conn.cursor()
        try:
            order = order_dao.get_order(cursor, order_id, member_id=member_id)
            if order is None:
                raise NotFoundError("订单不存在或不属于当前账号")
            if order["order_status"] != "PENDING":
                raise BusinessRuleError("只有待支付订单可以取消")

            updated = order_dao.cancel_order(cursor, order_id)
            if updated == 0:
                raise BusinessRuleError("订单状态已被其他操作改变，请刷新后重试")
        finally:
            cursor.close()

    logger.info("取消订单成功：order_id=%s，操作人=%s", order_id, user["username"])
    return get_order_detail(user, order_id)


def order_status_options():
    return [
        {"value": key, "label": label}
        for key, label in ORDER_STATUS_LABELS.items()
    ]


def payment_options():
    return [
        {"value": key, "label": label}
        for key, label in PAYMENT_LABELS.items()
    ]
