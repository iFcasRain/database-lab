/*
  第三周 04：商品、库存和订单 CRUD 演示
  每组操作都会展示执行前后结果，并在结束时恢复或清理测试数据。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* A. 商品和库存：新增、查询、修改、删除 */
PRINT N'A1 新增测试商品及其库存';
BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO dbo.product
        (product_code, barcode, product_name, category_id, unit, selling_price, status)
    VALUES
        ('P900', '6900000000905', N'CRUD 测试饼干 100g', 2, N'袋', 6.00, 'ACTIVE');

    DECLARE @test_product_id INT = CONVERT(INT, SCOPE_IDENTITY());

    INSERT INTO dbo.inventory (product_id, quantity, reorder_level)
    VALUES (@test_product_id, 20, 5);

    SELECT p.product_id, p.product_code, p.product_name, p.selling_price,
           i.quantity, i.reorder_level
    FROM dbo.product AS p
    JOIN dbo.inventory AS i ON i.product_id = p.product_id
    WHERE p.product_code = 'P900';

    PRINT N'A2 修改测试商品价格和库存';
    UPDATE dbo.product
    SET selling_price = 6.50
    WHERE product_code = 'P900';

    UPDATE dbo.inventory
    SET quantity = quantity + 10,
        updated_at = SYSDATETIME()
    WHERE product_id = @test_product_id;

    SELECT p.product_code, p.product_name, p.selling_price, i.quantity
    FROM dbo.product AS p
    JOIN dbo.inventory AS i ON i.product_id = p.product_id
    WHERE p.product_code = 'P900';

    PRINT N'A3 先删除从表库存，再删除主表商品';
    DELETE FROM dbo.inventory WHERE product_id = @test_product_id;
    DELETE FROM dbo.product WHERE product_id = @test_product_id;

    SELECT COUNT(*) AS remaining_test_products
    FROM dbo.product
    WHERE product_code = 'P900';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

/* B. 已有库存：查询、修改和恢复 */
PRINT N'B1 查询商品 P002 的修改前库存';
SELECT p.product_code, p.product_name, i.quantity, i.updated_at
FROM dbo.product AS p
JOIN dbo.inventory AS i ON i.product_id = p.product_id
WHERE p.product_code = 'P002';
GO

BEGIN TRANSACTION;

UPDATE i
SET i.quantity = i.quantity + 12,
    i.updated_at = SYSDATETIME()
FROM dbo.inventory AS i
JOIN dbo.product AS p ON p.product_id = i.product_id
WHERE p.product_code = 'P002';

PRINT N'B2 查看库存修改结果';
SELECT p.product_code, p.product_name, i.quantity, i.updated_at
FROM dbo.product AS p
JOIN dbo.inventory AS i ON i.product_id = p.product_id
WHERE p.product_code = 'P002';

ROLLBACK TRANSACTION;

PRINT N'B3 回滚后再次查询，库存应恢复为 8';
SELECT p.product_code, p.product_name, i.quantity, i.updated_at
FROM dbo.product AS p
JOIN dbo.inventory AS i ON i.product_id = p.product_id
WHERE p.product_code = 'P002';
GO

/* C. 待支付订单：新增、查询、修改、删除 */
PRINT N'C1 新增一张测试待支付订单及明细';
BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO dbo.sales_order
        (order_no, member_id, cashier_id, order_status, payment_method,
         original_amount, discount_amount, paid_amount)
    VALUES
        ('SO-CRUD-TEST-001', 201, 302, 'PENDING', NULL, 2.00, 0.00, 0.00);

    DECLARE @test_order_id BIGINT = CONVERT(BIGINT, SCOPE_IDENTITY());

    INSERT INTO dbo.sales_order_item
        (order_id, product_id, quantity, unit_price)
    VALUES
        (@test_order_id, 101, 1, 2.00);

    SELECT o.order_id, o.order_no, o.order_status,
           p.product_name, oi.quantity, oi.unit_price
    FROM dbo.sales_order AS o
    JOIN dbo.sales_order_item AS oi ON oi.order_id = o.order_id
    JOIN dbo.product AS p ON p.product_id = oi.product_id
    WHERE o.order_no = 'SO-CRUD-TEST-001';

    PRINT N'C2 顾客放弃支付，将订单修改为已取消';
    UPDATE dbo.sales_order
    SET order_status = 'CANCELLED'
    WHERE order_id = @test_order_id;

    SELECT order_no, order_status, payment_method
    FROM dbo.sales_order
    WHERE order_id = @test_order_id;

    PRINT N'C3 删除测试订单时先删除订单明细';
    DELETE FROM dbo.sales_order_item WHERE order_id = @test_order_id;
    DELETE FROM dbo.sales_order WHERE order_id = @test_order_id;

    SELECT COUNT(*) AS remaining_test_orders
    FROM dbo.sales_order
    WHERE order_no = 'SO-CRUD-TEST-001';

    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

/* D. 最终查询：确认正式样例数据未被 CRUD 演示破坏 */
SELECT product_id, product_code, product_name, selling_price, status
FROM dbo.product
ORDER BY product_id;

SELECT product_id, quantity, reorder_level, updated_at
FROM dbo.inventory
ORDER BY product_id;

SELECT order_id, order_no, member_id, cashier_id,
       order_status, payment_method, paid_amount
FROM dbo.sales_order
ORDER BY order_id;
GO
