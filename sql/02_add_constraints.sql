/*
  第三周 02：添加外码与检查约束
  执行前提：已运行 01_create_tables.sql，且业务表为空。
*/

USE ConvenienceStoreDB;
GO

SET XACT_ABORT ON;
GO

ALTER TABLE dbo.category ADD
    CONSTRAINT CK_category_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'));
GO

ALTER TABLE dbo.product ADD
    CONSTRAINT FK_product_category
        FOREIGN KEY (category_id) REFERENCES dbo.category(category_id),
    CONSTRAINT CK_product_price
        CHECK (selling_price >= 0),
    CONSTRAINT CK_product_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'));
GO

ALTER TABLE dbo.inventory ADD
    CONSTRAINT FK_inventory_product
        FOREIGN KEY (product_id) REFERENCES dbo.product(product_id),
    CONSTRAINT CK_inventory_quantity
        CHECK (quantity >= 0),
    CONSTRAINT CK_inventory_reorder_level
        CHECK (reorder_level >= 0);
GO

ALTER TABLE dbo.member ADD
    CONSTRAINT CK_member_points_balance
        CHECK (points_balance >= 0),
    CONSTRAINT CK_member_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'));
GO

ALTER TABLE dbo.employee ADD
    CONSTRAINT CK_employee_job_type
        CHECK (job_type IN ('MANAGER', 'CASHIER', 'INVENTORY')),
    CONSTRAINT CK_employee_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'));
GO

ALTER TABLE dbo.supplier ADD
    CONSTRAINT CK_supplier_status
        CHECK (status IN ('ACTIVE', 'INACTIVE'));
GO

ALTER TABLE dbo.sales_order ADD
    CONSTRAINT FK_sales_order_member
        FOREIGN KEY (member_id) REFERENCES dbo.member(member_id),
    CONSTRAINT FK_sales_order_cashier
        FOREIGN KEY (cashier_id) REFERENCES dbo.employee(employee_id),
    CONSTRAINT CK_sales_order_status
        CHECK (order_status IN ('PENDING', 'COMPLETED', 'CANCELLED')),
    CONSTRAINT CK_sales_order_payment_method
        CHECK (payment_method IS NULL OR payment_method IN ('CASH', 'MOBILE', 'CARD')),
    CONSTRAINT CK_sales_order_amounts
        CHECK
        (
            original_amount >= 0
            AND discount_amount >= 0
            AND discount_amount <= original_amount
            AND paid_amount >= 0
            AND
            (
                (
                    order_status = 'COMPLETED'
                    AND paid_amount = original_amount - discount_amount
                )
                OR
                (
                    order_status IN ('PENDING', 'CANCELLED')
                    AND paid_amount = 0
                )
            )
        ),
    CONSTRAINT CK_sales_order_completed_payment
        CHECK
        (
            (order_status = 'COMPLETED' AND payment_method IS NOT NULL)
            OR
            (order_status IN ('PENDING', 'CANCELLED') AND payment_method IS NULL)
        );
GO

ALTER TABLE dbo.sales_order_item ADD
    CONSTRAINT FK_sales_order_item_order
        FOREIGN KEY (order_id) REFERENCES dbo.sales_order(order_id),
    CONSTRAINT FK_sales_order_item_product
        FOREIGN KEY (product_id) REFERENCES dbo.product(product_id),
    CONSTRAINT CK_sales_order_item_quantity
        CHECK (quantity > 0),
    CONSTRAINT CK_sales_order_item_price
        CHECK (unit_price >= 0);
GO

ALTER TABLE dbo.points_transaction ADD
    CONSTRAINT FK_points_transaction_member
        FOREIGN KEY (member_id) REFERENCES dbo.member(member_id),
    CONSTRAINT FK_points_transaction_order
        FOREIGN KEY (order_id) REFERENCES dbo.sales_order(order_id),
    CONSTRAINT CK_points_transaction_type_and_sign
        CHECK
        (
            (change_type = 'EARN' AND points_change > 0)
            OR (change_type = 'REDEEM' AND points_change < 0)
            OR (change_type = 'ADJUST' AND points_change <> 0)
        ),
    CONSTRAINT CK_points_transaction_balance
        CHECK (balance_after >= 0);
GO

ALTER TABLE dbo.purchase_order ADD
    CONSTRAINT FK_purchase_order_supplier
        FOREIGN KEY (supplier_id) REFERENCES dbo.supplier(supplier_id),
    CONSTRAINT FK_purchase_order_created_by
        FOREIGN KEY (created_by) REFERENCES dbo.employee(employee_id),
    CONSTRAINT FK_purchase_order_approved_by
        FOREIGN KEY (approved_by) REFERENCES dbo.employee(employee_id),
    CONSTRAINT CK_purchase_order_status
        CHECK (order_status IN ('DRAFT', 'APPROVED', 'RECEIVED', 'CANCELLED')),
    CONSTRAINT CK_purchase_order_amount
        CHECK (total_amount >= 0),
    CONSTRAINT CK_purchase_order_approval
        CHECK
        (
            order_status NOT IN ('APPROVED', 'RECEIVED')
            OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
        );
GO

ALTER TABLE dbo.purchase_order_item ADD
    CONSTRAINT FK_purchase_order_item_order
        FOREIGN KEY (purchase_order_id) REFERENCES dbo.purchase_order(purchase_order_id),
    CONSTRAINT FK_purchase_order_item_product
        FOREIGN KEY (product_id) REFERENCES dbo.product(product_id),
    CONSTRAINT CK_purchase_order_item_ordered_quantity
        CHECK (ordered_quantity > 0),
    CONSTRAINT CK_purchase_order_item_received_quantity
        CHECK (received_quantity >= 0 AND received_quantity <= ordered_quantity),
    CONSTRAINT CK_purchase_order_item_price
        CHECK (purchase_unit_price >= 0);
GO

ALTER TABLE dbo.inventory_transaction ADD
    CONSTRAINT FK_inventory_transaction_product
        FOREIGN KEY (product_id) REFERENCES dbo.product(product_id),
    CONSTRAINT FK_inventory_transaction_sales_order
        FOREIGN KEY (sales_order_id) REFERENCES dbo.sales_order(order_id),
    CONSTRAINT FK_inventory_transaction_purchase_order
        FOREIGN KEY (purchase_order_id) REFERENCES dbo.purchase_order(purchase_order_id),
    CONSTRAINT FK_inventory_transaction_operator
        FOREIGN KEY (operator_id) REFERENCES dbo.employee(employee_id),
    CONSTRAINT CK_inventory_transaction_source
        CHECK
        (
            (
                transaction_type = 'SALE_OUT'
                AND quantity_change < 0
                AND sales_order_id IS NOT NULL
                AND purchase_order_id IS NULL
            )
            OR
            (
                transaction_type = 'PURCHASE_IN'
                AND quantity_change > 0
                AND sales_order_id IS NULL
                AND purchase_order_id IS NOT NULL
            )
            OR
            (
                transaction_type = 'COUNT_GAIN'
                AND quantity_change > 0
                AND sales_order_id IS NULL
                AND purchase_order_id IS NULL
            )
            OR
            (
                transaction_type = 'COUNT_LOSS'
                AND quantity_change < 0
                AND sales_order_id IS NULL
                AND purchase_order_id IS NULL
            )
        );
GO

SELECT
    OBJECT_NAME(parent_object_id) AS table_name,
    name AS constraint_name,
    type_desc
FROM sys.objects
WHERE type IN ('F', 'C', 'D', 'PK', 'UQ')
  AND OBJECT_SCHEMA_NAME(parent_object_id) = N'dbo'
ORDER BY table_name, type_desc, constraint_name;
GO
