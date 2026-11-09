# 小卖部 ER 模型与 ER 图（第五周）

## 1. 文档目的与范围

第五周的任务是从第一阶段的 v0.1 表设计反推出规范的 ER 模型，检查实体、属性、标识、联系、基数和参与约束是否与业务一致。文档面向三类读者：需要核对设计的组员、需要验收的教师，以及第六周要写迁移脚本的同学。

范围覆盖小卖部的核心业务对象：商品分类、商品、当前库存、供应商、采购单、采购明细、会员、员工、销售订单、订单明细、积分流水、库存流水，以及第 7—9 周 Web 应用需要的应用账号。

产出物：

| 产出 | 位置 |
|---|---|
| ER 图（可编辑源文件） | `docs/er_diagram.svg` |
| ER 图（导出图片） | `result/week5_01_er_diagram.png` |
| ER 图生成脚本 | `tools/generate_er_diagram.py` |
| 业务规则与映射清单 | [业务规则映射清单](业务规则映射清单.md) |
| v0.1 问题清单 | [v0.1问题清单](v0.1问题清单.md) |

## 2. 表示法与图例

ER 图采用鸦爪（crow's foot）表示法，与关系模型的对应关系最直接：

| 图形 | 含义 |
|---|---|
| 矩形 | 一个实体（对应一张表） |
| 矩形首行 | 实体名（英文表名）与中文业务名称 |
| `PK` | 主码（primary key），决定该实体的一行 |
| `UQ` | 候选码（unique），业务上也能唯一标识一行 |
| `FK` | 外码，实现实体之间的联系 |
| 实体之间的连线 | 一个联系 |
| 短竖线 `|` | 连线“一”的一端：最多一条对应记录 |
| 三叉鸦爪 | 连线“多”的一端：可以有多条对应记录 |
| 小圆圈 `o` | 该端可以不参与联系（0..1 或 0..N） |
| 线上的数字 | 该端的最小/最大基数，例如 `1`、`N`、`0..1`、`0..N` |

图中只画关键属性（主码、候选码、外码和少量业务属性），完整字段、类型、默认值和取值范围见[关系模式与数据字典](关系模式与数据字典.md)。

## 3. 实体清单

| 序号 | 实体 | 业务含义 | 主码 | 候选码 | 是否独立保存 | 理由 |
|---:|---|---|---|---|---|---|
| 1 | CATEGORY 商品分类 | 商品的分类目录 | `category_id` | `category_code`、`category_name` | 是 | 分类被多个商品共享，独立保存避免在每个商品上重复存分类名称 |
| 2 | PRODUCT 商品 | 门店销售的商品与当前售价 | `product_id` | `product_code`、`barcode` | 是 | 商品是销售与库存的核心对象，价格会变动，需要独立维护 |
| 3 | INVENTORY 当前库存 | 每种商品现在的可售数量 | `product_id` | 无（`product_id` 同时是外码） | 是 | 与商品 1:1 但更新频率和权限完全不同（店长维护商品、库存管理员维护数量） |
| 4 | SUPPLIER 供应商 | 补货协作方 | `supplier_id` | `supplier_code` | 是 | 供应商被多张采购单引用，且与门店内部人员无关 |
| 5 | PURCHASE_ORDER 采购单 | 一次补货申请与审批 | `purchase_order_id` | `purchase_order_no` | 是 | 一张采购单包含多种商品，金额、状态、审批人属于单据级属性 |
| 6 | PURCHASE_ORDER_ITEM 采购明细 | 采购单中的一种商品 | `purchase_order_item_id` | (`purchase_order_id`, `product_id`) | 是 | 采购单与商品是多对多，必须用关联实体表达数量与进价 |
| 7 | MEMBER 会员 | 会员身份与当前积分 | `member_id` | `member_no`、`phone` | 是 | 会员可以没有订单，订单也可以没有会员，二者独立 |
| 8 | EMPLOYEE 员工 | 门店员工与业务岗位 | `employee_id` | `employee_no`、`phone` | 是 | 员工是订单、采购单、库存流水的经办人，被反复引用 |
| 9 | SALES_ORDER 销售订单 | 一笔交易的整体信息 | `order_id` | `order_no` | 是 | 订单级属性（时间、状态、金额、支付方式、经办人）不属于任何明细 |
| 10 | SALES_ORDER_ITEM 销售订单明细 | 订单中的一种商品 | `order_item_id` | (`order_id`, `product_id`) | 是 | 订单与商品是多对多，且必须保存成交单价以保护历史交易 |
| 11 | POINTS_TRANSACTION 积分流水 | 一次积分变化 | `points_transaction_id` | `transaction_no` | 是 | 余额变化需要可追溯的审计记录，一笔订单可能产生两条流水 |
| 12 | INVENTORY_TRANSACTION 库存流水 | 一次库存变化 | `inventory_transaction_id` | `transaction_no` | 是 | 当前库存只保存结果，变化依据必须单独留痕 |
| 13 | APP_USER 应用账号 | Web 应用的登录账号与角色 | `user_id` | `username` | 是（v1.0 新增） | 登录信息不属于员工也不属于会员：顾客账号对应会员，员工账号对应员工，映射关系一对一 |

## 4. 主要属性与标识分析

### 4.1 单一主码与复合候选码

本设计统一使用单属性代理码（整数自增）作为主码，理由是：

1. 业务编码可能被修改（例如商品重新编码），代理码不受影响；
2. 外码只需要保存一个整数，订单明细等关联表更紧凑；
3. 代理码与业务语义解耦，便于历史数据保持一致。

同时，业务上能唯一识别实体的属性设为候选码（`UQ`）：

| 实体 | 候选码 | 说明 |
|---|---|---|
| CATEGORY | `category_code`、`category_name` | 单门店范围内分类名不会重复 |
| PRODUCT | `product_code`、`barcode` | 门店编码与条码都能唯一识别商品 |
| MEMBER | `member_no`、`phone` | 会员号与手机号都能唯一定位会员 |
| EMPLOYEE | `employee_no`、`phone` | 工号与手机号都唯一 |
| SUPPLIER | `supplier_code` | 供应商名称可能因分公司重名，不作候选码 |
| SALES_ORDER | `order_no` | 对外展示的订单号 |
| SALES_ORDER_ITEM | (`order_id`, `product_id`) | 复合候选码：同一订单内同一商品合并为一条明细 |
| POINTS_TRANSACTION | `transaction_no` | 积分流水号 |
| PURCHASE_ORDER | `purchase_order_no` | 采购单号 |
| PURCHASE_ORDER_ITEM | (`purchase_order_id`, `product_id`) | 复合候选码：同一采购单内同一商品只出现一次 |
| INVENTORY_TRANSACTION | `transaction_no` | 库存流水号 |
| APP_USER | `username` | 登录名唯一 |

### 4.2 为什么订单明细使用复合候选码而不是“明细编号 + 商品”

`order_item_id` 是主码，保证每条明细可被单独更新或删除；(`order_id`, `product_id`) 作为复合候选码，表达“同一订单中同一商品只出现一次”的业务规则。如果允许同一商品在一张订单中出现两行，会出现两条成交单价，退货和核对时无法判断以哪一行为准。

## 5. 联系清单

| 编号 | 联系 | 两端实体 | 基数 | 参与约束 | 对应外码 |
|---:|---|---|---|---|---|
| R1 | 分类包含商品 | CATEGORY — PRODUCT | 1 : N | 商品必须属于一个分类；分类可以暂时没有商品 | `product.category_id` |
| R2 | 商品拥有库存 | PRODUCT — INVENTORY | 1 : 1 | 商品必须有且只有一条库存记录 | `inventory.product_id` |
| R3 | 供应商供货 | SUPPLIER — PURCHASE_ORDER | 1 : N | 采购单必须有供应商；供应商可以暂时没有采购单 | `purchase_order.supplier_id` |
| R4 | 采购单包含明细 | PURCHASE_ORDER — PURCHASE_ORDER_ITEM | 1 : N | 采购单至少一条明细；明细必须属于一张采购单 | `purchase_order_item.purchase_order_id` |
| R5 | 商品被采购 | PRODUCT — PURCHASE_ORDER_ITEM | 1 : N | 采购明细必须有商品；商品可以从未被采购 | `purchase_order_item.product_id` |
| R6 | 会员下单 | MEMBER — SALES_ORDER | 1 : N | 订单可以是非会员（0..1）；会员可以没有订单 | `sales_order.member_id`（可空） |
| R7 | 员工经办订单 | EMPLOYEE — SALES_ORDER | 1 : N | 订单必须有经办收银员 | `sales_order.cashier_id` |
| R8 | 订单包含明细 | SALES_ORDER — SALES_ORDER_ITEM | 1 : N | 订单至少一条明细；明细必须属于一张订单 | `sales_order_item.order_id` |
| R9 | 商品被销售 | PRODUCT — SALES_ORDER_ITEM | 1 : N | 明细必须有商品；商品可以从未被销售 | `sales_order_item.product_id` |
| R10 | 会员拥有积分流水 | MEMBER — POINTS_TRANSACTION | 1 : N | 流水必须有会员；会员可以没有流水 | `points_transaction.member_id` |
| R11 | 订单产生积分流水 | SALES_ORDER — POINTS_TRANSACTION | 1 : N | 流水可以来自订单（0..1）；一笔订单可产生抵扣与获得两条流水 | `points_transaction.order_id`（可空） |
| R12 | 员工创建或审批采购单 | EMPLOYEE — PURCHASE_ORDER | 1 : N | 采购单必须有创建人；审批人在审批前为空 | `purchase_order.created_by`、`approved_by` |
| R13 | 商品产生库存流水 | PRODUCT — INVENTORY_TRANSACTION | 1 : N | 流水必须有商品；商品可以没有流水 | `inventory_transaction.product_id` |
| R14 | 销售出库 | SALES_ORDER — INVENTORY_TRANSACTION | 1 : N | 销售出库流水必须来自订单（`SALE_OUT`）；其他类型为空 | `inventory_transaction.sales_order_id` |
| R15 | 采购入库 | PURCHASE_ORDER — INVENTORY_TRANSACTION | 1 : N | 采购入库流水必须来自采购单（`PURCHASE_IN`） | `inventory_transaction.purchase_order_id` |
| R16 | 员工经办库存变化 | EMPLOYEE — INVENTORY_TRANSACTION | 1 : N | 库存流水必须有经办人 | `inventory_transaction.operator_id` |
| R17 | 员工拥有应用账号 | EMPLOYEE — APP_USER | 0..1 : 0..1 | 员工账号必须有员工；员工可以没有账号 | `app_user.employee_id`（可空） |
| R18 | 会员拥有应用账号 | MEMBER — APP_USER | 1 : 0..N | 顾客账号必须关联会员；会员可以没有账号 | `app_user.member_id`（可空） |

## 6. 参与约束的落地方式

ER 图区分“业务要求必须参与”和“数据库能强制必须参与”，这一点在第五周和第六周都必须说清楚：

| 业务要求 | 数据库层能否强制 | 实际落地 |
|---|---|---|
| 订单至少有一条明细 | 不能（外码只保证明细指向已存在的订单） | 写入订单与明细的同一个事务由业务层保证（`order_service.create_order`） |
| 采购单至少有一条明细 | 不能 | 当前版本由人工录入，回归脚本检查“没有明细的订单数量 = 0” |
| 商品必须有库存记录 | 不能 | 新增商品时在同一事务中插入库存记录（`product_service.create_product`） |
| 商品必须属于已存在且在用的分类 | 能（外码 + 检查约束） | `FK_product_category` |
| 订单必须有经办收银员 | 能（非空外码） | `cashier_id NOT NULL` + `FK_sales_order_cashier` |
| 会员订单的积分必须与流水一致 | 部分能 | `CK_points_transaction_balance` 限制余额非负，余额与流水的一致性由业务层事务和回归脚本共同保证 |
| 库存不能为负 | 能 | `CK_inventory_quantity` |
| 库存变化必须有依据 | 部分能 | `CK_inventory_transaction_source` 限定四种类型与来源单据的组合 |

## 7. ER 图与表结构的对照

| ER 图中的对象 | 数据库中的实现 |
|---|---|
| 13 个实体 | 13 张表（v0.1 的 12 张 + v1.0 的 `app_user`） |
| R1、R3、R6、R7、R10、R12、R16 | 直接从表外码实现（N 端保存 1 端的主码） |
| R2 | 主码即外码：`inventory.product_id` 同时是主码和外码 |
| R4、R8 | 明细表保存单据主码，并用复合唯一约束表达候选码 |
| R5、R9、R13 | 商品被明细或流水引用，商品表不需要保存反向字段 |
| R11、R14、R15 | 流水表保存来源单据外码，允许为空以支持盘点与人工调整 |
| R17、R18 | 应用账号用两个可空外码 + 检查约束保证“非空且仅一个” |

## 8. 设计说明

### 8.1 商品与库存为什么拆成两个实体

- 商品保存“是什么、卖多少钱”，库存保存“现在有多少”。两者的修改频率、责任人和并发特征完全不同：店长改价，库存管理员盘点。
- 如果合并成一张表，调价和盘点会互相阻塞，也无法对库存数量单独授权。
- 拆分后，库存数量变化必须写库存流水，调价不会产生库存流水，审计语义清晰。

### 8.2 订单与订单明细为什么必须拆

- 一张订单包含多种商品，把商品写在一行会出现重复组，违反 1NF。
- 订单级属性（时间、状态、支付方式、经办人）如果在每条明细重复保存，会出现更新异常：修改订单状态要改多行，漏改就产生矛盾数据。
- 拆分后订单明细只保留“本单这个商品买了多少、按什么单价成交”，历史成交价与当前售价解耦。

### 8.3 为什么还要“积分流水”和“库存流水”

`member.points_balance` 和 `inventory.quantity` 是便于快速读取的当前状态，但它们无法回答“为什么变成这个数”。流水表保存每一次变化的方向、数量、来源单据和经办人，是审计与对账的依据。二者必须在同一个事务中更新，这也是第 7—9 周事务边界的核心场景。

### 8.4 应用账号为什么单独建实体

会员和员工各有自己的业务属性（积分、岗位、联系方式），都不应保存登录口令。应用账号只保存登录名、口令摘要、角色和外码，做到：

1. 一个员工或会员可以有多个账号，也可以暂时没有账号；
2. 口令摘要与业务数据分离，泄露风险可控；
3. 角色（顾客 / 店员 / 库存管理员 / 店长）与数据库中的授权一一对应。

## 9. 验证记录

| 验证项 | 在 ER 图中的体现 | 在数据库中的验证 |
|---|---|---|
| 多商品订单 | SALES_ORDER 1:N SALES_ORDER_ITEM | 样例订单 `SO202609230001` 含 2 条明细；回归检查“明细合计 = 原价” |
| 散客购买 | MEMBER 0..1 : N SALES_ORDER | 样例订单 `SO202609230003` 的 `member_id` 为空，界面显示“非会员” |
| 会员购买与积分 | MEMBER 1:N POINTS_TRANSACTION，SALES_ORDER 0..1:N POINTS_TRANSACTION | 样例订单 `SO202609230001` 产生 REDEEM 与 EARN 两条流水 |
| 库存查询 | PRODUCT 1:1 INVENTORY，PRODUCT 1:N INVENTORY_TRANSACTION | `vw_inventory_status` 返回纯牛奶 8 / 预警 10，显示需要补货 |
| 销售出库必须关联订单 | R14 的参与约束 | `CK_inventory_transaction_source` 拒绝 `SALE_OUT` 缺少 `sales_order_id` |
| 顾客与店员的权限差异 | R17、R18 | 应用账号分别加入 `customer_app_role` 与 `store_manager_role`，回归脚本验证授权差异 |

## 10. ER 图的重绘方式

ER 图由脚本生成，修改实体或联系后重新运行即可：

```bash
python tools/generate_er_diagram.py
```

脚本输出 `docs/er_diagram.svg`（可编辑源文件），用浏览器打开该 SVG 后截图或导出即可得到 `result/week5_01_er_diagram.png`。
