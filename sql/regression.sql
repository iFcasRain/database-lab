/*
  第六周 regression.sql
  作用：迁移到 v1.0 之后，逐项核对关键标识、关系映射、订单金额、商品销量、库存、
        会员积分、应用账号和角色权限，确认迁移前后的业务含义没有改变。
  执行前提：
    1. 已执行 migration.sql；
    2. 已执行第四周 role.sql（本脚本复用它创建的 demo_ 演示用户）。
  结果：全部 check_result 为 PASS 时，最后一行显示“v1.0 回归通过”。
  说明：使用临时表 #regression / #approle_result 保存结果，使其跨 GO 批次可见。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
/* 权限用例需要故意触发拒绝错误，因此关闭 XACT_ABORT，便于在 CATCH 中清理事务。 */
SET XACT_ABORT OFF;
GO

IF OBJECT_ID(N'tempdb..#regression') IS NOT NULL DROP TABLE #regression;
IF OBJECT_ID(N'tempdb..#approle_result') IS NOT NULL DROP TABLE #approle_result;
GO

CREATE TABLE #regression
(
    check_no      INT IDENTITY(1, 1) PRIMARY KEY,
    check_item    NVARCHAR(160) NOT NULL,
    expected      NVARCHAR(100) NOT NULL,
    actual_value  NVARCHAR(100) NOT NULL,
    check_result  NVARCHAR(20) NOT NULL
);

/* ---------------- 1. 结构与对象：v0.1 的 12 张表 + v1.0 的 app_user ---------------- */

DECLARE @table_count INT =
(
    SELECT COUNT(*) FROM sys.tables WHERE schema_id = SCHEMA_ID(N'dbo')
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'业务表数量（v0.1 为 12，v1.0 为 13）', N'13', CONVERT(NVARCHAR(100), @table_count),
        CASE WHEN @table_count = 13 THEN N'PASS' ELSE N'FAIL' END);

DECLARE @view_count INT =
(
    SELECT COUNT(*)
    FROM sys.views
    WHERE schema_id = SCHEMA_ID(N'dbo')
      AND name IN
      (
          N'vw_order_detail', N'vw_product_sales_summary',
          N'vw_inventory_status', N'vw_member_consumption_summary',
          N'vw_product_catalog', N'vw_active_cashier', N'vw_order_summary'
      )
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'业务视图数量（4 个第四周视图 + 3 个应用视图）', N'7', CONVERT(NVARCHAR(100), @view_count),
        CASE WHEN @view_count = 7 THEN N'PASS' ELSE N'FAIL' END);

DECLARE @db_role_count INT =
(
    SELECT COUNT(*)
    FROM sys.database_principals
    WHERE type = 'R'
      AND name IN (N'store_manager_role', N'cashier_role', N'inventory_clerk_role',
                   N'auth_lookup_role', N'customer_app_role')
);

DECLARE @app_user_count INT =
(
    SELECT COUNT(*)
    FROM sys.database_principals
    WHERE type = 'S'
      AND name IN (N'app_auth', N'app_customer', N'app_cashier', N'app_inventory', N'app_manager')
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'数据库角色数量 / 应用账号数量', N'5 / 5',
        CONVERT(NVARCHAR(100), @db_role_count) + N' / ' + CONVERT(NVARCHAR(100), @app_user_count),
        CASE WHEN @db_role_count = 5 AND @app_user_count = 5 THEN N'PASS' ELSE N'FAIL' END);

/* ---------------- 2. 关键标识与关系映射：样例数据未因迁移而改变 ---------------- */

DECLARE @product_count INT = (SELECT COUNT(*) FROM dbo.product);
DECLARE @member_count  INT = (SELECT COUNT(*) FROM dbo.member);
DECLARE @employee_count INT = (SELECT COUNT(*) FROM dbo.employee);
DECLARE @order_count   INT = (SELECT COUNT(*) FROM dbo.sales_order);
DECLARE @item_count    INT = (SELECT COUNT(*) FROM dbo.sales_order_item);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'样例商品 / 会员 / 员工 / 订单 / 明细数量', N'3 / 3 / 3 / 3 / 5',
        CONVERT(NVARCHAR(100), @product_count) + N' / '
        + CONVERT(NVARCHAR(100), @member_count) + N' / '
        + CONVERT(NVARCHAR(100), @employee_count) + N' / '
        + CONVERT(NVARCHAR(100), @order_count) + N' / '
        + CONVERT(NVARCHAR(100), @item_count),
        CASE WHEN @product_count = 3 AND @member_count = 3 AND @employee_count = 3
                  AND @order_count = 3 AND @item_count = 5
             THEN N'PASS' ELSE N'FAIL' END);

DECLARE @orphan_item INT =
(
    SELECT COUNT(*)
    FROM dbo.sales_order_item AS oi
    LEFT JOIN dbo.sales_order AS o ON o.order_id = oi.order_id
    LEFT JOIN dbo.product AS p ON p.product_id = oi.product_id
    WHERE o.order_id IS NULL OR p.product_id IS NULL
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'孤立订单明细数量', N'0', CONVERT(NVARCHAR(100), @orphan_item),
        CASE WHEN @orphan_item = 0 THEN N'PASS' ELSE N'FAIL' END);

/* 一张订单至少一条明细：迁移不改变订单与明细的 1:N 基数。 */
DECLARE @order_without_item INT =
(
    SELECT COUNT(*)
    FROM dbo.sales_order AS o
    WHERE NOT EXISTS (SELECT 1 FROM dbo.sales_order_item AS oi WHERE oi.order_id = o.order_id)
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'没有任何明细的订单数量', N'0', CONVERT(NVARCHAR(100), @order_without_item),
        CASE WHEN @order_without_item = 0 THEN N'PASS' ELSE N'FAIL' END);

/* ---------------- 3. 订单金额：明细合计 = 原价，实付 = 原价 - 优惠 ---------------- */

DECLARE @bad_amount_order INT =
(
    SELECT COUNT(*)
    FROM dbo.sales_order AS o
    WHERE (o.order_status = 'COMPLETED' AND o.paid_amount <> o.original_amount - o.discount_amount)
       OR (o.order_status IN ('PENDING', 'CANCELLED') AND o.paid_amount <> 0)
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'金额规则异常订单数量', N'0', CONVERT(NVARCHAR(100), @bad_amount_order),
        CASE WHEN @bad_amount_order = 0 THEN N'PASS' ELSE N'FAIL' END);

DECLARE @bad_item_total INT =
(
    SELECT COUNT(*)
    FROM
    (
        SELECT o.order_id, o.original_amount, SUM(oi.quantity * oi.unit_price) AS item_total
        FROM dbo.sales_order AS o
        JOIN dbo.sales_order_item AS oi ON oi.order_id = o.order_id
        GROUP BY o.order_id, o.original_amount
    ) AS t
    WHERE t.original_amount <> t.item_total
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'订单原价与明细合计不一致的订单数量', N'0', CONVERT(NVARCHAR(100), @bad_item_total),
        CASE WHEN @bad_item_total = 0 THEN N'PASS' ELSE N'FAIL' END);

/* 关键查询：迁移前基线中 SO202609230001 的原价 7.50、优惠 0.50、实付 7.00。 */
DECLARE @sample_order_no VARCHAR(30) = 'SO202609230001';
DECLARE @sample_paid DECIMAL(10, 2) =
(
    SELECT paid_amount FROM dbo.sales_order WHERE order_no = @sample_order_no
);
DECLARE @sample_item_total DECIMAL(10, 2) =
(
    SELECT SUM(oi.quantity * oi.unit_price)
    FROM dbo.sales_order AS o
    JOIN dbo.sales_order_item AS oi ON oi.order_id = o.order_id
    WHERE o.order_no = @sample_order_no
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'关键查询：SO202609230001 实付 / 明细合计', N'7.00 / 7.50',
        CONVERT(NVARCHAR(100), @sample_paid) + N' / ' + CONVERT(NVARCHAR(100), @sample_item_total),
        CASE WHEN @sample_paid = 7.00 AND @sample_item_total = 7.50 THEN N'PASS' ELSE N'FAIL' END);

/* ---------------- 4. 商品销量与库存 ---------------- */

DECLARE @total_quantity_sold INT =
(
    SELECT SUM(oi.quantity)
    FROM dbo.sales_order_item AS oi
    JOIN dbo.sales_order AS o ON o.order_id = oi.order_id
    WHERE o.order_status = 'COMPLETED'
);

DECLARE @total_sales_amount DECIMAL(10, 2) =
(
    SELECT SUM(oi.quantity * oi.unit_price)
    FROM dbo.sales_order_item AS oi
    JOIN dbo.sales_order AS o ON o.order_id = oi.order_id
    WHERE o.order_status = 'COMPLETED'
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'关键查询：已完成订单销量合计 / 销售额合计', N'8 件 / 27.50 元',
        CONVERT(NVARCHAR(100), @total_quantity_sold) + N' 件 / '
        + CONVERT(NVARCHAR(100), @total_sales_amount) + N' 元',
        CASE WHEN @total_quantity_sold = 8 AND @total_sales_amount = 27.50 THEN N'PASS' ELSE N'FAIL' END);

DECLARE @per_product_ok INT =
(
    SELECT COUNT(*)
    FROM
    (
        SELECT p.product_code, SUM(oi.quantity) AS qty,
               CAST(SUM(oi.quantity * oi.unit_price) AS DECIMAL(10, 2)) AS amount
        FROM dbo.product AS p
        JOIN dbo.sales_order_item AS oi ON oi.product_id = p.product_id
        JOIN dbo.sales_order AS o ON o.order_id = oi.order_id AND o.order_status = 'COMPLETED'
        GROUP BY p.product_code
    ) AS s
    WHERE (s.product_code = 'P001' AND s.qty = 3 AND s.amount = 6.00)
       OR (s.product_code = 'P002' AND s.qty = 3 AND s.amount = 10.50)
       OR (s.product_code = 'P003' AND s.qty = 2 AND s.amount = 11.00)
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'逐商品销量与销售额命中数（P001/P002/P003）', N'3', CONVERT(NVARCHAR(100), @per_product_ok),
        CASE WHEN @per_product_ok = 3 THEN N'PASS' ELSE N'FAIL' END);

DECLARE @low_stock_count INT =
(
    SELECT COUNT(*) FROM dbo.vw_inventory_status WHERE inventory_status = N'需要补货'
);

DECLARE @milk_quantity INT =
(
    SELECT i.quantity
    FROM dbo.inventory AS i
    JOIN dbo.product AS p ON p.product_id = i.product_id
    WHERE p.product_code = 'P002'
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'低库存商品数量 / 纯牛奶现存数量', N'1 / 8',
        CONVERT(NVARCHAR(100), @low_stock_count) + N' / ' + CONVERT(NVARCHAR(100), @milk_quantity),
        CASE WHEN @low_stock_count = 1 AND @milk_quantity = 8 THEN N'PASS' ELSE N'FAIL' END);

DECLARE @negative_inventory INT = (SELECT COUNT(*) FROM dbo.inventory WHERE quantity < 0);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'负库存商品数量', N'0', CONVERT(NVARCHAR(100), @negative_inventory),
        CASE WHEN @negative_inventory = 0 THEN N'PASS' ELSE N'FAIL' END);

/* ---------------- 5. 会员积分：余额必须等于该会员最后一条流水的 balance_after ---------------- */

DECLARE @bad_points_chain INT =
(
    SELECT COUNT(*)
    FROM dbo.member AS m
    WHERE m.points_balance <>
    (
        SELECT TOP (1) pt.balance_after
        FROM dbo.points_transaction AS pt
        WHERE pt.member_id = m.member_id
        ORDER BY pt.points_transaction_id DESC
    )
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'积分余额与最后一条流水不一致的会员数量', N'0', CONVERT(NVARCHAR(100), @bad_points_chain),
        CASE WHEN @bad_points_chain = 0 THEN N'PASS' ELSE N'FAIL' END);

/* ---------------- 6. 应用账号：数量、身份约束与口令格式 ---------------- */

DECLARE @user_count INT = (SELECT COUNT(*) FROM dbo.app_user);

DECLARE @bad_user_identity INT =
(
    SELECT COUNT(*)
    FROM dbo.app_user
    WHERE
    (
        role = 'CUSTOMER' AND (member_id IS NULL OR employee_id IS NOT NULL)
    )
    OR
    (
        role <> 'CUSTOMER' AND (employee_id IS NULL OR member_id IS NOT NULL)
    )
);

DECLARE @bad_password_hash INT =
(
    SELECT COUNT(*) FROM dbo.app_user WHERE password_hash NOT LIKE N'pbkdf2_sha256$%'
);

INSERT INTO #regression (check_item, expected, actual_value, check_result)
VALUES (N'应用账号数量 / 身份违规 / 口令格式异常', N'5 / 0 / 0',
        CONVERT(NVARCHAR(100), @user_count) + N' / '
        + CONVERT(NVARCHAR(100), @bad_user_identity) + N' / '
        + CONVERT(NVARCHAR(100), @bad_password_hash),
        CASE WHEN @user_count = 5 AND @bad_user_identity = 0 AND @bad_password_hash = 0
             THEN N'PASS' ELSE N'FAIL' END);

/* ---------------- 7. 权限回归：第四周的授权与拒绝项未被迁移破坏 ---------------- */

/* 7.1 收银员查询商品：允许 */
BEGIN TRY
    EXECUTE AS USER = N'demo_cashier';
    SELECT COUNT(*) FROM dbo.product;
    REVERT;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：收银员查询商品', N'允许', N'允许', N'PASS');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'demo_cashier' REVERT;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：收银员查询商品', N'允许', N'拒绝', N'FAIL');
END CATCH;

/* 7.2 收银员修改售价：拒绝 */
BEGIN TRY
    BEGIN TRANSACTION;
    EXECUTE AS USER = N'demo_cashier';
    UPDATE dbo.product SET selling_price = selling_price + 1 WHERE product_id = 101;
    REVERT;
    ROLLBACK TRANSACTION;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：收银员修改商品售价', N'拒绝', N'允许', N'FAIL');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    IF USER_NAME() = N'demo_cashier' REVERT;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：收银员修改商品售价', N'拒绝', N'拒绝', N'PASS');
END CATCH;

/* 7.3 库存管理员查看会员资料：拒绝 */
BEGIN TRY
    EXECUTE AS USER = N'demo_inventory';
    SELECT COUNT(*) FROM dbo.member;
    REVERT;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：库存管理员查看会员资料', N'拒绝', N'允许', N'FAIL');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'demo_inventory' REVERT;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：库存管理员查看会员资料', N'拒绝', N'拒绝', N'PASS');
END CATCH;

/* 7.4 店长新增商品（测试后回滚）：允许 */
BEGIN TRY
    BEGIN TRANSACTION;
    EXECUTE AS USER = N'demo_manager';
    INSERT INTO dbo.product (product_code, barcode, product_name, category_id, unit, selling_price, status)
    VALUES ('P999', '6900000000999', N'回归测试商品', 1, N'件', 1.00, 'ACTIVE');
    REVERT;
    ROLLBACK TRANSACTION;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：店长新增商品', N'允许', N'允许', N'PASS');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    IF USER_NAME() = N'demo_manager' REVERT;
    INSERT INTO #regression (check_item, expected, actual_value, check_result)
    VALUES (N'权限：店长新增商品', N'允许', N'拒绝', N'FAIL');
END CATCH;

SELECT check_no, check_item, expected, actual_value, check_result
FROM #regression
ORDER BY check_no;
GO

/* ---------------- 8. 应用程序角色回归 ----------------
   sp_setapprole 不能在显式事务中执行，因此单独一个批次。 */

CREATE TABLE #approle_result
(
    check_no     INT IDENTITY(1, 1) PRIMARY KEY,
    check_item   NVARCHAR(160) NOT NULL,
    expected     NVARCHAR(100) NOT NULL,
    actual_value NVARCHAR(100) NOT NULL,
    check_result NVARCHAR(20) NOT NULL
);

/* 8.1 顾客应用账号可以查询商品目录视图 */
BEGIN TRY
    EXECUTE AS USER = N'app_customer';

    IF (SELECT COUNT(*) FROM dbo.vw_product_catalog) = 3
        INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
        VALUES (N'应用账号：顾客查询商品目录视图', N'允许', N'允许', N'PASS');
    ELSE
        INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
        VALUES (N'应用账号：顾客查询商品目录视图', N'允许', N'结果不符', N'FAIL');

    REVERT;
END TRY
BEGIN CATCH
    IF USER_NAME() = N'app_customer' REVERT;
    INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
    VALUES (N'应用账号：顾客查询商品目录视图', N'允许', N'拒绝', N'FAIL');
END CATCH;

/* 8.2 顾客应用账号不能直接把员工表当员工资料查询 */
BEGIN TRY
    EXECUTE AS USER = N'app_customer';
    SELECT COUNT(*) FROM dbo.employee;
    REVERT;
    INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
    VALUES (N'应用账号：顾客直接查询员工表', N'拒绝', N'允许', N'FAIL');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'app_customer' REVERT;
    INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
    VALUES (N'应用账号：顾客直接查询员工表', N'拒绝', N'拒绝', N'PASS');
END CATCH;

/* 8.3 店长应用账号读取经营汇总 */
BEGIN TRY
    EXECUTE AS USER = N'app_manager';
    DECLARE @manager_rows INT =
    (
        SELECT COUNT(*) FROM dbo.vw_product_sales_summary
    );
    REVERT;
    INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
    VALUES (N'应用账号：店长查询销售统计视图', N'允许', N'允许', N'PASS');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'app_manager' REVERT;
    INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
    VALUES (N'应用账号：店长查询销售统计视图', N'允许', N'拒绝', N'FAIL');
END CATCH;

/* 8.4 绑定关系：应用账号必须已加入对应数据库角色 */
DECLARE @app_user_members INT =
(
    SELECT COUNT(*)
    FROM sys.database_role_members AS drm
    JOIN sys.database_principals AS r ON r.principal_id = drm.role_principal_id
    JOIN sys.database_principals AS m ON m.principal_id = drm.member_principal_id
    WHERE (r.name = N'auth_lookup_role' AND m.name = N'app_auth')
       OR (r.name = N'customer_app_role' AND m.name = N'app_customer')
       OR (r.name = N'cashier_role' AND m.name = N'app_cashier')
       OR (r.name = N'inventory_clerk_role' AND m.name = N'app_inventory')
       OR (r.name = N'store_manager_role' AND m.name = N'app_manager')
);

INSERT INTO #approle_result (check_item, expected, actual_value, check_result)
VALUES (N'应用账号与角色的绑定数量', N'5', CONVERT(NVARCHAR(100), @app_user_members),
        CASE WHEN @app_user_members = 5 THEN N'PASS' ELSE N'FAIL' END);

SELECT check_no, check_item, expected, actual_value, check_result
FROM #approle_result
ORDER BY check_no;

/* ---------------- 9. 汇总 ---------------- */
SELECT
    SUM(CASE WHEN check_result = N'PASS' THEN 1 ELSE 0 END) AS pass_count,
    SUM(CASE WHEN check_result = N'FAIL' THEN 1 ELSE 0 END) AS fail_count,
    COUNT(*) AS total_count
FROM
(
    SELECT check_result FROM #regression
    UNION ALL
    SELECT check_result FROM #approle_result
) AS all_checks;

SELECT
    CASE
        WHEN (SELECT COUNT(*) FROM #regression WHERE check_result = N'FAIL') > 0
          OR (SELECT COUNT(*) FROM #approle_result WHERE check_result = N'FAIL') > 0
            THEN N'v1.0 回归未通过，请检查 FAIL 项'
        ELSE N'v1.0 回归通过'
    END AS final_result;

DROP TABLE #approle_result;
DROP TABLE #regression;
GO
