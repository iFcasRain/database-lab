/*
  第四周 constraint.sql
  内容：补充格式约束，并验证合法数据成功、非法数据失败。
  执行前提：已完成第三周 00 至 04 脚本。
  所有测试均在事务中执行，不会污染正式样例数据。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* 补充商品编码格式约束：P 加 3 位数字。 */
IF NOT EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.product')
      AND name = N'CK_product_code_format'
)
BEGIN
    ALTER TABLE dbo.product WITH CHECK ADD
        CONSTRAINT CK_product_code_format
        CHECK
        (
            LEN(product_code) = 4
            AND product_code LIKE 'P[0-9][0-9][0-9]'
        );
END;
GO

/* 补充手机号格式约束：11 位数字。 */
IF NOT EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.member')
      AND name = N'CK_member_phone_format'
)
BEGIN
    ALTER TABLE dbo.member WITH CHECK ADD
        CONSTRAINT CK_member_phone_format
        CHECK (LEN(phone) = 11 AND phone NOT LIKE '%[^0-9]%');
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.employee')
      AND name = N'CK_employee_phone_format'
)
BEGIN
    ALTER TABLE dbo.employee WITH CHECK ADD
        CONSTRAINT CK_employee_phone_format
        CHECK (LEN(phone) = 11 AND phone NOT LIKE '%[^0-9]%');
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.supplier')
      AND name = N'CK_supplier_phone_format'
)
BEGIN
    ALTER TABLE dbo.supplier WITH CHECK ADD
        CONSTRAINT CK_supplier_phone_format
        CHECK (LEN(phone) = 11 AND phone NOT LIKE '%[^0-9]%');
END;
GO

DECLARE @test_results TABLE
(
    test_no       INT IDENTITY(1, 1) PRIMARY KEY,
    test_case     NVARCHAR(100) NOT NULL,
    expected      NVARCHAR(100) NOT NULL,
    actual_result NVARCHAR(20) NOT NULL,
    detail        NVARCHAR(4000) NULL
);

/* 用例 1：合法商品和库存应成功。 */
BEGIN TRY
    BEGIN TRANSACTION;

    INSERT INTO dbo.product
        (product_code, barcode, product_name, category_id, unit, selling_price, status)
    VALUES
        ('P998', '6999999999998', N'约束测试合法商品', 1, N'件', 9.90, 'ACTIVE');

    DECLARE @valid_product_id INT = CONVERT(INT, SCOPE_IDENTITY());

    INSERT INTO dbo.inventory (product_id, quantity, reorder_level)
    VALUES (@valid_product_id, 5, 2);

    ROLLBACK TRANSACTION;

    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'合法商品与库存', N'允许写入', N'PASS', N'合法数据成功通过全部约束，随后回滚测试数据');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'合法商品与库存', N'允许写入', N'FAIL', ERROR_MESSAGE());
END CATCH;

/* 用例 2：负数商品价格应被 CHECK 拒绝。 */
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.product
        (product_code, barcode, product_name, category_id, unit, selling_price, status)
    VALUES
        ('P997', '6999999999997', N'负价格测试商品', 1, N'件', -1.00, 'ACTIVE');
    ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'负数商品价格', N'被 CHECK 拒绝', N'FAIL', N'非法数据意外写入');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'负数商品价格', N'被 CHECK 拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 3：不存在的分类应被外码拒绝。 */
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.product
        (product_code, barcode, product_name, category_id, unit, selling_price, status)
    VALUES
        ('P996', '6999999999996', N'外码测试商品', 999999, N'件', 1.00, 'ACTIVE');
    ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'不存在的商品分类', N'被外码拒绝', N'FAIL', N'非法数据意外写入');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'不存在的商品分类', N'被外码拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 4：重复条码应被 UNIQUE 拒绝。 */
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.product
        (product_code, barcode, product_name, category_id, unit, selling_price, status)
    VALUES
        ('P995', '6900000000011', N'重复条码测试商品', 1, N'件', 1.00, 'ACTIVE');
    ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'重复商品条码', N'被 UNIQUE 拒绝', N'FAIL', N'非法数据意外写入');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'重复商品条码', N'被 UNIQUE 拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 5：负库存应被 CHECK 拒绝。 */
BEGIN TRY
    BEGIN TRANSACTION;
    UPDATE dbo.inventory
    SET quantity = -1
    WHERE product_id = 101;
    ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'负数库存', N'被 CHECK 拒绝', N'FAIL', N'非法数据意外写入');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'负数库存', N'被 CHECK 拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 6：已完成订单缺少支付方式应被 CHECK 拒绝。 */
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.sales_order
        (order_no, member_id, cashier_id, order_status, payment_method,
         original_amount, discount_amount, paid_amount)
    VALUES
        ('SO-CONSTRAINT-001', 201, 302, 'COMPLETED', NULL, 2.00, 0.00, 2.00);
    ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'完成订单缺少支付方式', N'被 CHECK 拒绝', N'FAIL', N'非法数据意外写入');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'完成订单缺少支付方式', N'被 CHECK 拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 7：订单明细数量为 0 应被 CHECK 拒绝。 */
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.sales_order_item
        (order_id, product_id, quantity, unit_price)
    VALUES
        (5001, 103, 0, 5.50);
    ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'订单明细数量为零', N'被 CHECK 拒绝', N'FAIL', N'非法数据意外写入');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'订单明细数量为零', N'被 CHECK 拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 8：格式不正确的手机号应被新增约束拒绝。 */
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO dbo.member
        (member_no, member_name, phone, points_balance, status)
    VALUES
        ('M998', N'手机号约束测试', 'ABC123', 0, 'ACTIVE');
    ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'格式错误的会员手机号', N'被 CHECK 拒绝', N'FAIL', N'非法数据意外写入');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    INSERT INTO @test_results (test_case, expected, actual_result, detail)
    VALUES (N'格式错误的会员手机号', N'被 CHECK 拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

SELECT test_no, test_case, expected, actual_result, detail
FROM @test_results
ORDER BY test_no;

SELECT
    OBJECT_NAME(parent_object_id) AS table_name,
    name AS added_constraint,
    definition
FROM sys.check_constraints
WHERE name IN
(
    N'CK_product_code_format',
    N'CK_member_phone_format',
    N'CK_employee_phone_format',
    N'CK_supplier_phone_format'
)
ORDER BY table_name, added_constraint;
GO
