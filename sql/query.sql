/*
  第四周 query.sql
  内容：多表连接、聚合、GROUP BY、HAVING 和子查询。
  执行前提：已完成第三周 00 至 04 脚本。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
GO

/* 查询 1：订单详情。LEFT JOIN 保留非会员订单。 */
SELECT
    o.order_no,
    o.order_time,
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
JOIN dbo.product AS p ON p.product_id = oi.product_id
WHERE o.order_status = 'COMPLETED'
ORDER BY o.order_time, o.order_id, oi.order_item_id;
GO

/* 查询 2：每种商品的销量与销售额。 */
SELECT
    p.product_code,
    p.product_name,
    SUM(oi.quantity) AS total_quantity_sold,
    CAST(SUM(oi.quantity * oi.unit_price) AS DECIMAL(10, 2)) AS total_sales_amount,
    COUNT(DISTINCT oi.order_id) AS order_count
FROM dbo.product AS p
JOIN dbo.sales_order_item AS oi ON oi.product_id = p.product_id
JOIN dbo.sales_order AS o ON o.order_id = oi.order_id
WHERE o.order_status = 'COMPLETED'
GROUP BY p.product_id, p.product_code, p.product_name
ORDER BY total_sales_amount DESC, p.product_code;
GO

/* 查询 3：使用 HAVING 筛选累计销量不少于 3 件的商品。 */
SELECT
    p.product_code,
    p.product_name,
    SUM(oi.quantity) AS total_quantity_sold
FROM dbo.product AS p
JOIN dbo.sales_order_item AS oi ON oi.product_id = p.product_id
JOIN dbo.sales_order AS o ON o.order_id = oi.order_id
WHERE o.order_status = 'COMPLETED'
GROUP BY p.product_id, p.product_code, p.product_name
HAVING SUM(oi.quantity) >= 3
ORDER BY total_quantity_sold DESC, p.product_code;
GO

/* 查询 4：会员消费汇总，保留当前没有完成订单的会员。 */
SELECT
    m.member_no,
    m.member_name,
    COUNT(o.order_id) AS completed_order_count,
    CAST(COALESCE(SUM(o.paid_amount), 0) AS DECIMAL(10, 2)) AS total_paid_amount,
    m.points_balance
FROM dbo.member AS m
LEFT JOIN dbo.sales_order AS o
    ON o.member_id = m.member_id
   AND o.order_status = 'COMPLETED'
GROUP BY m.member_id, m.member_no, m.member_name, m.points_balance
ORDER BY total_paid_amount DESC, m.member_no;
GO

/* 查询 5：子查询找出实付金额高于平均值的已完成订单。 */
SELECT
    o.order_no,
    COALESCE(m.member_name, N'非会员') AS customer_name,
    o.paid_amount,
    CAST
    (
        (
            SELECT AVG(CAST(o2.paid_amount AS DECIMAL(10, 2)))
            FROM dbo.sales_order AS o2
            WHERE o2.order_status = 'COMPLETED'
        )
        AS DECIMAL(10, 2)
    ) AS average_paid_amount
FROM dbo.sales_order AS o
LEFT JOIN dbo.member AS m ON m.member_id = o.member_id
WHERE o.order_status = 'COMPLETED'
  AND o.paid_amount >
      (
          SELECT AVG(CAST(o2.paid_amount AS DECIMAL(10, 2)))
          FROM dbo.sales_order AS o2
          WHERE o2.order_status = 'COMPLETED'
      )
ORDER BY o.paid_amount DESC;
GO

/* 查询 6：库存状态与补货建议。 */
SELECT
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
    END AS suggested_reorder_quantity
FROM dbo.product AS p
JOIN dbo.category AS c ON c.category_id = p.category_id
JOIN dbo.inventory AS i ON i.product_id = p.product_id
ORDER BY inventory_status DESC, p.product_code;
GO

/* 查询 7：采购单及其明细，用于核对供应商、创建人和审批人。 */
SELECT
    po.purchase_order_no,
    s.supplier_name,
    creator.employee_name AS created_by_name,
    COALESCE(approver.employee_name, N'尚未审批') AS approved_by_name,
    po.order_status,
    p.product_name,
    poi.ordered_quantity,
    poi.received_quantity,
    poi.purchase_unit_price,
    CAST(poi.ordered_quantity * poi.purchase_unit_price AS DECIMAL(10, 2)) AS line_amount
FROM dbo.purchase_order AS po
JOIN dbo.supplier AS s ON s.supplier_id = po.supplier_id
JOIN dbo.employee AS creator ON creator.employee_id = po.created_by
LEFT JOIN dbo.employee AS approver ON approver.employee_id = po.approved_by
JOIN dbo.purchase_order_item AS poi ON poi.purchase_order_id = po.purchase_order_id
JOIN dbo.product AS p ON p.product_id = poi.product_id
ORDER BY po.purchase_order_id, poi.purchase_order_item_id;
GO

/* 查询 8：使用 NOT EXISTS 检查从未出现在已完成订单中的商品。 */
SELECT
    p.product_code,
    p.product_name,
    p.status
FROM dbo.product AS p
WHERE NOT EXISTS
(
    SELECT 1
    FROM dbo.sales_order_item AS oi
    JOIN dbo.sales_order AS o ON o.order_id = oi.order_id
    WHERE oi.product_id = p.product_id
      AND o.order_status = 'COMPLETED'
)
ORDER BY p.product_code;
GO
