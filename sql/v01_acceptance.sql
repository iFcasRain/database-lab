/*
  v0.1 阶段验收脚本
  执行前提：已经依次运行第三周脚本和第四周四个脚本。
  作用：集中检查表、视图、角色、样例数据和关键业务结果。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
GO

DECLARE @acceptance TABLE
(
    check_no      INT IDENTITY(1, 1) PRIMARY KEY,
    check_item    NVARCHAR(120) NOT NULL,
    expected      NVARCHAR(100) NOT NULL,
    actual_value  NVARCHAR(100) NOT NULL,
    check_result  NVARCHAR(20) NOT NULL
);

DECLARE @table_count INT =
(
    SELECT COUNT(*)
    FROM sys.tables
    WHERE schema_id = SCHEMA_ID(N'dbo')
);

INSERT INTO @acceptance (check_item, expected, actual_value, check_result)
VALUES
(
    N'业务表数量', N'12', CONVERT(NVARCHAR(100), @table_count),
    CASE WHEN @table_count = 12 THEN N'PASS' ELSE N'FAIL' END
);

DECLARE @view_count INT =
(
    SELECT COUNT(*)
    FROM sys.views
    WHERE schema_id = SCHEMA_ID(N'dbo')
      AND name IN
      (
          N'vw_order_detail',
          N'vw_product_sales_summary',
          N'vw_inventory_status',
          N'vw_member_consumption_summary'
      )
);

INSERT INTO @acceptance (check_item, expected, actual_value, check_result)
VALUES
(
    N'第四周统计视图数量', N'4', CONVERT(NVARCHAR(100), @view_count),
    CASE WHEN @view_count = 4 THEN N'PASS' ELSE N'FAIL' END
);

DECLARE @role_count INT =
(
    SELECT COUNT(*)
    FROM sys.database_principals
    WHERE type = 'R'
      AND name IN
      (N'store_manager_role', N'cashier_role', N'inventory_clerk_role')
);

INSERT INTO @acceptance (check_item, expected, actual_value, check_result)
VALUES
(
    N'业务数据库角色数量', N'3', CONVERT(NVARCHAR(100), @role_count),
    CASE WHEN @role_count = 3 THEN N'PASS' ELSE N'FAIL' END
);

DECLARE @product_count INT = (SELECT COUNT(*) FROM dbo.product);
DECLARE @order_count INT = (SELECT COUNT(*) FROM dbo.sales_order);
DECLARE @order_item_count INT = (SELECT COUNT(*) FROM dbo.sales_order_item);

INSERT INTO @acceptance (check_item, expected, actual_value, check_result)
VALUES
    (N'样例商品数量', N'3', CONVERT(NVARCHAR(100), @product_count),
     CASE WHEN @product_count = 3 THEN N'PASS' ELSE N'FAIL' END),
    (N'样例订单数量', N'3', CONVERT(NVARCHAR(100), @order_count),
     CASE WHEN @order_count = 3 THEN N'PASS' ELSE N'FAIL' END),
    (N'样例订单明细数量', N'5', CONVERT(NVARCHAR(100), @order_item_count),
     CASE WHEN @order_item_count = 5 THEN N'PASS' ELSE N'FAIL' END);

DECLARE @low_inventory_count INT =
(
    SELECT COUNT(*)
    FROM dbo.vw_inventory_status
    WHERE inventory_status = N'需要补货'
);

INSERT INTO @acceptance (check_item, expected, actual_value, check_result)
VALUES
(
    N'低库存商品数量', N'1', CONVERT(NVARCHAR(100), @low_inventory_count),
    CASE WHEN @low_inventory_count = 1 THEN N'PASS' ELSE N'FAIL' END
);

DECLARE @bad_order_amount_count INT =
(
    SELECT COUNT(*)
    FROM dbo.sales_order
    WHERE
        (order_status = 'COMPLETED' AND paid_amount <> original_amount - discount_amount)
        OR (order_status IN ('PENDING', 'CANCELLED') AND paid_amount <> 0)
);

INSERT INTO @acceptance (check_item, expected, actual_value, check_result)
VALUES
(
    N'金额规则异常订单数量', N'0', CONVERT(NVARCHAR(100), @bad_order_amount_count),
    CASE WHEN @bad_order_amount_count = 0 THEN N'PASS' ELSE N'FAIL' END
);

DECLARE @orphan_order_item_count INT =
(
    SELECT COUNT(*)
    FROM dbo.sales_order_item AS oi
    LEFT JOIN dbo.sales_order AS o ON o.order_id = oi.order_id
    LEFT JOIN dbo.product AS p ON p.product_id = oi.product_id
    WHERE o.order_id IS NULL OR p.product_id IS NULL
);

INSERT INTO @acceptance (check_item, expected, actual_value, check_result)
VALUES
(
    N'孤立订单明细数量', N'0', CONVERT(NVARCHAR(100), @orphan_order_item_count),
    CASE WHEN @orphan_order_item_count = 0 THEN N'PASS' ELSE N'FAIL' END
);

SELECT check_no, check_item, expected, actual_value, check_result
FROM @acceptance
ORDER BY check_no;

SELECT
    CASE
        WHEN EXISTS (SELECT 1 FROM @acceptance WHERE check_result = N'FAIL')
            THEN N'v0.1 验收未通过，请检查 FAIL 项'
        ELSE N'v0.1 验收通过'
    END AS final_result;
GO
