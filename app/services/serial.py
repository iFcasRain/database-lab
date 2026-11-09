"""流水号生成。

订单号使用“前缀 + 日期 + 顺序号”，便于人工识别；
库存流水号和积分流水号使用“前缀 + 精确到秒的时间 + 4 位随机后缀”，
在并发下几乎不会重复，且不必额外读取业务表（部分角色没有该表的查询权限）。
"""

import uuid
from datetime import datetime


def make_serial(prefix):
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return "%s%s%s" % (prefix, stamp, uuid.uuid4().hex[:4].upper())


def make_order_no(sequence):
    return "SO%s%04d" % (datetime.now().strftime("%Y%m%d"), int(sequence))
