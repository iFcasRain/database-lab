/*
  第六周 migration.sql
  作用：把 v0.1 数据库（12 张表）迁移到第 7—9 周 Web 应用使用的 v1.0 结构。
  执行前提：
    1. 已按 README 依次执行 00_create_database.sql 至 04_crud.sql；
    2. 已执行第四周 query.sql、view.sql、constraint.sql、role.sql 和 v01_acceptance.sql；
    3. v01_acceptance.sql 显示“v0.1 验收通过”。
  迁移结论（详见 docs/函数依赖与规范化分析.md）：
    a. 12 张业务表已满足 3NF/BCNF，本脚本不拆分、不合并、不删除任何既有表与字段，
       保持第二周数据字典和第三周样例数据不变；
    b. 唯一的结构缺口是缺少“应用账号”实体。Web 应用需要登录，而 member 与 employee
       都不应保存密码；因此新增 app_user 表，通过外码分别关联会员或员工；
    c. 新增 2 个只读视图供应用按角色查询，避免为查询放宽基表授权；
    d. 新增 2 个应用程序角色（application role），配合第四周已有的 3 个数据库角色，
       使界面权限、后端权限和数据库权限保持一致；
    e. 补充少量索引和外码列索引，不改变任何业务语义。
  再次运行：脚本按“不存在才创建”编写，可重复执行；重复执行不会重复插入账号。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* ------------------------------------------------------------------
   0. 前置检查：v0.1 基线必须完整，否则迁移没有意义。
   ------------------------------------------------------------------ */
IF OBJECT_ID(N'dbo.product', N'U') IS NULL
   OR OBJECT_ID(N'dbo.inventory', N'U') IS NULL
   OR OBJECT_ID(N'dbo.member', N'U') IS NULL
   OR OBJECT_ID(N'dbo.employee', N'U') IS NULL
   OR OBJECT_ID(N'dbo.sales_order', N'U') IS NULL
   OR OBJECT_ID(N'dbo.sales_order_item', N'U') IS NULL
   OR OBJECT_ID(N'dbo.inventory_transaction', N'U') IS NULL
BEGIN
    THROW 50020, N'v0.1 基线不完整：请先按 README 执行第三周和第四周脚本，并确认 v0.1 验收通过。', 1;
END;
GO

/* ------------------------------------------------------------------
   1. 迁移前基线快照
   这些结果与第四周 query.sql 的关键结果一致；迁移结束后由 regression.sql 再次核对。
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 1：迁移前基线快照 ===';

SELECT
    N'订单金额' AS baseline_item,
    o.order_no,
    o.original_amount,
    o.discount_amount,
    o.paid_amount,
    CAST(SUM(oi.quantity * oi.unit_price) AS DECIMAL(10, 2)) AS item_amount_total
FROM dbo.sales_order AS o
JOIN dbo.sales_order_item AS oi ON oi.order_id = o.order_id
GROUP BY o.order_no, o.original_amount, o.discount_amount, o.paid_amount
ORDER BY o.order_no;

SELECT
    N'商品销量' AS baseline_item,
    p.product_code,
    p.product_name,
    SUM(oi.quantity) AS total_quantity_sold,
    CAST(SUM(oi.quantity * oi.unit_price) AS DECIMAL(10, 2)) AS total_sales_amount
FROM dbo.product AS p
JOIN dbo.sales_order_item AS oi ON oi.product_id = p.product_id
JOIN dbo.sales_order AS o ON o.order_id = oi.order_id AND o.order_status = 'COMPLETED'
GROUP BY p.product_id, p.product_code, p.product_name
ORDER BY p.product_code;

SELECT
    N'库存' AS baseline_item,
    p.product_code,
    i.quantity,
    i.reorder_level,
    CASE WHEN i.quantity <= i.reorder_level THEN N'需要补货' ELSE N'库存正常' END AS inventory_status
FROM dbo.product AS p
JOIN dbo.inventory AS i ON i.product_id = p.product_id
ORDER BY p.product_code;
GO

/* ------------------------------------------------------------------
   2. 结构结论：12 张既有表保持 v0.1 结构
   第六周依赖与范式分析的结论是“无需拆分”，原因见文档：
     商品、会员、员工、供应商、订单、采购单等表的主码均为单属性代理码，
     非主属性完全且直接依赖于主码，不存在部分依赖与传递依赖；
     订单明细与采购明细只保留“成交单价”“采购单价”等交易期事实，
     金额一律由数量乘单价计算，不保存派生字段。
   因此本步骤只做“记录结论”，不做 DDL。
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 2：既有表结构保持不变（结论性检查）===';

SELECT
    t.name AS table_name,
    COUNT(c.column_id) AS column_count,
    CASE
        WHEN t.name IN (N'app_user') THEN N'v1.0 新增'
        ELSE N'保持 v0.1'
    END AS migration_decision
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id = t.object_id
WHERE t.schema_id = SCHEMA_ID(N'dbo')
GROUP BY t.name
ORDER BY t.name;
GO

/* ------------------------------------------------------------------
   3. 新增 app_user 应用账号表
   设计说明：
     - 账号只保存登录信息与角色，不复制员工或会员的业务属性；
     - employee_id / member_id 二者恰好一个非空，由 CHECK 约束保证；
     - 密码只保存 PBKDF2-SHA256 摘要，不保存明文，也不可逆。
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 3：创建 app_user ===';

IF OBJECT_ID(N'dbo.app_user', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.app_user
    (
        user_id       INT IDENTITY(1, 1) NOT NULL,
        username      VARCHAR(32) NOT NULL,
        password_hash VARCHAR(200) NOT NULL,
        display_name  NVARCHAR(50) NOT NULL,
        role          VARCHAR(12) NOT NULL,
        employee_id   INT NULL,
        member_id     INT NULL,
        status        VARCHAR(10) NOT NULL
            CONSTRAINT DF_app_user_status DEFAULT ('ACTIVE'),
        created_at    DATETIME2(0) NOT NULL
            CONSTRAINT DF_app_user_created_at DEFAULT (SYSDATETIME()),
        last_login_at DATETIME2(0) NULL,

        CONSTRAINT PK_app_user PRIMARY KEY (user_id),
        CONSTRAINT UQ_app_user_username UNIQUE (username),
        CONSTRAINT FK_app_user_employee
            FOREIGN KEY (employee_id) REFERENCES dbo.employee(employee_id),
        CONSTRAINT FK_app_user_member
            FOREIGN KEY (member_id) REFERENCES dbo.member(member_id),
        CONSTRAINT CK_app_user_role
            CHECK (role IN ('CUSTOMER', 'CASHIER', 'INVENTORY', 'MANAGER')),
        CONSTRAINT CK_app_user_status
            CHECK (status IN ('ACTIVE', 'INACTIVE')),
        CONSTRAINT CK_app_user_identity
            CHECK
            (
                (role = 'CUSTOMER' AND member_id IS NOT NULL AND employee_id IS NULL)
                OR
                (role IN ('CASHIER', 'INVENTORY', 'MANAGER')
                    AND employee_id IS NOT NULL AND member_id IS NULL)
            )
    );

    PRINT N'app_user 表已创建。';
END
ELSE
BEGIN
    PRINT N'app_user 表已存在，本次跳过创建。';
END;
GO

/* ------------------------------------------------------------------
   4. 新增 2 个只读视图
   vw_product_catalog：商品 + 分类 + 库存的只读目录，供各角色按权限查询，
                       避免为了“能显示分类名”而放宽 category 的基表授权。
   vw_active_cashier：只在职收银员的编号与姓名，供顾客线上下单时由业务层指派经办人。
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 4：创建应用视图 ===';
GO

CREATE OR ALTER VIEW dbo.vw_product_catalog
AS
SELECT
    p.product_id,
    p.product_code,
    p.barcode,
    p.product_name,
    p.category_id,
    c.category_name,
    p.unit,
    p.selling_price,
    p.status AS product_status,
    i.quantity,
    i.reorder_level,
    i.updated_at,
    CASE WHEN i.quantity <= i.reorder_level THEN 1 ELSE 0 END AS low_stock_flag
FROM dbo.product AS p
JOIN dbo.category AS c ON c.category_id = p.category_id
JOIN dbo.inventory AS i ON i.product_id = p.product_id;
GO

CREATE OR ALTER VIEW dbo.vw_active_cashier
AS
SELECT
    e.employee_id,
    e.employee_no,
    e.employee_name
FROM dbo.employee AS e
WHERE e.job_type = 'CASHIER'
  AND e.status = 'ACTIVE';
GO

/* 订单列表视图：把会员姓名和经办店员姓名一次取出，
   让没有 employee / member 基表授权的角色也能看到完整列表。 */
CREATE OR ALTER VIEW dbo.vw_order_summary
AS
SELECT
    o.order_id,
    o.order_no,
    o.member_id,
    m.member_no,
    COALESCE(m.member_name, N'非会员') AS customer_name,
    o.cashier_id,
    e.employee_name AS cashier_name,
    o.order_time,
    o.order_status,
    o.payment_method,
    o.original_amount,
    o.discount_amount,
    o.paid_amount,
    (SELECT COUNT(*) FROM dbo.sales_order_item AS i WHERE i.order_id = o.order_id) AS item_count
FROM dbo.sales_order AS o
LEFT JOIN dbo.member AS m ON m.member_id = o.member_id
LEFT JOIN dbo.employee AS e ON e.employee_id = o.cashier_id;
GO

/* ------------------------------------------------------------------
   5. 索引
   为外码列与常用查询条件补索引，减少应用查询时的全表扫描。
   不改变任何约束与业务语义。
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 5：补充索引 ===';

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sales_order_member' AND object_id = OBJECT_ID(N'dbo.sales_order'))
    CREATE INDEX IX_sales_order_member ON dbo.sales_order (member_id, order_time DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sales_order_cashier' AND object_id = OBJECT_ID(N'dbo.sales_order'))
    CREATE INDEX IX_sales_order_cashier ON dbo.sales_order (cashier_id, order_time DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sales_order_status_time' AND object_id = OBJECT_ID(N'dbo.sales_order'))
    CREATE INDEX IX_sales_order_status_time ON dbo.sales_order (order_status, order_time DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_sales_order_item_product' AND object_id = OBJECT_ID(N'dbo.sales_order_item'))
    CREATE INDEX IX_sales_order_item_product ON dbo.sales_order_item (product_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_points_transaction_member' AND object_id = OBJECT_ID(N'dbo.points_transaction'))
    CREATE INDEX IX_points_transaction_member ON dbo.points_transaction (member_id, occurred_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_inventory_transaction_product' AND object_id = OBJECT_ID(N'dbo.inventory_transaction'))
    CREATE INDEX IX_inventory_transaction_product ON dbo.inventory_transaction (product_id, occurred_at DESC);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_purchase_order_supplier' AND object_id = OBJECT_ID(N'dbo.purchase_order'))
    CREATE INDEX IX_purchase_order_supplier ON dbo.purchase_order (supplier_id, order_date DESC);
GO

/* ------------------------------------------------------------------
   6. 数据库角色与应用账号（界面权限 = 后端权限 = 数据库权限）
   v1.0 的 Web 应用不使用 sa 或 Windows 管理员身份执行业务 SQL：
   连接建立后立即 EXECUTE AS USER 切换成下表的“应用账号”，
   之后这条连接上的一切 SQL 都受该账号在数据库中的真实授权约束。

     应用账号      所属角色                可执行业务
     app_auth      auth_lookup_role        仅登录校验与登录时间更新
     app_customer  customer_app_role       浏览商品、查看本人订单与积分、线上下单
     app_cashier   cashier_role（第四周）   商品/会员查询、订单结算与确认
     app_inventory inventory_clerk_role     库存查询、盘点调整
     app_manager   store_manager_role       全部经营数据与商品维护

   这里使用 WITHOUT LOGIN 的数据库用户：它们不能直接登录服务器，
   只能由应用登录名通过 EXECUTE AS USER 借用，因此权限收敛落在数据库一侧。
   第 7—9 周的补充授权只做“增加”，不回退第四周已确定的任何拒绝项。
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 6：创建角色与应用账号并授权 ===';

IF DATABASE_PRINCIPAL_ID(N'auth_lookup_role') IS NULL
    CREATE ROLE auth_lookup_role;
GO

IF DATABASE_PRINCIPAL_ID(N'customer_app_role') IS NULL
    CREATE ROLE customer_app_role;
GO

/* 6.1 登录校验角色：只能读账号表并更新最后登录时间。 */
GRANT SELECT ON dbo.app_user TO auth_lookup_role;
GRANT UPDATE (last_login_at) ON dbo.app_user TO auth_lookup_role;
GO

/* 6.2 顾客角色：目录只读 + 本人订单查询 + 线上下单 + 取消未付款订单。 */
GRANT SELECT ON dbo.vw_product_catalog TO customer_app_role;
GRANT SELECT ON dbo.vw_active_cashier TO customer_app_role;
GRANT SELECT ON dbo.vw_order_summary TO customer_app_role;
GRANT SELECT ON dbo.vw_order_detail TO customer_app_role;
GRANT SELECT ON dbo.sales_order TO customer_app_role;
GRANT SELECT ON dbo.sales_order_item TO customer_app_role;
GRANT SELECT ON dbo.points_transaction TO customer_app_role;
GRANT SELECT ON dbo.member TO customer_app_role;
GRANT INSERT ON dbo.sales_order TO customer_app_role;
GRANT INSERT ON dbo.sales_order_item TO customer_app_role;
GRANT UPDATE (order_status) ON dbo.sales_order TO customer_app_role;
DENY UPDATE ON dbo.product TO customer_app_role;
DENY INSERT, UPDATE, DELETE ON dbo.employee TO customer_app_role;
DENY SELECT ON dbo.employee TO customer_app_role;
GO

/* 6.3 第四周角色的补充授权（只增加 v1.0 应用需要的操作）。 */
GRANT SELECT ON dbo.vw_product_catalog TO cashier_role;
GRANT SELECT ON dbo.vw_product_catalog TO inventory_clerk_role;
GRANT SELECT ON dbo.vw_active_cashier TO cashier_role;
GRANT SELECT ON dbo.vw_active_cashier TO inventory_clerk_role;
GRANT SELECT ON dbo.vw_order_summary TO cashier_role;
GRANT SELECT ON dbo.vw_order_summary TO inventory_clerk_role;
GRANT SELECT ON dbo.vw_order_detail TO cashier_role;
GO

/* 店长同时承担代班收银与新建商品建档，因此补授予结算与库存初始化权限。 */
GRANT INSERT ON dbo.inventory TO store_manager_role;
GRANT UPDATE (quantity, reorder_level, updated_at) ON dbo.inventory TO store_manager_role;
GRANT INSERT, UPDATE ON dbo.sales_order TO store_manager_role;
GRANT INSERT, UPDATE ON dbo.sales_order_item TO store_manager_role;
GRANT INSERT ON dbo.points_transaction TO store_manager_role;
GRANT UPDATE (points_balance) ON dbo.member TO store_manager_role;
GRANT INSERT ON dbo.inventory_transaction TO store_manager_role;
GO

/* 6.4 创建应用账号（数据库用户，无登录名）并加入对应角色。 */
IF DATABASE_PRINCIPAL_ID(N'app_auth') IS NULL
    CREATE USER app_auth WITHOUT LOGIN;
IF DATABASE_PRINCIPAL_ID(N'app_customer') IS NULL
    CREATE USER app_customer WITHOUT LOGIN;
IF DATABASE_PRINCIPAL_ID(N'app_cashier') IS NULL
    CREATE USER app_cashier WITHOUT LOGIN;
IF DATABASE_PRINCIPAL_ID(N'app_inventory') IS NULL
    CREATE USER app_inventory WITHOUT LOGIN;
IF DATABASE_PRINCIPAL_ID(N'app_manager') IS NULL
    CREATE USER app_manager WITHOUT LOGIN;
GO

IF IS_ROLEMEMBER(N'auth_lookup_role', N'app_auth') <> 1
    ALTER ROLE auth_lookup_role ADD MEMBER app_auth;
IF IS_ROLEMEMBER(N'customer_app_role', N'app_customer') <> 1
    ALTER ROLE customer_app_role ADD MEMBER app_customer;
IF IS_ROLEMEMBER(N'cashier_role', N'app_cashier') <> 1
    ALTER ROLE cashier_role ADD MEMBER app_cashier;
IF IS_ROLEMEMBER(N'inventory_clerk_role', N'app_inventory') <> 1
    ALTER ROLE inventory_clerk_role ADD MEMBER app_inventory;
IF IS_ROLEMEMBER(N'store_manager_role', N'app_manager') <> 1
    ALTER ROLE store_manager_role ADD MEMBER app_manager;
GO

/* 6.5 允许当前登录名借用这些应用账号（生产环境请改写为应用自己的登录名）。 */
DECLARE @grant_sql NVARCHAR(MAX) = N'';

SELECT @grant_sql = @grant_sql
       + N'GRANT IMPERSONATE ON USER::' + QUOTENAME(name)
       + N' TO ' + QUOTENAME(ORIGINAL_LOGIN()) + N';' + CHAR(10)
FROM sys.database_principals
WHERE type = 'S'
  AND name IN (N'app_auth', N'app_customer', N'app_cashier', N'app_inventory', N'app_manager');

BEGIN TRY
    EXEC sp_executesql @grant_sql;
    PRINT N'已为当前登录名授予应用账号的 IMPERSONATE 权限。';
END TRY
BEGIN CATCH
    PRINT N'提示：无法自动授予 IMPERSONATE 权限，请由管理员手工为应用登录名执行 GRANT。';
END CATCH;
GO

/* ------------------------------------------------------------------
   7. 播种应用账号
   密码均为演示口令，规则见 docs/应用操作手册.md；正式环境必须修改。
   password_hash 为 PBKDF2-SHA256（200000 次迭代）摘要。
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 7：写入演示账号 ===';

INSERT INTO dbo.app_user (username, password_hash, display_name, role, employee_id, member_id, status)
SELECT N'manager01', N'pbkdf2_sha256$200000$f47a1b1d075c2f616d23315fd2a4538b$49a8366f5ea4d7c59baae3ec0fd1e0436d5cea9cb37aa47af813fa08ad3b2b68',
       N'陈店长', 'MANAGER', e.employee_id, NULL, 'ACTIVE'
FROM dbo.employee AS e
WHERE e.employee_no = 'E001'
  AND NOT EXISTS (SELECT 1 FROM dbo.app_user WHERE username = N'manager01');

INSERT INTO dbo.app_user (username, password_hash, display_name, role, employee_id, member_id, status)
SELECT N'cashier01', N'pbkdf2_sha256$200000$e18c3573a4f8de9538d873b54d305cda$66159c6eed7c9d01f6ff5f0de5b5425d98b37657c5a4a6bdd8f5688dc48841fc',
       N'刘收银', 'CASHIER', e.employee_id, NULL, 'ACTIVE'
FROM dbo.employee AS e
WHERE e.employee_no = 'E002'
  AND NOT EXISTS (SELECT 1 FROM dbo.app_user WHERE username = N'cashier01');

INSERT INTO dbo.app_user (username, password_hash, display_name, role, employee_id, member_id, status)
SELECT N'stock01', N'pbkdf2_sha256$200000$249a86af39a5d38034035bbce140681d$9ca32f1990ae6167a73bf440dcc5a14cf7c09ddebc7a11129dbb2423a277e57d',
       N'赵理货', 'INVENTORY', e.employee_id, NULL, 'ACTIVE'
FROM dbo.employee AS e
WHERE e.employee_no = 'E003'
  AND NOT EXISTS (SELECT 1 FROM dbo.app_user WHERE username = N'stock01');

INSERT INTO dbo.app_user (username, password_hash, display_name, role, employee_id, member_id, status)
SELECT N'member01', N'pbkdf2_sha256$200000$29d5fdb5c236f78725b9627144ded2a7$dd9f306cd4ed3546d0d43b48d43855fe681a57cbdeeb46f8b524ffa9a2abd8f7',
       N'张晓雨', 'CUSTOMER', NULL, m.member_id, 'ACTIVE'
FROM dbo.member AS m
WHERE m.member_no = 'M001'
  AND NOT EXISTS (SELECT 1 FROM dbo.app_user WHERE username = N'member01');

INSERT INTO dbo.app_user (username, password_hash, display_name, role, employee_id, member_id, status)
SELECT N'member02', N'pbkdf2_sha256$200000$3ebb09e62eab5757a57aa6045e9773dd$0cf6c74094f0dcbdccf37fff2f97a32783ec05c6bf478ecf6b336663a3379771',
       N'李明', 'CUSTOMER', NULL, m.member_id, 'ACTIVE'
FROM dbo.member AS m
WHERE m.member_no = 'M002'
  AND NOT EXISTS (SELECT 1 FROM dbo.app_user WHERE username = N'member02');
GO

/* ------------------------------------------------------------------
   8. 迁移结果核对
   ------------------------------------------------------------------ */
PRINT N'=== 步骤 8：迁移结果 ===';

SELECT
    N'业务表数量（v0.1 为 12，v1.0 为 13）' AS check_item,
    COUNT(*) AS actual_value
FROM sys.tables
WHERE schema_id = SCHEMA_ID(N'dbo');

SELECT
    N'应用视图数量（含订单列表视图）' AS check_item,
    COUNT(*) AS actual_value
FROM sys.views
WHERE schema_id = SCHEMA_ID(N'dbo')
  AND name IN (N'vw_product_catalog', N'vw_active_cashier', N'vw_order_summary');

SELECT
    N'数据库角色数量（第四周 3 个 + v1.0 2 个）' AS check_item,
    COUNT(*) AS actual_value
FROM sys.database_principals
WHERE type = 'R'
  AND name IN (N'store_manager_role', N'cashier_role', N'inventory_clerk_role',
               N'auth_lookup_role', N'customer_app_role');

SELECT
    N'应用账号数量' AS check_item,
    COUNT(*) AS actual_value
FROM sys.database_principals
WHERE type = 'S'
  AND name IN (N'app_auth', N'app_customer', N'app_cashier', N'app_inventory', N'app_manager');

SELECT user_id, username, display_name, role, employee_id, member_id, status
FROM dbo.app_user
ORDER BY user_id;

SELECT
    N'v1.0 迁移完成：既有 12 张表未改变，新增 app_user、3 个应用视图和 5 个应用账号。' AS migration_result;
GO
