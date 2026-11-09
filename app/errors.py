"""统一错误类型与错误码。

设计约定：
1. 每个可预期的失败都对应一个稳定错误码，前端依据错误码决定提示方式；
2. 前端只会看到面向用户的简明提示，SQL 语句、表名、连接信息、异常堆栈一律不返回；
3. 真实原因通过 ``log_detail`` 交给日志层，由后端保留用于定位。
"""


class AppError(Exception):
    """所有业务异常的基类。"""

    code = "INTERNAL_ERROR"
    http_status = 500
    default_message = "系统暂时无法完成操作，请稍后再试"

    def __init__(self, message=None, *, fields=None, log_detail=None):
        self.message = message or self.default_message
        self.fields = fields or {}
        self.log_detail = log_detail
        super().__init__(self.message)

    def to_payload(self):
        payload = {"code": self.code, "message": self.message}
        if self.fields:
            payload["fields"] = self.fields
        return payload


class ValidationError(AppError):
    """参数缺失、格式错误或超出允许范围。"""

    code = "VALIDATION_ERROR"
    http_status = 400
    default_message = "提交的内容不符合要求，请检查后重试"


class AuthRequiredError(AppError):
    """未登录或登录状态已失效。"""

    code = "AUTH_REQUIRED"
    http_status = 401
    default_message = "请先登录后再操作"


class AuthFailedError(AppError):
    """账号或口令不正确。"""

    code = "AUTH_FAILED"
    http_status = 401
    default_message = "用户名或密码不正确"


class ForbiddenError(AppError):
    """已登录，但当前角色没有该业务操作的权限。"""

    code = "FORBIDDEN"
    http_status = 403
    default_message = "当前角色无权执行该操作"


class NotFoundError(AppError):
    """请求的数据不存在。"""

    code = "NOT_FOUND"
    http_status = 404
    default_message = "没有找到对应的数据"


class BusinessRuleError(AppError):
    """业务规则不满足，例如库存不足、订单状态不允许该操作。"""

    code = "BUSINESS_RULE_VIOLATION"
    http_status = 409
    default_message = "操作不满足业务规则"


class ConstraintConflictError(AppError):
    """数据库约束冲突，例如唯一键重复、外码不存在、检查约束不通过。"""

    code = "CONSTRAINT_CONFLICT"
    http_status = 409
    default_message = "数据与数据库约束冲突，请检查输入内容"


class DatabaseUnavailableError(AppError):
    """数据库连接失败、实例不可用或网络中断。"""

    code = "DATABASE_UNAVAILABLE"
    http_status = 503
    default_message = "系统暂时无法完成操作，请稍后再试"


class ConfigurationError(AppError):
    """运行配置不完整，例如未建应用账号或连接参数缺失。"""

    code = "CONFIGURATION_ERROR"
    http_status = 500
    default_message = "系统配置不完整，请联系管理员"
