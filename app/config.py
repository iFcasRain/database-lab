"""应用配置。

所有可变项都从环境变量读取；同目录下的 ``.env`` 文件可以覆盖默认值，
避免把服务器地址、账号和口令写死在页面或业务代码里。
"""

import os

# database-lab 根目录（app 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env_file(path):
    """极简 .env 读取：仅支持 KEY=VALUE，已存在的环境变量优先。"""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_env_file(os.path.join(BASE_DIR, ".env"))


def _env(key, default=""):
    return os.environ.get(key, default)


def _env_int(key, default):
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key, default):
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # ---------- Web 应用 ----------
    SECRET_KEY = _env("APP_SECRET_KEY", "dev-only-secret-change-me")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = _env_int("APP_SESSION_SECONDS", 3600)
    JSON_AS_ASCII = False
    LOG_DIR = _env("APP_LOG_DIR", os.path.join(BASE_DIR, "logs"))
    LOG_LEVEL = _env("APP_LOG_LEVEL", "INFO").upper()

    # ---------- SQL Server 连接 ----------
    DB_DRIVER = _env("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    DB_SERVER = _env("DB_SERVER", r".\SQLEXPRESS")
    DB_DATABASE = _env("DB_DATABASE", "ConvenienceStoreDB")
    DB_TRUSTED_CONNECTION = _env_bool("DB_TRUSTED_CONNECTION", True)
    DB_USER = _env("DB_USER", "")
    DB_PASSWORD = _env("DB_PASSWORD", "")
    DB_ENCRYPT = _env("DB_ENCRYPT", "no")
    DB_TRUST_SERVER_CERTIFICATE = _env("DB_TRUST_SERVER_CERTIFICATE", "yes")
    DB_TIMEOUT = _env_int("DB_TIMEOUT", 5)

    # ---------- 按角色收敛数据库权限 ----------
    # 应用登录只负责建立连接；建立后立即 EXECUTE AS USER 切换到下表的应用账号，
    # 使页面层、业务层的权限判断与数据库实际授权保持一致。
    DB_APP_USER_AUTH = _env("DB_APP_USER_AUTH", "app_auth")
    DB_APP_USER_CUSTOMER = _env("DB_APP_USER_CUSTOMER", "app_customer")
    DB_APP_USER_CASHIER = _env("DB_APP_USER_CASHIER", "app_cashier")
    DB_APP_USER_INVENTORY = _env("DB_APP_USER_INVENTORY", "app_inventory")
    DB_APP_USER_MANAGER = _env("DB_APP_USER_MANAGER", "app_manager")

    # ---------- 业务参数 ----------
    # 积分规则：每消费 1 元获得 1 分；每 10 分抵扣 1 元。
    POINTS_PER_YUAN = _env_int("POINTS_PER_YUAN", 1)
    POINTS_PER_DISCOUNT_YUAN = _env_int("POINTS_PER_DISCOUNT_YUAN", 10)


def build_app_user_map(config):
    """把“登录身份”映射到迁移脚本创建的数据库应用账号。"""
    return {
        "AUTH": config["DB_APP_USER_AUTH"],
        "CUSTOMER": config["DB_APP_USER_CUSTOMER"],
        "CASHIER": config["DB_APP_USER_CASHIER"],
        "INVENTORY": config["DB_APP_USER_INVENTORY"],
        "MANAGER": config["DB_APP_USER_MANAGER"],
    }
