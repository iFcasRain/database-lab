"""生成小卖部 v1.0 的 ER 图（可编辑的 SVG 源文件）。

用法（在 database-lab 目录下）：

    python tools/generate_er_diagram.py

脚本只依赖标准库，输出 docs/er_diagram.svg。
SVG 可直接在浏览器、Inkscape 或 VS Code 中打开和编辑；
导出 PNG 时用浏览器打开该 SVG 截图即可（结果见 result/week5_01_er_diagram.png）。

图中采用鸦爪（crow's foot）表示法：
    实体 = 矩形，第一行为表名，内部列出主码与关键属性；
    PK / UQ / FK 标记分别表示主码、候选码和外码；
    一的一端用短竖线，多的一端用三叉鸦爪，圆点表示“可以不参与”。
"""

import os
import sys
from xml.sax.saxutils import escape

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(BASE_DIR, "docs", "er_diagram.svg")

WIDTH = 1680
HEIGHT = 1080
BOX_W = 250
HEADER_H = 34
ROW_H = 22
PAD_BOTTOM = 10

COLOR_LINE = "#94a3b8"
COLOR_HEAD = "#16324f"
COLOR_TEXT = "#1f2937"
COLOR_MUTED = "#6b7280"
COLOR_PK = "#b45309"
COLOR_FK = "#2f6feb"
COLOR_UQ = "#0e7490"

ENTITIES = [
    {
        "name": "CATEGORY", "cn": "商品分类", "x": 40, "y": 70,
        "attrs": [("category_id", "PK"), ("category_code", "UQ"),
                  ("category_name", "UQ"), ("status", "")],
    },
    {
        "name": "PRODUCT", "cn": "商品", "x": 40, "y": 280,
        "attrs": [("product_id", "PK"), ("product_code", "UQ"), ("barcode", "UQ"),
                  ("product_name", ""), ("category_id", "FK"),
                  ("selling_price", ""), ("status", "")],
    },
    {
        "name": "INVENTORY", "cn": "当前库存", "x": 40, "y": 540,
        "attrs": [("product_id", "PK,FK"), ("quantity", ""),
                  ("reorder_level", ""), ("updated_at", "")],
    },
    {
        "name": "SUPPLIER", "cn": "供应商", "x": 40, "y": 800,
        "attrs": [("supplier_id", "PK"), ("supplier_code", "UQ"),
                  ("supplier_name", ""), ("contact_name", "")],
    },
    {
        "name": "SALES_ORDER_ITEM", "cn": "销售订单明细", "x": 370, "y": 70,
        "attrs": [("order_item_id", "PK"), ("order_id", "FK"),
                  ("product_id", "FK"), ("quantity", ""), ("unit_price", "")],
    },
    {
        "name": "PURCHASE_ORDER_ITEM", "cn": "采购明细", "x": 370, "y": 430,
        "attrs": [("purchase_order_item_id", "PK"), ("purchase_order_id", "FK"),
                  ("product_id", "FK"), ("ordered_quantity", ""),
                  ("received_quantity", "")],
    },
    {
        "name": "INVENTORY_TRANSACTION", "cn": "库存流水", "x": 370, "y": 720,
        "attrs": [("inventory_transaction_id", "PK"), ("transaction_no", "UQ"),
                  ("product_id", "FK"), ("transaction_type", ""),
                  ("quantity_change", ""), ("sales_order_id", "FK")],
    },
    {
        "name": "SALES_ORDER", "cn": "销售订单", "x": 700, "y": 280,
        "attrs": [("order_id", "PK"), ("order_no", "UQ"), ("member_id", "FK"),
                  ("cashier_id", "FK"), ("order_status", ""), ("paid_amount", "")],
    },
    {
        "name": "PURCHASE_ORDER", "cn": "采购单", "x": 700, "y": 540,
        "attrs": [("purchase_order_id", "PK"), ("purchase_order_no", "UQ"),
                  ("supplier_id", "FK"), ("created_by", "FK"),
                  ("approved_by", "FK"), ("total_amount", "")],
    },
    {
        "name": "POINTS_TRANSACTION", "cn": "积分流水", "x": 700, "y": 70,
        "attrs": [("points_transaction_id", "PK"), ("transaction_no", "UQ"),
                  ("member_id", "FK"), ("order_id", "FK"),
                  ("change_type", ""), ("points_change", "")],
    },
    {
        "name": "MEMBER", "cn": "会员", "x": 1030, "y": 70,
        "attrs": [("member_id", "PK"), ("member_no", "UQ"), ("member_name", ""),
                  ("phone", "UQ"), ("points_balance", "")],
    },
    {
        "name": "EMPLOYEE", "cn": "员工", "x": 1030, "y": 300,
        "attrs": [("employee_id", "PK"), ("employee_no", "UQ"), ("employee_name", ""),
                  ("job_type", ""), ("status", "")],
    },
    {
        "name": "APP_USER", "cn": "应用账号", "x": 1330, "y": 600,
        "attrs": [("user_id", "PK"), ("username", "UQ"), ("role", ""),
                  ("employee_id", "FK"), ("member_id", "FK")],
    },
]

# (起点实体, 起点边, 起点偏移比例, 终点实体, 终点边, 终点偏移比例,
#  起点标记, 终点标记, 折线中间点)
EDGES = [
    ("CATEGORY", "bottom", 0.5, "PRODUCT", "top", 0.5, "1", "N", []),
    ("PRODUCT", "bottom", 0.5, "INVENTORY", "top", 0.5, "1", "1", []),
    ("PRODUCT", "right", 0.30, "SALES_ORDER_ITEM", "left", 0.55, "1", "N",
     [(330, 0), (330, 154)]),
    ("PRODUCT", "right", 0.58, "PURCHASE_ORDER_ITEM", "left", 0.45, "1", "N",
     [(350, 0), (350, 498)]),
    ("PRODUCT", "right", 0.80, "INVENTORY_TRANSACTION", "left", 0.55, "1", "N",
     [(355, 0), (355, 816)]),
    ("SALES_ORDER", "left", 0.40, "SALES_ORDER_ITEM", "right", 0.60, "1", "N",
     [(655, 0), (655, 161)]),
    ("SALES_ORDER", "top", 0.5, "POINTS_TRANSACTION", "bottom", 0.5, "0..1", "N", []),
    ("POINTS_TRANSACTION", "right", 0.48, "MEMBER", "left", 0.48, "N", "1", []),
    ("MEMBER", "bottom", 0.5, "SALES_ORDER", "right", 0.18, "0..1", "N",
     [(1155, 0), (1155, 311)]),
    ("EMPLOYEE", "left", 0.55, "SALES_ORDER", "right", 0.60, "1", "N", []),
    ("EMPLOYEE", "bottom", 0.5, "PURCHASE_ORDER", "right", 0.05, "1", "N",
     [(1155, 0), (1155, 549)]),
    ("PURCHASE_ORDER", "left", 0.115, "PURCHASE_ORDER_ITEM", "right", 0.855, "1", "N", []),
    ("SUPPLIER", "right", 0.35, "PURCHASE_ORDER", "left", 0.75, "1", "N",
     [(340, 0), (340, 670)]),
    ("EMPLOYEE", "left", 0.85, "INVENTORY_TRANSACTION", "right", 0.55, "1", "N",
     [(1000, 0), (1000, 816)]),
    ("SALES_ORDER", "left", 0.85, "INVENTORY_TRANSACTION", "right", 0.30, "0..1", "N",
     [(660, 0), (660, 772)]),
    ("EMPLOYEE", "right", 0.30, "APP_USER", "left", 0.30, "0..1", "0..1",
     [(1310, 0), (1310, 646)]),
    ("MEMBER", "right", 0.70, "APP_USER", "left", 0.75, "1", "0..N",
     [(1320, 0), (1320, 714)]),
]


def box_height(entity):
    return HEADER_H + ROW_H * len(entity["attrs"]) + PAD_BOTTOM


def box_rect(entity):
    return entity["x"], entity["y"], BOX_W, box_height(entity)


def anchor(entity, side, ratio):
    x, y, w, h = box_rect(entity)
    if side == "left":
        return (x, y + h * ratio)
    if side == "right":
        return (x + w, y + h * ratio)
    if side == "top":
        return (x + w * ratio, y)
    return (x + w * ratio, y + h)


def unit(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
    return dx / length, dy / length


def bar(p, direction, size=9):
    """一的一端：垂直于连线的短竖线。"""
    ux, uy = direction
    px, py = -uy, ux
    return [(p[0] - px * size, p[1] - py * size), (p[0] + px * size, p[1] + py * size)]


def circle(p, radius=4.5):
    return p, radius


def crow_foot(p, direction, size=11, spread=8):
    """多的一端：三叉鸦爪。"""
    ux, uy = direction
    px, py = -uy, ux
    base = (p[0] - ux * size, p[1] - uy * size)
    tip = (p[0], p[1])
    left = (base[0] + px * spread, base[1] + py * spread)
    right = (base[0] - px * spread, base[1] - py * spread)
    return [(tip, left), (tip, base), (tip, right)]


def build_svg():
    parts = []
    parts.append(
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" font-family="Microsoft YaHei, Segoe UI, sans-serif">'
        % (WIDTH, HEIGHT, WIDTH, HEIGHT)
    )
    parts.append('<rect width="100%" height="100%" fill="#fbfcfe"/>')
    parts.append(
        '<text x="40" y="44" font-size="22" font-weight="700" fill="%s">'
        "小卖部经营管理数据库 v1.0 ER 图</text>" % COLOR_HEAD
    )
    parts.append(
        '<text x="40" y="66" font-size="12.5" fill="%s">'
        "实体 13 个（v0.1 的 12 张表 + 第 6 周迁移新增的 APP_USER）；"
        "标注主码、候选码、外码与联系基数；鸦爪表示法</text>" % COLOR_MUTED
    )

    by_name = {entity["name"]: entity for entity in ENTITIES}
    labels = []

    # 连线先画，避免压住实体框
    for source, s_side, s_ratio, target, t_side, t_ratio, s_label, t_label, waypoints in EDGES:
        start = anchor(by_name[source], s_side, s_ratio)
        end = anchor(by_name[target], t_side, t_ratio)
        points = [start]
        for wx, wy in waypoints:
            points.append((wx if wx else start[0], wy if wy else start[1]))
        points.append(end)

        # 中间点若某一维为 0，则沿用起点对应坐标（写成折线时按需替换）
        cleaned = [points[0]]
        for point in points[1:-1]:
            cleaned.append((point[0], point[1]))
        cleaned.append(points[-1])

        d = " ".join("%.1f,%.1f" % (px, py) for px, py in cleaned)
        parts.append(
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="1.5"/>'
            % (d, COLOR_LINE)
        )

        d_start = unit(cleaned[1], cleaned[0])
        d_end = unit(cleaned[-2], cleaned[-1])

        if s_label in ("1",):
            (ax, ay), (bx, by) = bar(cleaned[0], d_start)
            parts.append(
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5"/>'
                % (ax, ay, bx, by, COLOR_LINE)
            )
        if t_label in ("1",):
            (ax, ay), (bx, by) = bar(cleaned[-1], d_end)
            parts.append(
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5"/>'
                % (ax, ay, bx, by, COLOR_LINE)
            )
        if s_label in ("N", "0..N"):
            for a, b in crow_foot(cleaned[0], d_start):
                parts.append(
                    '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5"/>'
                    % (a[0], a[1], b[0], b[1], COLOR_LINE)
                )
        if t_label in ("N", "0..N"):
            for a, b in crow_foot(cleaned[-1], d_end):
                parts.append(
                    '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5"/>'
                    % (a[0], a[1], b[0], b[1], COLOR_LINE)
                )

        # 机动性：圆点表示可以不参与
        for label, point, direction in (
            (s_label, cleaned[0], d_start),
            (t_label, cleaned[-1], d_end),
        ):
            if label.startswith("0"):
                cx, cy = point[0] + direction[0] * 17, point[1] + direction[1] * 17
                parts.append(
                    '<circle cx="%.1f" cy="%.1f" r="4" fill="#ffffff" stroke="%s" stroke-width="1.3"/>'
                    % (cx, cy, COLOR_LINE)
                )

        # 基数文字（先缓存，等实体框画完再写，避免被框盖住）
        for label, point, direction in (
            (s_label, cleaned[0], d_start),
            (t_label, cleaned[-1], d_end),
        ):
            # direction 指向实体框，因此取反后才会落在框外的连线上
            offset_x = -direction[0] * 24
            offset_y = -direction[1] * 24
            if direction[1] < 0:
                offset_y -= 8
            elif direction[1] > 0:
                offset_y += 18
            else:
                offset_y += 6
            if direction[0] != 0:
                offset_x += 4 if direction[0] > 0 else -4
            labels.append((point[0] + offset_x, point[1] + offset_y, label))

    # 实体框
    for entity in ENTITIES:
        x, y, w, h = box_rect(entity)
        parts.append(
            '<g><rect x="%d" y="%d" width="%d" height="%d" rx="7" fill="#ffffff" '
            'stroke="%s" stroke-width="1.6"/>' % (x, y, w, h, COLOR_HEAD)
        )
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" rx="7" fill="%s"/>'
            % (x, y, w, HEADER_H, COLOR_HEAD)
        )
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
            % (x, y + HEADER_H - 7, w, 7, COLOR_HEAD)
        )
        name_font = 13 if len(entity["name"]) <= 12 else 11.5
        name_width = len(entity["name"]) * (7.6 if name_font == 13 else 6.7)
        cn_text = entity["cn"]
        cn_font = 10.5
        cn_width = len(cn_text) * 10.6
        show_cn = 12 + name_width + 10 + cn_width + 10 <= w

        parts.append(
            '<text x="%d" y="%d" font-size="%.1f" font-weight="700" fill="#ffffff">%s</text>'
            % (x + 12, y + 22, name_font, escape(entity["name"]))
        )
        if show_cn:
            parts.append(
                '<text x="%d" y="%d" font-size="%.1f" fill="#cbd5e1" text-anchor="end">%s</text>'
                % (x + w - 10, y + 22, cn_font, escape(cn_text))
            )

        for index, (attr, tag) in enumerate(entity["attrs"]):
            row_y = y + HEADER_H + ROW_H * index + 15
            parts.append(
                '<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
                % (x + 12, row_y, COLOR_TEXT, escape(attr))
            )
            if tag:
                color = COLOR_PK if "PK" in tag else (COLOR_UQ if "UQ" in tag else COLOR_FK)
                parts.append(
                    '<text x="%d" y="%d" font-size="10.5" font-weight="700" fill="%s" '
                    'text-anchor="end">%s</text>'
                    % (x + w - 12, row_y, color, escape(tag))
                )
        parts.append("</g>")

    # 基数文字最后画，带浅色描边保证在连线与框上仍然清晰
    for lx, ly, label in labels:
        parts.append(
            '<text x="%.1f" y="%.1f" font-size="11" font-weight="700" fill="%s" '
            'text-anchor="middle" paint-order="stroke" stroke="#fbfcfe" stroke-width="3.5" '
            'stroke-linejoin="round">%s</text>'
            % (lx, ly, COLOR_MUTED, escape(label))
        )

    # 图例
    legend_x, legend_y = 700, 900
    parts.append(
        '<g><rect x="%d" y="%d" width="620" height="140" rx="8" fill="#ffffff" '
        'stroke="#cbd5e1" stroke-width="1.2"/>' % (legend_x, legend_y)
    )
    parts.append(
        '<text x="%d" y="%d" font-size="13" font-weight="700" fill="%s">图例</text>'
        % (legend_x + 16, legend_y + 24, COLOR_HEAD)
    )
    legend_lines = [
        "PK 主码　UQ 候选码（唯一约束）　FK 外码",
        "一的一端：短竖线　　多的一端：三叉鸦爪",
        "圆点表示该实体可以不参与联系（0..1 / 0..N）",
        "CATEGORY → PRODUCT → INVENTORY 为 1:N 与 1:1；",
        "订单与明细、采购单与明细均为 1:N，一张单据至少一条明细",
        "APP_USER 由第 6 周 migration.sql 新增，关联 MEMBER 或 EMPLOYEE",
    ]
    for index, line in enumerate(legend_lines):
        parts.append(
            '<text x="%d" y="%d" font-size="11.5" fill="%s">%s</text>'
            % (legend_x + 16, legend_y + 46 + index * 15, COLOR_MUTED, escape(line))
        )
    parts.append("</g>")

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    svg = build_svg()
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        handle.write(svg)
    print("已生成：%s（%d 字节）" % (OUTPUT, len(svg.encode("utf-8"))))


if __name__ == "__main__":
    sys.exit(main())
