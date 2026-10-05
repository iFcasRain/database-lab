/*
  第四周 view.sql
  内容：创建并查询订单详情、商品销售、库存状态和会员消费视图。
  执行前提：已完成第三周 00 至 04 脚本。
*/

USE ConvenienceStoreDB;
GO

CREATE OR ALTER VIEW dbo.vw_order_detail
AS
SELECT
    o.order_id,
    o.order_no,
    o.order_time,
    o.order_status,
    COALESCE(m.member_name, N'非会员') AS customer_name,
    e.employee_name AS cashier_name,
    p.product_code,
    p.product_name,
    oi.quantity,
    oi.unit_price,
    CAST(oi.quantity * oi.unit_price AS DECIMAL(10, 2)) AS line_amount,
    o.payment_method,
    o.paid_amount
FROM dbo.sales_order AS o
LEFT JOIN dbo.member AS m ON m.member_id = o.member_id
JOIN dbo.employee AS e ON e.employee_id = o.cashier_id
JOIN dbo.sales_order_item AS oi ON oi.order_id = o.order_id
JOIN dbo.product AS p ON p.product_id = oi.product_id;
GO

CREATE OR ALTER VIEW dbo.vw_product_sales_summary
AS
SELECT
    p.product_id,
    p.product_code,
    p.product_name,
    CAST
    (
        COALESCE
        (
            SUM(CASE WHEN o.order_id IS NOT NULL THEN oi.quantity ELSE 0 END),
            0
        ) AS INT
    ) AS total_quantity_sold,
    CAST
    (
        COALESCE
        (
            SUM
            (
                CASE
                    WHEN o.order_id IS NOT NULL THEN oi.quantity * oi.unit_price
                    ELSE 0
                END
            ),
            0
        ) AS DECIMAL(10, 2)
    ) AS total_sales_amount,
    COUNT(DISTINCT o.order_id) AS completed_order_count
FROM dbo.product AS p
LEFT JOIN dbo.sales_order_item AS oi ON oi.product_id = p.product_id
LEFT JOIN dbo.sales_order AS o
    ON o.order_id = oi.order_id
   AND o.order_status = 'COMPLETED'
GROUP BY p.product_id, p.product_code, p.product_name;
GO

CREATE OR ALTER VIEW dbo.vw_inventory_status
AS
SELECT
    p.product_id,
    p.product_code,
    p.product_name,
    c.category_name,
    i.quantity,
    i.reorder_level,
    CASE
        WHEN i.quantity <= i.reorder_level THEN N'需要补货'
        ELSE N'库存正常'
    END AS inventory_status,
    CASE
        WHEN i.quantity <= i.reorder_level
            THEN i.reorder_level * 2 - i.quantity
        ELSE 0
    END AS suggested_reorder_quantity,
    i.updated_at
FROM dbo.product AS p
JOIN dbo.category AS c ON c.category_id = p.category_id
JOIN dbo.inventory AS i ON i.product_id = p.product_id;
GO

CREATE OR ALTER VIEW dbo.vw_member_consumption_summary
AS
SELECT
    m.member_id,
    m.member_no,
    m.member_name,
    COUNT(o.order_id) AS completed_order_count,
    CAST(COALESCE(SUM(o.paid_amount), 0) AS DECIMAL(10, 2)) AS total_paid_amount,
    m.points_balance,
    m.status AS member_status
FROM dbo.member AS m
LEFT JOIN dbo.sales_order AS o
    ON o.member_id = m.member_id
   AND o.order_status = 'COMPLETED'
GROUP BY
    m.member_id,
    m.member_no,
    m.member_name,
    m.points_balance,
    m.status;
GO

/* 验证四个视图。 */
SELECT *
FROM dbo.vw_order_detail
ORDER BY order_time, order_id, product_code;

SELECT *
FROM dbo.vw_product_sales_summary
ORDER BY total_sales_amount DESC, product_code;

SELECT *
FROM dbo.vw_inventory_status
ORDER BY inventory_status DESC, product_code;

SELECT *
FROM dbo.vw_member_consumption_summary
ORDER BY total_paid_amount DESC, member_no;
GO

/* 验证视图已经创建。 */
SELECT
    s.name AS schema_name,
    v.name AS view_name
FROM sys.views AS v
JOIN sys.schemas AS s ON s.schema_id = v.schema_id
WHERE s.name = N'dbo'
  AND v.name IN
      (
          N'vw_order_detail',
          N'vw_product_sales_summary',
          N'vw_inventory_status',
          N'vw_member_consumption_summary'
      )
ORDER BY v.name;
GO
