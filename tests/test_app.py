"""应用测试脚本（第 7—9 周）。

运行方式（在 database-lab 目录下）：

    python tests/test_app.py -v

覆盖场景：
    登录成功 / 登录失败 / 未登录访问 / 越权访问 / 参数校验 / 唯一键冲突 /
    库存不足导致事务回滚 / 门店结算下单 / 顾客线上下单 / 确认收款 /
    库存盘点调整 / SQL 注入尝试 / 访问不存在资源。

测试会真实写入数据库，因此 setUpModule 记录基线，tearDownModule 还原：
删除测试新增的订单、明细、库存流水、积分流水和商品，并把库存数量与会员积分恢复原值。
"""

import os
import sys
import unittest

import pyodbc

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402

import logging  # noqa: E402

# 测试报告需要清晰的用例列表，因此关闭运行日志输出（日志本身仍由应用正常运行产生）。
logging.disable(logging.CRITICAL)

PASSWORDS = {
    "manager01": "Manager@2026",
    "cashier01": "Cashier@2026",
    "stock01": "Stock@2026",
    "member01": "Member@2026",
    "member02": "Member@2026",
}

STATE = {}


def _connection_string():
    parts = [
        "DRIVER={%s}" % Config.DB_DRIVER,
        "SERVER=%s" % Config.DB_SERVER,
        "DATABASE=%s" % Config.DB_DATABASE,
    ]
    if Config.DB_TRUSTED_CONNECTION:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append("UID=%s" % Config.DB_USER)
        parts.append("PWD=%s" % Config.DB_PASSWORD)
    parts.append("Encrypt=%s" % Config.DB_ENCRYPT)
    parts.append("TrustServerCertificate=%s" % Config.DB_TRUST_SERVER_CERTIFICATE)
    return ";".join(parts) + ";"


def _raw_connection():
    return pyodbc.connect(_connection_string(), autocommit=True, timeout=5)


def setUpModule():
    app = create_app()
    app.config["TESTING"] = True
    STATE["app"] = app

    conn = _raw_connection()
    try:
        cursor = conn.cursor()

        def max_id(sql):
            cursor.execute(sql)
            return cursor.fetchone()[0] or 0

        STATE["max_order_id"] = max_id("SELECT MAX(order_id) FROM dbo.sales_order")
        STATE["max_item_id"] = max_id("SELECT MAX(order_item_id) FROM dbo.sales_order_item")
        STATE["max_inventory_tx"] = max_id(
            "SELECT MAX(inventory_transaction_id) FROM dbo.inventory_transaction"
        )
        STATE["max_points_tx"] = max_id(
            "SELECT MAX(points_transaction_id) FROM dbo.points_transaction"
        )
        STATE["max_product_id"] = max_id("SELECT MAX(product_id) FROM dbo.product")

        cursor.execute("SELECT product_id, quantity, updated_at FROM dbo.inventory")
        STATE["inventory"] = {
            row[0]: (row[1], row[2]) for row in cursor.fetchall()
        }

        cursor.execute("SELECT member_id, points_balance FROM dbo.member")
        STATE["points"] = {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()


def tearDownModule():
    conn = _raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM dbo.sales_order_item WHERE order_item_id > ?", STATE["max_item_id"]
        )
        cursor.execute(
            "DELETE FROM dbo.inventory_transaction WHERE inventory_transaction_id > ?",
            STATE["max_inventory_tx"],
        )
        cursor.execute(
            "DELETE FROM dbo.points_transaction WHERE points_transaction_id > ?",
            STATE["max_points_tx"],
        )
        cursor.execute(
            "DELETE FROM dbo.sales_order WHERE order_id > ?", STATE["max_order_id"]
        )
        cursor.execute(
            "DELETE FROM dbo.inventory WHERE product_id > ?", STATE["max_product_id"]
        )
        cursor.execute(
            "DELETE FROM dbo.product WHERE product_id > ?", STATE["max_product_id"]
        )
        for product_id, (quantity, updated_at) in STATE["inventory"].items():
            cursor.execute(
                "UPDATE dbo.inventory SET quantity = ?, updated_at = ? WHERE product_id = ?",
                quantity,
                updated_at,
                product_id,
            )
        for member_id, points in STATE["points"].items():
            cursor.execute(
                "UPDATE dbo.member SET points_balance = ? WHERE member_id = ?",
                points,
                member_id,
            )
        print("\n[清理] 测试数据已删除，库存与积分已恢复基线。")
    finally:
        conn.close()


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = STATE["app"]
        self.client = self.app.test_client()

    def login(self, username):
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": PASSWORDS[username]},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return self.client

    def logout(self):
        self.client.post("/api/auth/logout", json={})

    def product(self, code):
        response = self.client.get("/api/products?keyword=%s" % code)
        self.assertEqual(response.status_code, 200)
        items = [p for p in response.get_json()["data"] if p["product_code"] == code]
        self.assertTrue(items, "商品 %s 不存在" % code)
        return items[0]

    def inventory_quantity(self, product_id):
        response = self.client.get("/api/inventory")
        self.assertEqual(response.status_code, 200, response.get_json())
        rows = [row for row in response.get_json()["data"] if row["product_id"] == product_id]
        self.assertTrue(rows)
        return rows[0]["quantity"]

    def member_points(self, member_id):
        response = self.client.get("/api/members/%d" % member_id)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["data"]["points_balance"]


class LoginTests(ApiTestCase):
    def test_login_success(self):
        response = self.client.post(
            "/api/auth/login",
            json={"username": "cashier01", "password": PASSWORDS["cashier01"]},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["role"], "CASHIER")
        self.assertEqual(payload["data"]["role_label"], "店员")

    def test_login_wrong_password(self):
        response = self.client.post(
            "/api/auth/login", json={"username": "cashier01", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"]["code"], "AUTH_FAILED")

    def test_login_unknown_user(self):
        response = self.client.post(
            "/api/auth/login", json={"username": "nobody", "password": "whatever"}
        )
        self.assertEqual(response.status_code, 401)

    def test_login_missing_fields(self):
        response = self.client.post("/api/auth/login", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_api_requires_login(self):
        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, 401)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], "AUTH_REQUIRED")
        self.assertIn("request_id", body)

    def test_page_redirects_to_login(self):
        response = self.client.get("/orders")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_unknown_api_returns_404(self):
        self.login("cashier01")
        response = self.client.get("/api/not-exists")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"]["code"], "NOT_FOUND")


class PermissionTests(ApiTestCase):
    def test_customer_cannot_create_product(self):
        self.login("member01")
        response = self.client.post(
            "/api/products",
            json={
                "product_code": "P901",
                "barcode": "6900000009011",
                "product_name": "越权商品",
                "category_id": 1,
                "unit": "件",
                "selling_price": 1.00,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"]["code"], "FORBIDDEN")

    def test_cashier_cannot_create_product(self):
        self.login("cashier01")
        response = self.client.post(
            "/api/products",
            json={
                "product_code": "P902",
                "barcode": "6900000009028",
                "product_name": "店员越权商品",
                "category_id": 1,
                "unit": "件",
                "selling_price": 1.00,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_view_inventory_module(self):
        self.login("member01")
        response = self.client.get("/api/inventory")
        self.assertEqual(response.status_code, 403)

    def test_inventory_clerk_cannot_view_orders(self):
        self.login("stock01")
        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"]["code"], "FORBIDDEN")

    def test_cashier_cannot_adjust_stock(self):
        self.login("cashier01")
        response = self.client.post(
            "/api/inventory/adjust", json={"product_id": 101, "quantity": 10}
        )
        self.assertEqual(response.status_code, 403)

    def test_page_forbidden_returns_error_page(self):
        self.login("member01")
        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 403)
        self.assertIn("当前角色", response.get_data(as_text=True))


class ValidationAndConstraintTests(ApiTestCase):
    def test_negative_price_rejected(self):
        self.login("manager01")
        response = self.client.post(
            "/api/products",
            json={
                "product_code": "P903",
                "barcode": "6900000009035",
                "product_name": "负价格商品",
                "category_id": 1,
                "unit": "件",
                "selling_price": -1,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_bad_product_code_format_rejected(self):
        self.login("manager01")
        response = self.client.post(
            "/api/products",
            json={
                "product_code": "X1",
                "barcode": "6900000009042",
                "product_name": "编码格式错误",
                "category_id": 1,
                "unit": "件",
                "selling_price": 1,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_product_code_rejected(self):
        self.login("manager01")
        response = self.client.post(
            "/api/products",
            json={
                "product_code": "P001",
                "barcode": "6900000009059",
                "product_name": "重复编码商品",
                "category_id": 1,
                "unit": "件",
                "selling_price": 1,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("已被使用", response.get_json()["error"]["message"])

    def test_unknown_category_rejected(self):
        self.login("manager01")
        response = self.client.post(
            "/api/products",
            json={
                "product_code": "P904",
                "barcode": "6900000009066",
                "product_name": "不存在的分类",
                "category_id": 999,
                "unit": "件",
                "selling_price": 1,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_zero_quantity_order_rejected(self):
        self.login("cashier01")
        response = self.client.post(
            "/api/orders",
            json={"items": [{"product_id": 101, "quantity": 0}], "payment_method": "CASH"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "VALIDATION_ERROR")

    def test_empty_items_rejected(self):
        self.login("cashier01")
        response = self.client.post("/api/orders", json={"items": [], "payment_method": "CASH"})
        self.assertEqual(response.status_code, 400)

    def test_bad_payment_method_rejected(self):
        self.login("cashier01")
        response = self.client.post(
            "/api/orders",
            json={"items": [{"product_id": 101, "quantity": 1}], "payment_method": "BITCOIN"},
        )
        self.assertEqual(response.status_code, 400)

    def test_sql_injection_keyword_returns_no_rows(self):
        self.login("cashier01")
        response = self.client.get("/api/products?keyword=%27%20OR%201=1%20--")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"], [])


class OrderFlowTests(ApiTestCase):
    def test_insufficient_stock_rolls_back(self):
        self.login("cashier01")
        before = self.inventory_quantity(101)
        response = self.client.post(
            "/api/orders",
            json={"items": [{"product_id": 101, "quantity": 900}], "payment_method": "CASH"},
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "BUSINESS_RULE_VIOLATION")
        self.assertEqual(self.inventory_quantity(101), before, "库存不足时不应改变库存")

    def test_store_order_completes_and_deducts_stock(self):
        self.login("cashier01")
        before = self.inventory_quantity(101)
        points_before = self.member_points(201)

        response = self.client.post(
            "/api/orders",
            json={
                "items": [{"product_id": 101, "quantity": 2}],
                "payment_method": "CASH",
                "member_no": "M001",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()["data"]
        self.assertEqual(order["order_status"], "COMPLETED")
        self.assertEqual(order["paid_amount"], 4.0)
        self.assertEqual(len(order["items"]), 1)

        self.assertEqual(self.inventory_quantity(101), before - 2, "下单后库存应扣减")
        self.assertEqual(self.member_points(201), points_before + 4, "会员应获得 4 积分")

    def test_member_points_redeem(self):
        self.login("cashier01")
        points_before = self.member_points(201)
        response = self.client.post(
            "/api/orders",
            json={
                "items": [{"product_id": 101, "quantity": 3}],
                "payment_method": "MOBILE",
                "member_no": "M001",
                "redeem_points": 10,
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        order = response.get_json()["data"]
        self.assertEqual(order["original_amount"], 6.0)
        self.assertEqual(order["discount_amount"], 1.0)
        self.assertEqual(order["paid_amount"], 5.0)
        self.assertEqual(self.member_points(201), points_before - 10 + 5)

    def test_redeem_points_not_multiple_of_ten(self):
        self.login("cashier01")
        response = self.client.post(
            "/api/orders",
            json={
                "items": [{"product_id": 101, "quantity": 1}],
                "payment_method": "CASH",
                "member_no": "M001",
                "redeem_points": 5,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_online_order_pending_then_confirm(self):
        self.client.post(
            "/api/auth/login",
            json={"username": "member01", "password": PASSWORDS["member01"]},
        )
        stock_before = None
        response = self.client.get("/api/products?keyword=P003")
        stock_before = [p for p in response.get_json()["data"] if p["product_code"] == "P003"][0][
            "quantity"
        ]

        created = self.client.post(
            "/api/orders", json={"items": [{"product_id": 103, "quantity": 1}]}
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        order = created.get_json()["data"]
        self.assertEqual(order["order_status"], "PENDING")
        self.assertEqual(order["paid_amount"], 0.0)
        order_id = order["order_id"]

        # 顾客下单不扣库存
        response = self.client.get("/api/products?keyword=P003")
        after_order = [p for p in response.get_json()["data"] if p["product_code"] == "P003"][0][
            "quantity"
        ]
        self.assertEqual(after_order, stock_before, "待支付订单不应扣减库存")

        self.logout()
        self.login("cashier01")
        confirmed = self.client.post(
            "/api/orders/%d/confirm" % order_id, json={"payment_method": "CASH"}
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.get_json())
        self.assertEqual(confirmed.get_json()["data"]["order_status"], "COMPLETED")
        self.assertEqual(self.inventory_quantity(103), after_order - 1, "确认收款后应扣减库存")

    def test_customer_cannot_see_other_member_order(self):
        self.login("cashier01")
        created = self.client.post(
            "/api/orders",
            json={
                "items": [{"product_id": 101, "quantity": 1}],
                "payment_method": "CASH",
                "member_no": "M001",
            },
        )
        order_id = created.get_json()["data"]["order_id"]

        self.logout()
        self.login("member02")
        response = self.client.get("/api/orders/%d" % order_id)
        self.assertEqual(response.status_code, 404)

    def test_cancel_pending_order(self):
        self.client.post(
            "/api/auth/login",
            json={"username": "member01", "password": PASSWORDS["member01"]},
        )
        created = self.client.post(
            "/api/orders", json={"items": [{"product_id": 102, "quantity": 1}]}
        )
        order_id = created.get_json()["data"]["order_id"]
        cancelled = self.client.post("/api/orders/%d/cancel" % order_id, json={})
        self.assertEqual(cancelled.status_code, 200, cancelled.get_json())
        self.assertEqual(cancelled.get_json()["data"]["order_status"], "CANCELLED")

    def test_cannot_confirm_completed_order(self):
        self.login("cashier01")
        created = self.client.post(
            "/api/orders",
            json={"items": [{"product_id": 101, "quantity": 1}], "payment_method": "CASH"},
        )
        order_id = created.get_json()["data"]["order_id"]
        again = self.client.post(
            "/api/orders/%d/confirm" % order_id, json={"payment_method": "CASH"}
        )
        self.assertEqual(again.status_code, 409)


class InventoryTests(ApiTestCase):
    def test_inventory_clerk_can_adjust_stock(self):
        self.login("stock01")
        before = self.inventory_quantity(102)
        target = before + 5
        response = self.client.post(
            "/api/inventory/adjust",
            json={"product_id": 102, "quantity": target, "reason": "自动化测试盘点"},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["before_quantity"], before)
        self.assertEqual(data["after_quantity"], target)
        self.assertEqual(self.inventory_quantity(102), target)

    def test_adjust_without_change_rejected(self):
        self.login("stock01")
        current = self.inventory_quantity(102)
        response = self.client.post(
            "/api/inventory/adjust", json={"product_id": 102, "quantity": current}
        )
        self.assertEqual(response.status_code, 409)

    def test_negative_inventory_rejected(self):
        self.login("stock01")
        response = self.client.post(
            "/api/inventory/adjust", json={"product_id": 102, "quantity": -1}
        )
        self.assertEqual(response.status_code, 400)


class ReportTests(ApiTestCase):
    def test_manager_can_read_summary(self):
        self.login("manager01")
        response = self.client.get("/api/reports/summary")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertIn("today", data)
        self.assertIn("top_products", data)

    def test_cashier_cannot_read_summary(self):
        self.login("cashier01")
        response = self.client.get("/api/reports/summary")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
