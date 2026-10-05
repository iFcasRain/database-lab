/*
  第三周 01：创建 12 张业务表
  执行前提：已运行 00_create_database.sql。
  安全设计：如果发现任一目标表已存在，脚本立即停止，避免覆盖已有数据。
*/

USE ConvenienceStoreDB;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'dbo.category', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.product', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.inventory', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.member', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.employee', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.supplier', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.sales_order', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.sales_order_item', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.points_transaction', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.purchase_order', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.purchase_order_item', N'U') IS NOT NULL
   OR OBJECT_ID(N'dbo.inventory_transaction', N'U') IS NOT NULL
BEGIN
    THROW 50001, N'检测到目标表已存在。为保护数据，本脚本已停止。请使用新建的空数据库完成复现。', 1;
END;
GO

CREATE TABLE dbo.category
(
    category_id   INT IDENTITY(1, 1) NOT NULL,
    category_code VARCHAR(20) NOT NULL,
    category_name NVARCHAR(50) NOT NULL,
    status        VARCHAR(10) NOT NULL
        CONSTRAINT DF_category_status DEFAULT ('ACTIVE'),
    created_at    DATETIME2(0) NOT NULL
        CONSTRAINT DF_category_created_at DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_category PRIMARY KEY (category_id),
    CONSTRAINT UQ_category_code UNIQUE (category_code),
    CONSTRAINT UQ_category_name UNIQUE (category_name)
);
GO

CREATE TABLE dbo.product
(
    product_id    INT IDENTITY(101, 1) NOT NULL,
    product_code  VARCHAR(20) NOT NULL,
    barcode       VARCHAR(32) NOT NULL,
    product_name  NVARCHAR(100) NOT NULL,
    category_id   INT NOT NULL,
    unit          NVARCHAR(10) NOT NULL,
    selling_price DECIMAL(10, 2) NOT NULL,
    status        VARCHAR(12) NOT NULL
        CONSTRAINT DF_product_status DEFAULT ('ACTIVE'),
    created_at    DATETIME2(0) NOT NULL
        CONSTRAINT DF_product_created_at DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_product PRIMARY KEY (product_id),
    CONSTRAINT UQ_product_code UNIQUE (product_code),
    CONSTRAINT UQ_product_barcode UNIQUE (barcode)
);
GO

CREATE TABLE dbo.inventory
(
    product_id    INT NOT NULL,
    quantity      INT NOT NULL
        CONSTRAINT DF_inventory_quantity DEFAULT (0),
    reorder_level INT NOT NULL
        CONSTRAINT DF_inventory_reorder_level DEFAULT (10),
    updated_at    DATETIME2(0) NOT NULL
        CONSTRAINT DF_inventory_updated_at DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_inventory PRIMARY KEY (product_id)
);
GO

CREATE TABLE dbo.member
(
    member_id      INT IDENTITY(201, 1) NOT NULL,
    member_no      VARCHAR(20) NOT NULL,
    member_name    NVARCHAR(50) NOT NULL,
    phone          VARCHAR(20) NOT NULL,
    points_balance INT NOT NULL
        CONSTRAINT DF_member_points_balance DEFAULT (0),
    registered_at  DATETIME2(0) NOT NULL
        CONSTRAINT DF_member_registered_at DEFAULT (SYSDATETIME()),
    status          VARCHAR(10) NOT NULL
        CONSTRAINT DF_member_status DEFAULT ('ACTIVE'),
    remark          NVARCHAR(200) NULL,

    CONSTRAINT PK_member PRIMARY KEY (member_id),
    CONSTRAINT UQ_member_no UNIQUE (member_no),
    CONSTRAINT UQ_member_phone UNIQUE (phone)
);
GO

CREATE TABLE dbo.employee
(
    employee_id   INT IDENTITY(301, 1) NOT NULL,
    employee_no   VARCHAR(20) NOT NULL,
    employee_name NVARCHAR(50) NOT NULL,
    phone         VARCHAR(20) NOT NULL,
    job_type      VARCHAR(20) NOT NULL,
    hire_date     DATE NOT NULL,
    status        VARCHAR(10) NOT NULL
        CONSTRAINT DF_employee_status DEFAULT ('ACTIVE'),
    created_at    DATETIME2(0) NOT NULL
        CONSTRAINT DF_employee_created_at DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_employee PRIMARY KEY (employee_id),
    CONSTRAINT UQ_employee_no UNIQUE (employee_no),
    CONSTRAINT UQ_employee_phone UNIQUE (phone)
);
GO

CREATE TABLE dbo.supplier
(
    supplier_id   INT IDENTITY(401, 1) NOT NULL,
    supplier_code VARCHAR(20) NOT NULL,
    supplier_name NVARCHAR(100) NOT NULL,
    contact_name  NVARCHAR(50) NOT NULL,
    phone         VARCHAR(20) NOT NULL,
    address       NVARCHAR(200) NULL,
    status        VARCHAR(10) NOT NULL
        CONSTRAINT DF_supplier_status DEFAULT ('ACTIVE'),
    created_at    DATETIME2(0) NOT NULL
        CONSTRAINT DF_supplier_created_at DEFAULT (SYSDATETIME()),

    CONSTRAINT PK_supplier PRIMARY KEY (supplier_id),
    CONSTRAINT UQ_supplier_code UNIQUE (supplier_code)
);
GO

CREATE TABLE dbo.sales_order
(
    order_id        BIGINT IDENTITY(5001, 1) NOT NULL,
    order_no        VARCHAR(30) NOT NULL,
    member_id       INT NULL,
    cashier_id      INT NOT NULL,
    order_time      DATETIME2(0) NOT NULL
        CONSTRAINT DF_sales_order_order_time DEFAULT (SYSDATETIME()),
    order_status    VARCHAR(12) NOT NULL
        CONSTRAINT DF_sales_order_status DEFAULT ('PENDING'),
    payment_method  VARCHAR(12) NULL,
    original_amount DECIMAL(10, 2) NOT NULL,
    discount_amount DECIMAL(10, 2) NOT NULL
        CONSTRAINT DF_sales_order_discount DEFAULT (0),
    paid_amount     DECIMAL(10, 2) NOT NULL,

    CONSTRAINT PK_sales_order PRIMARY KEY (order_id),
    CONSTRAINT UQ_sales_order_no UNIQUE (order_no)
);
GO

CREATE TABLE dbo.sales_order_item
(
    order_item_id BIGINT IDENTITY(5101, 1) NOT NULL,
    order_id      BIGINT NOT NULL,
    product_id    INT NOT NULL,
    quantity      INT NOT NULL,
    unit_price    DECIMAL(10, 2) NOT NULL,

    CONSTRAINT PK_sales_order_item PRIMARY KEY (order_item_id),
    CONSTRAINT UQ_sales_order_item_order_product UNIQUE (order_id, product_id)
);
GO

CREATE TABLE dbo.points_transaction
(
    points_transaction_id BIGINT IDENTITY(5201, 1) NOT NULL,
    transaction_no        VARCHAR(30) NOT NULL,
    member_id             INT NOT NULL,
    order_id              BIGINT NULL,
    change_type           VARCHAR(12) NOT NULL,
    points_change         INT NOT NULL,
    balance_after         INT NOT NULL,
    occurred_at           DATETIME2(0) NOT NULL
        CONSTRAINT DF_points_transaction_occurred_at DEFAULT (SYSDATETIME()),
    remark                NVARCHAR(200) NULL,

    CONSTRAINT PK_points_transaction PRIMARY KEY (points_transaction_id),
    CONSTRAINT UQ_points_transaction_no UNIQUE (transaction_no)
);
GO

CREATE TABLE dbo.purchase_order
(
    purchase_order_id BIGINT IDENTITY(6001, 1) NOT NULL,
    purchase_order_no VARCHAR(30) NOT NULL,
    supplier_id       INT NOT NULL,
    created_by        INT NOT NULL,
    approved_by       INT NULL,
    order_date        DATE NOT NULL
        CONSTRAINT DF_purchase_order_order_date DEFAULT (CONVERT(DATE, SYSDATETIME())),
    order_status      VARCHAR(12) NOT NULL
        CONSTRAINT DF_purchase_order_status DEFAULT ('DRAFT'),
    total_amount      DECIMAL(10, 2) NOT NULL
        CONSTRAINT DF_purchase_order_total_amount DEFAULT (0),
    approved_at       DATETIME2(0) NULL,

    CONSTRAINT PK_purchase_order PRIMARY KEY (purchase_order_id),
    CONSTRAINT UQ_purchase_order_no UNIQUE (purchase_order_no)
);
GO

CREATE TABLE dbo.purchase_order_item
(
    purchase_order_item_id BIGINT IDENTITY(6101, 1) NOT NULL,
    purchase_order_id      BIGINT NOT NULL,
    product_id             INT NOT NULL,
    ordered_quantity       INT NOT NULL,
    received_quantity      INT NOT NULL
        CONSTRAINT DF_purchase_order_item_received DEFAULT (0),
    purchase_unit_price    DECIMAL(10, 2) NOT NULL,

    CONSTRAINT PK_purchase_order_item PRIMARY KEY (purchase_order_item_id),
    CONSTRAINT UQ_purchase_order_item_order_product
        UNIQUE (purchase_order_id, product_id)
);
GO

CREATE TABLE dbo.inventory_transaction
(
    inventory_transaction_id BIGINT IDENTITY(7001, 1) NOT NULL,
    transaction_no           VARCHAR(30) NOT NULL,
    product_id               INT NOT NULL,
    transaction_type         VARCHAR(20) NOT NULL,
    quantity_change          INT NOT NULL,
    sales_order_id           BIGINT NULL,
    purchase_order_id        BIGINT NULL,
    operator_id              INT NOT NULL,
    occurred_at              DATETIME2(0) NOT NULL
        CONSTRAINT DF_inventory_transaction_occurred_at DEFAULT (SYSDATETIME()),
    remark                   NVARCHAR(200) NULL,

    CONSTRAINT PK_inventory_transaction PRIMARY KEY (inventory_transaction_id),
    CONSTRAINT UQ_inventory_transaction_no UNIQUE (transaction_no)
);
GO

SELECT
    s.name AS schema_name,
    t.name AS table_name,
    SUM(p.rows) AS row_count
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.partitions AS p ON p.object_id = t.object_id AND p.index_id IN (0, 1)
WHERE s.name = N'dbo'
GROUP BY s.name, t.name
ORDER BY t.name;
GO
