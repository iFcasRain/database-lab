/*
  第四周 role.sql
  内容：创建数据库角色、授予最小权限，并验证正常操作和越权失败。
  执行前提：已运行 view.sql，以便角色查询统计视图。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
/* 权限测试会故意触发拒绝错误，关闭 XACT_ABORT 便于在 CATCH 中安全清理。 */
SET XACT_ABORT OFF;
GO

/* 1. 创建数据库角色。 */
IF DATABASE_PRINCIPAL_ID(N'store_manager_role') IS NULL
    CREATE ROLE store_manager_role;

IF DATABASE_PRINCIPAL_ID(N'cashier_role') IS NULL
    CREATE ROLE cashier_role;

IF DATABASE_PRINCIPAL_ID(N'inventory_clerk_role') IS NULL
    CREATE ROLE inventory_clerk_role;
GO

/* 2. 创建无登录名的演示用户，只用于权限测试。 */
IF DATABASE_PRINCIPAL_ID(N'demo_manager') IS NULL
    CREATE USER demo_manager WITHOUT LOGIN;

IF DATABASE_PRINCIPAL_ID(N'demo_cashier') IS NULL
    CREATE USER demo_cashier WITHOUT LOGIN;

IF DATABASE_PRINCIPAL_ID(N'demo_inventory') IS NULL
    CREATE USER demo_inventory WITHOUT LOGIN;
GO

/* 3. 将演示用户加入对应角色。 */
IF IS_ROLEMEMBER(N'store_manager_role', N'demo_manager') <> 1
    ALTER ROLE store_manager_role ADD MEMBER demo_manager;

IF IS_ROLEMEMBER(N'cashier_role', N'demo_cashier') <> 1
    ALTER ROLE cashier_role ADD MEMBER demo_cashier;

IF IS_ROLEMEMBER(N'inventory_clerk_role', N'demo_inventory') <> 1
    ALTER ROLE inventory_clerk_role ADD MEMBER demo_inventory;
GO

/* 4. 店长：可查看全部经营数据，维护关键主数据和采购数据。 */
GRANT SELECT ON SCHEMA::dbo TO store_manager_role;
GRANT INSERT, UPDATE ON OBJECT::dbo.product TO store_manager_role;
GRANT INSERT, UPDATE ON OBJECT::dbo.employee TO store_manager_role;
GRANT INSERT, UPDATE ON OBJECT::dbo.supplier TO store_manager_role;
GRANT INSERT, UPDATE ON OBJECT::dbo.purchase_order TO store_manager_role;
GRANT INSERT, UPDATE ON OBJECT::dbo.purchase_order_item TO store_manager_role;
GO

/* 5. 收银员：只获得销售结算所需权限。 */
GRANT SELECT ON OBJECT::dbo.product TO cashier_role;
GRANT SELECT ON OBJECT::dbo.inventory TO cashier_role;
GRANT SELECT ON OBJECT::dbo.member TO cashier_role;
GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.sales_order TO cashier_role;
GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.sales_order_item TO cashier_role;
GRANT SELECT, INSERT ON OBJECT::dbo.points_transaction TO cashier_role;
GRANT INSERT ON OBJECT::dbo.inventory_transaction TO cashier_role;
GRANT UPDATE (points_balance) ON OBJECT::dbo.member TO cashier_role;
GRANT UPDATE (quantity, updated_at) ON OBJECT::dbo.inventory TO cashier_role;
DENY UPDATE ON OBJECT::dbo.product TO cashier_role;
DENY DELETE ON OBJECT::dbo.employee TO cashier_role;
GO

/* 6. 库存管理员：只获得库存、供应商和采购业务权限。 */
GRANT SELECT ON OBJECT::dbo.product TO inventory_clerk_role;
GRANT SELECT ON OBJECT::dbo.inventory TO inventory_clerk_role;
GRANT SELECT ON OBJECT::dbo.supplier TO inventory_clerk_role;
GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.purchase_order TO inventory_clerk_role;
GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.purchase_order_item TO inventory_clerk_role;
GRANT SELECT, INSERT ON OBJECT::dbo.inventory_transaction TO inventory_clerk_role;
GRANT SELECT ON OBJECT::dbo.vw_inventory_status TO inventory_clerk_role;
GRANT UPDATE (quantity, updated_at) ON OBJECT::dbo.inventory TO inventory_clerk_role;
DENY SELECT ON OBJECT::dbo.member TO inventory_clerk_role;
DENY SELECT ON OBJECT::dbo.sales_order TO inventory_clerk_role;
GO

DECLARE @permission_results TABLE
(
    test_no       INT IDENTITY(1, 1) PRIMARY KEY,
    test_case     NVARCHAR(120) NOT NULL,
    expected      NVARCHAR(100) NOT NULL,
    actual_result NVARCHAR(20) NOT NULL,
    detail        NVARCHAR(4000) NULL
);

/* 用例 1：店长查看销售统计视图，应成功。 */
BEGIN TRY
    EXECUTE AS USER = N'demo_manager';
    SELECT product_code, product_name, total_quantity_sold, total_sales_amount
    FROM dbo.vw_product_sales_summary;
    REVERT;

    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'店长查看销售统计视图', N'允许', N'PASS', N'店长具有经营数据查询权限');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'demo_manager' REVERT;
    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'店长查看销售统计视图', N'允许', N'FAIL', ERROR_MESSAGE());
END CATCH;

/* 用例 2：收银员查看商品与价格，应成功。 */
BEGIN TRY
    EXECUTE AS USER = N'demo_cashier';
    SELECT product_code, product_name, selling_price
    FROM dbo.product;
    REVERT;

    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'收银员查看商品信息', N'允许', N'PASS', N'收银员能够完成结算前的商品查询');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'demo_cashier' REVERT;
    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'收银员查看商品信息', N'允许', N'FAIL', ERROR_MESSAGE());
END CATCH;

/* 用例 3：库存管理员查看库存状态视图，应成功。 */
BEGIN TRY
    EXECUTE AS USER = N'demo_inventory';
    SELECT product_code, product_name, quantity, reorder_level, inventory_status
    FROM dbo.vw_inventory_status;
    REVERT;

    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'库存管理员查看库存状态', N'允许', N'PASS', N'库存管理员具有库存查询权限');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'demo_inventory' REVERT;
    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'库存管理员查看库存状态', N'允许', N'FAIL', ERROR_MESSAGE());
END CATCH;

/* 用例 4：收银员修改商品售价，应失败。 */
BEGIN TRY
    BEGIN TRANSACTION;
    EXECUTE AS USER = N'demo_cashier';
    UPDATE dbo.product
    SET selling_price = selling_price + 1
    WHERE product_id = 101;
    REVERT;
    ROLLBACK TRANSACTION;

    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'收银员修改商品售价', N'拒绝', N'FAIL', N'越权操作意外成功');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    IF USER_NAME() = N'demo_cashier' REVERT;
    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'收银员修改商品售价', N'拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 5：库存管理员查看会员资料，应失败。 */
BEGIN TRY
    EXECUTE AS USER = N'demo_inventory';
    SELECT member_no, member_name, phone
    FROM dbo.member;
    REVERT;

    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'库存管理员查看会员资料', N'拒绝', N'FAIL', N'越权操作意外成功');
END TRY
BEGIN CATCH
    IF USER_NAME() = N'demo_inventory' REVERT;
    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'库存管理员查看会员资料', N'拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

/* 用例 6：收银员删除员工，应失败。 */
BEGIN TRY
    BEGIN TRANSACTION;
    EXECUTE AS USER = N'demo_cashier';
    DELETE FROM dbo.employee
    WHERE employee_id = 303;
    REVERT;
    ROLLBACK TRANSACTION;

    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'收银员删除员工', N'拒绝', N'FAIL', N'越权操作意外成功');
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    IF USER_NAME() = N'demo_cashier' REVERT;
    INSERT INTO @permission_results (test_case, expected, actual_result, detail)
    VALUES (N'收银员删除员工', N'拒绝', N'PASS', ERROR_MESSAGE());
END CATCH;

SELECT test_no, test_case, expected, actual_result, detail
FROM @permission_results
ORDER BY test_no;

/* 输出角色成员关系，作为权限配置证据。 */
SELECT
    role_principal.name AS role_name,
    member_principal.name AS member_name
FROM sys.database_role_members AS drm
JOIN sys.database_principals AS role_principal
    ON role_principal.principal_id = drm.role_principal_id
JOIN sys.database_principals AS member_principal
    ON member_principal.principal_id = drm.member_principal_id
WHERE role_principal.name IN
      (N'store_manager_role', N'cashier_role', N'inventory_clerk_role')
ORDER BY role_name, member_name;
GO
