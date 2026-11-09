"""数据访问层的公共工具：驱动异常翻译、参数化执行与结果转换。

本文件是唯一与 pyodbc 异常打交道的地方；上层拿到的永远是可读的业务错误。
所有 SQL 一律通过参数占位符 ``?`` 传参，不接受字符串拼接。
"""

import logging
from decimal import Decimal

import pyodbc

from app.errors import (
    AppError,
    ConstraintConflictError,
    DatabaseUnavailableError,
    ForbiddenError,
)

logger = logging.getLogger(__name__)

# SQL Server 拒绝访问时的原生错误号。
PERMISSION_DENIED_ERRORS = (229, 230, 262, 300)


def _sqlstate(exc):
    args = getattr(exc, "args", ())
    return args[0] if args else ""


def _native_message(exc):
    args = getattr(exc, "args", ())
    return args[1] if len(args) > 1 else str(exc)


def translate_db_error(exc):
    """把驱动异常翻译成统一的业务异常。"""
    if isinstance(exc, ConstraintConflictError):
        return exc
    if isinstance(exc, pyodbc.IntegrityError):
        message = _native_message(exc)
        logger.warning("数据库约束冲突：%s", message)
        return ConstraintConflictError(log_detail=message)
    if isinstance(exc, pyodbc.ProgrammingError):
        message = _native_message(exc)
        lowered = message.lower()
        if (
            "permission" in lowered
            or "denied" in lowered
            or "拒绝" in message
        ):
            logger.warning("数据库权限不足：%s", message)
            return ForbiddenError(log_detail=message)
        logger.error("数据库语句错误：%s", message)
        return AppError(log_detail=message)
    if isinstance(exc, pyodbc.OperationalError):
        logger.error("数据库连接或运行异常：%s", _native_message(exc))
        return DatabaseUnavailableError(log_detail=_native_message(exc))
    if isinstance(exc, pyodbc.DatabaseError):
        logger.error("数据库异常：%s", _native_message(exc))
        return AppError(log_detail=_native_message(exc))
    return exc


def _to_jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _normalize(row):
    return {key: _to_jsonable(value) for key, value in row.items()}


def rows_to_dicts(cursor):
    columns = [column[0] for column in cursor.description]
    return [
        _normalize(dict(zip(columns, row)))
        for row in cursor.fetchall()
    ]


def fetch_all(cursor, sql, params=()):
    """执行查询并返回 dict 列表。"""
    try:
        cursor.execute(sql, params)
        return rows_to_dicts(cursor)
    except pyodbc.Error as exc:
        raise translate_db_error(exc) from exc


def fetch_one(cursor, sql, params=()):
    """执行查询并返回首行，没有结果时返回 None。"""
    rows = fetch_all(cursor, sql, params)
    return rows[0] if rows else None


def execute(cursor, sql, params=()):
    """执行增删改并返回受影响行数。"""
    try:
        cursor.execute(sql, params)
        return cursor.rowcount
    except pyodbc.Error as exc:
        raise translate_db_error(exc) from exc


def insert_returning(cursor, sql, params=()):
    """执行带 OUTPUT 的插入，返回第一列（通常是自增主码）。"""
    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return row[0] if row else None
    except pyodbc.Error as exc:
        raise translate_db_error(exc) from exc


def execute_scalar(cursor, sql, params=()):
    """执行查询并返回首行首列。"""
    row = fetch_one(cursor, sql, params)
    if not row:
        return None
    return next(iter(row.values()))
