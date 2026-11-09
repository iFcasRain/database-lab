"""业务层的输入校验工具。

页面层的校验只负责体验，真正的校验必须在业务层再做一次；
所有用户输入在进入 SQL 之前都要先经过这里，既保证参数化查询，也保证取值范围。
"""

import re
from decimal import Decimal, InvalidOperation

from app.errors import ValidationError


def as_text(value, field, label, *, required=True, max_length=None, pattern=None,
            pattern_hint=None):
    if value is None:
        value = ""
    text = str(value).strip()
    if required and not text:
        raise ValidationError("请填写%s" % label, fields={field: "必填"})
    if len(text) > (max_length or 200):
        raise ValidationError(
            "%s不能超过 %d 个字符" % (label, max_length),
            fields={field: "长度超限"},
        )
    if pattern and text and not re.match(pattern, text):
        raise ValidationError(
            pattern_hint or "%s格式不正确" % label,
            fields={field: "格式不正确"},
        )
    return text


def as_int(value, field, label, *, required=True, minimum=None, maximum=None):
    if value in (None, ""):
        if required:
            raise ValidationError("请填写%s" % label, fields={field: "必填"})
        return None
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError("%s必须是整数" % label, fields={field: "必须是整数"})
    if minimum is not None and number < minimum:
        raise ValidationError(
            "%s不能小于 %d" % (label, minimum), fields={field: "超出范围"}
        )
    if maximum is not None and number > maximum:
        raise ValidationError(
            "%s不能大于 %d" % (label, maximum), fields={field: "超出范围"}
        )
    return number


def as_money(value, field, label, *, minimum=Decimal("0"), maximum=Decimal("99999999")):
    if value in (None, ""):
        raise ValidationError("请填写%s" % label, fields={field: "必填"})
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("%s必须是数字" % label, fields={field: "必须是数字"})
    if amount < minimum:
        raise ValidationError("%s不能小于 %s" % (label, minimum), fields={field: "超出范围"})
    if amount > maximum:
        raise ValidationError("%s不能大于 %s" % (label, maximum), fields={field: "超出范围"})
    return amount


def as_choice(value, allowed, field, label):
    text = str(value or "").strip().upper()
    if text not in allowed:
        raise ValidationError(
            "%s只能是 %s 之一" % (label, " / ".join(sorted(allowed))),
            fields={field: "取值不在允许范围"},
        )
    return text


def as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")
