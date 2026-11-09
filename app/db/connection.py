"""连接管理：建立连接、按角色收敛数据库权限、管理事务边界。

做法说明：
1. 应用只使用一个连接标识（默认是当前 Windows 账户）建立连接，不把口令写在代码里；
2. 连接建立后立即执行 ``EXECUTE AS USER``，切换成 migration.sql 创建的应用账号
   （app_customer / app_cashier / app_inventory / app_manager / app_auth）；
   之后这条连接上的一切 SQL 都受该账号在数据库中真实权限的约束；
3. 显式写出 BEGIN / COMMIT / ROLLBACK，业务层可以清楚看到事务边界；
4. 关闭连接池，保证一次请求结束即丢弃连接，不把身份上下文带入下一次请求。
"""

import logging
import re
from contextlib import contextmanager

import pyodbc
from flask import current_app

from app.db.base import translate_db_error
from app.errors import ConfigurationError

logger = logging.getLogger(__name__)

# 每个请求单独一条连接，身份上下文不会残留到其他请求。
pyodbc.pooling = False

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _connection_string(config):
    parts = [
        "DRIVER={%s}" % config["DB_DRIVER"],
        "SERVER=%s" % config["DB_SERVER"],
        "DATABASE=%s" % config["DB_DATABASE"],
    ]
    if config["DB_TRUSTED_CONNECTION"]:
        parts.append("Trusted_Connection=yes")
    else:
        parts.append("UID=%s" % config["DB_USER"])
        parts.append("PWD=%s" % config["DB_PASSWORD"])
    parts.append("Encrypt=%s" % config["DB_ENCRYPT"])
    parts.append("TrustServerCertificate=%s" % config["DB_TRUST_SERVER_CERTIFICATE"])
    parts.append("APP=ConvenienceStoreWeb")
    return ";".join(parts) + ";"


def _impersonate(connection, application_user):
    if not _SAFE_IDENTIFIER.match(application_user or ""):
        raise ConfigurationError("数据库应用账号配置不合法，请检查 .env")
    cursor = connection.cursor()
    try:
        # EXECUTE AS USER 只接受字符串常量，不接受方括号标识符。
        cursor.execute("EXECUTE AS USER = '%s';" % application_user)
    except pyodbc.Error as exc:
        detail = str(exc)
        logger.error("切换数据库应用账号失败：%s", detail)
        raise ConfigurationError(
            "数据库应用账号 %s 不可用，请先执行 sql/migration.sql" % application_user,
            log_detail=detail,
        ) from exc
    finally:
        cursor.close()


def _app_user_for(app_user_key):
    mapping = current_app.config["DB_APP_USER_MAP"]
    if app_user_key not in mapping:
        raise ConfigurationError("未知的数据库应用账号类型：%s" % app_user_key)
    return mapping[app_user_key]


@contextmanager
def connection(app_user_key):
    """获取一条已切换到指定应用账号的连接。只读操作用它。"""
    config = current_app.config
    application_user = _app_user_for(app_user_key)
    try:
        conn = pyodbc.connect(
            _connection_string(config),
            autocommit=True,
            timeout=config["DB_TIMEOUT"],
        )
    except pyodbc.Error as exc:
        logger.error("数据库连接失败：%s", exc)
        raise translate_db_error(exc) from exc

    try:
        _impersonate(conn, application_user)
        yield conn
    finally:
        try:
            conn.close()
        except pyodbc.Error:  # pragma: no cover - 关闭失败不影响业务结果
            logger.debug("关闭数据库连接时出现异常", exc_info=True)


@contextmanager
def transaction(app_user_key):
    """获取一条处于显式事务中的连接。写操作必须使用它。"""
    with connection(app_user_key) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN TRANSACTION;")
        except pyodbc.Error as exc:
            cursor.close()
            raise translate_db_error(exc) from exc

        try:
            yield conn
            cursor.execute("COMMIT TRANSACTION;")
        except Exception:
            try:
                cursor.execute("IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;")
                logger.info("事务已回滚")
            except pyodbc.Error:  # pragma: no cover - 连接已断开时无法回滚
                logger.warning("事务回滚失败，连接可能已断开", exc_info=True)
            raise
        finally:
            try:
                cursor.close()
            except pyodbc.Error:  # pragma: no cover
                pass


def check_health():
    """健康检查：确认数据库可连接、应用账号可用。"""
    with connection("AUTH") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        cursor.close()
    return True
