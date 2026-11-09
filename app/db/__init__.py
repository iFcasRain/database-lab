"""数据访问层（DAO）。

约束：
1. 只有本包内的模块可以直接使用 pyodbc，页面层与业务层不得出现 SQL；
2. 全部 SQL 使用参数占位符 ``?``，用户输入不参与字符串拼接；
3. 每个方法只负责“取数/写数”，业务规则判断放在 services 层。

业务层按如下方式使用：

    from app.db import connection, transaction

    with connection("CASHIER") as conn:      # 只读
        ...
    with transaction("MANAGER") as conn:     # 写操作，显式事务
        ...
"""

from app.db import base
from app.db.connection import check_health, connection, transaction
from app.db import user_dao, product_dao, inventory_dao, order_dao, member_dao

__all__ = [
    "base",
    "connection",
    "transaction",
    "check_health",
    "user_dao",
    "product_dao",
    "inventory_dao",
    "order_dao",
    "member_dao",
]
