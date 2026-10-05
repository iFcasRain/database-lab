/*
  第三周 03：插入样例数据
  执行前提：已依次运行 00、01、02 脚本。
  样例数据与 docs/样例元组.md 保持一致。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF EXISTS (SELECT 1 FROM dbo.category)
   OR EXISTS (SELECT 1 FROM dbo.product)
   OR EXISTS (SELECT 1 FROM dbo.member)
   OR EXISTS (SELECT 1 FROM dbo.employee)
BEGIN
    THROW 50002, N'检测到样例表中已有数据。为避免重复插入，本脚本已停止。', 1;
END;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO dbo.category
        (category_code, category_name, status, created_at)
    VALUES
        ('BEVERAGE', N'饮料', 'ACTIVE', '2026-09-01T08:00:00'),
        ('SNACK', N'零食', 'ACTIVE', '2026-09-01T08:00:00'),
        ('DAILY', N'日用品', 'ACTIVE', '2026-09-01T08:00:00');

    INSERT INTO dbo.product
        (product_code, barcode, product_name, category_id, unit,
         selling_price, status, created_at)
    VALUES
        ('P001', '6900000000011', N'饮用天然水 550ml', 1, N'瓶', 2.00, 'ACTIVE', '2026-09-01T08:10:00'),
        ('P002', '6900000000028', N'纯牛奶 250ml', 1, N'盒', 3.50, 'ACTIVE', '2026-09-01T08:11:00'),
        ('P003', '6900000000035', N'原味薯片 70g', 2, N'袋', 5.50, 'ACTIVE', '2026-09-01T08:12:00');

    INSERT INTO dbo.inventory
        (product_id, quantity, reorder_level, updated_at)
    VALUES
        (101, 24, 10, '2026-09-23T10:20:00'),
        (102, 8, 10, '2026-09-23T10:20:00'),
        (103, 15, 8, '2026-09-23T10:20:00');

    INSERT INTO dbo.member
        (member_no, member_name, phone, points_balance,
         registered_at, status, remark)
    VALUES
        ('M001', N'张晓雨', '13800000001', 120, '2026-09-05T09:30:00', 'ACTIVE', N'常规会员'),
        ('M002', N'李明', '13800000002', 65, '2026-09-08T14:20:00', 'ACTIVE', N'常规会员'),
        ('M003', N'王芳', '13800000003', 0, '2026-09-10T16:00:00', 'INACTIVE', N'已停用测试会员');

    INSERT INTO dbo.employee
        (employee_no, employee_name, phone, job_type,
         hire_date, status, created_at)
    VALUES
        ('E001', N'陈店长', '13900000001', 'MANAGER', '2025-03-01', 'ACTIVE', '2026-09-01T08:00:00'),
        ('E002', N'刘收银', '13900000002', 'CASHIER', '2026-02-15', 'ACTIVE', '2026-09-01T08:00:00'),
        ('E003', N'赵理货', '13900000003', 'INVENTORY', '2026-04-10', 'ACTIVE', '2026-09-01T08:00:00');

    INSERT INTO dbo.supplier
        (supplier_code, supplier_name, contact_name, phone,
         address, status, created_at)
    VALUES
        ('S001', N'华东饮品配送有限公司', N'周师傅', '13700000001', N'城北物流园 A 区', 'ACTIVE', '2026-09-01T09:00:00'),
        ('S002', N'城市乳业供应中心', N'孙经理', '13700000002', N'城西食品产业园', 'ACTIVE', '2026-09-01T09:05:00'),
        ('S003', N'乐购食品批发部', N'吴女士', '13700000003', N'中心批发市场 18 号', 'ACTIVE', '2026-09-01T09:10:00');

    INSERT INTO dbo.sales_order
        (order_no, member_id, cashier_id, order_time, order_status,
         payment_method, original_amount, discount_amount, paid_amount)
    VALUES
        ('SO202609230001', 201, 302, '2026-09-23T09:10:00', 'COMPLETED', 'MOBILE', 7.50, 0.50, 7.00),
        ('SO202609230002', 202, 302, '2026-09-23T09:35:00', 'COMPLETED', 'CASH', 11.00, 0.00, 11.00),
        ('SO202609230003', NULL, 302, '2026-09-23T10:05:00', 'COMPLETED', 'CARD', 9.00, 0.00, 9.00);

    INSERT INTO dbo.sales_order_item
        (order_id, product_id, quantity, unit_price)
    VALUES
        (5001, 101, 2, 2.00),
        (5001, 102, 1, 3.50),
        (5002, 103, 2, 5.50),
        (5003, 101, 1, 2.00),
        (5003, 102, 2, 3.50);

    INSERT INTO dbo.points_transaction
        (transaction_no, member_id, order_id, change_type,
         points_change, balance_after, occurred_at, remark)
    VALUES
        ('PT202609230001', 201, 5001, 'REDEEM', -5, 113, '2026-09-23T09:10:00', N'订单积分抵扣'),
        ('PT202609230002', 201, 5001, 'EARN', 7, 120, '2026-09-23T09:10:01', N'完成订单获得积分'),
        ('PT202609230003', 202, 5002, 'EARN', 11, 65, '2026-09-23T09:35:01', N'完成订单获得积分');

    INSERT INTO dbo.purchase_order
        (purchase_order_no, supplier_id, created_by, approved_by,
         order_date, order_status, total_amount, approved_at)
    VALUES
        ('PO202609200001', 402, 303, 301, '2026-09-20', 'RECEIVED', 210.00, '2026-09-20T11:00:00'),
        ('PO202609230001', 401, 303, NULL, '2026-09-23', 'DRAFT', 100.00, NULL),
        ('PO202609220001', 403, 303, 301, '2026-09-22', 'CANCELLED', 126.00, '2026-09-22T15:00:00');

    INSERT INTO dbo.purchase_order_item
        (purchase_order_id, product_id, ordered_quantity,
         received_quantity, purchase_unit_price)
    VALUES
        (6001, 102, 60, 60, 3.00),
        (6001, 101, 30, 30, 1.00),
        (6002, 101, 100, 0, 1.00),
        (6003, 103, 30, 0, 4.20);

    INSERT INTO dbo.inventory_transaction
        (transaction_no, product_id, transaction_type, quantity_change,
         sales_order_id, purchase_order_id, operator_id, occurred_at, remark)
    VALUES
        ('IT202609200001', 102, 'PURCHASE_IN', 60, NULL, 6001, 303, '2026-09-20T16:00:00', N'牛奶采购入库'),
        ('IT202609200002', 101, 'PURCHASE_IN', 30, NULL, 6001, 303, '2026-09-20T16:01:00', N'饮用水采购入库'),
        ('IT202609230001', 101, 'SALE_OUT', -2, 5001, NULL, 302, '2026-09-23T09:10:02', N'订单销售出库'),
        ('IT202609230002', 102, 'SALE_OUT', -1, 5001, NULL, 302, '2026-09-23T09:10:02', N'订单销售出库'),
        ('IT202609230003', 103, 'SALE_OUT', -2, 5002, NULL, 302, '2026-09-23T09:35:02', N'订单销售出库'),
        ('IT202609230004', 101, 'SALE_OUT', -1, 5003, NULL, 302, '2026-09-23T10:05:02', N'订单销售出库'),
        ('IT202609230005', 102, 'SALE_OUT', -2, 5003, NULL, 302, '2026-09-23T10:05:02', N'订单销售出库');

    COMMIT TRANSACTION;
    PRINT N'样例数据插入成功。';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT N'category' AS table_name, COUNT(*) AS row_count FROM dbo.category
UNION ALL SELECT N'product', COUNT(*) FROM dbo.product
UNION ALL SELECT N'inventory', COUNT(*) FROM dbo.inventory
UNION ALL SELECT N'member', COUNT(*) FROM dbo.member
UNION ALL SELECT N'employee', COUNT(*) FROM dbo.employee
UNION ALL SELECT N'supplier', COUNT(*) FROM dbo.supplier
UNION ALL SELECT N'sales_order', COUNT(*) FROM dbo.sales_order
UNION ALL SELECT N'sales_order_item', COUNT(*) FROM dbo.sales_order_item
UNION ALL SELECT N'points_transaction', COUNT(*) FROM dbo.points_transaction
UNION ALL SELECT N'purchase_order', COUNT(*) FROM dbo.purchase_order
UNION ALL SELECT N'purchase_order_item', COUNT(*) FROM dbo.purchase_order_item
UNION ALL SELECT N'inventory_transaction', COUNT(*) FROM dbo.inventory_transaction
ORDER BY table_name;
GO

SELECT
    p.product_code,
    p.product_name,
    i.quantity,
    i.reorder_level,
    CASE WHEN i.quantity <= i.reorder_level THEN N'需要补货' ELSE N'库存正常' END AS inventory_status
FROM dbo.product AS p
JOIN dbo.inventory AS i ON i.product_id = p.product_id
ORDER BY p.product_id;
GO
