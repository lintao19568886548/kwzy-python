import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import get_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "APP_ERROR",
        status_code: int = 400,
        data=None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.data = data
        super().__init__(message)


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "data": exc.data},
    )


async def validation_error_handler(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """将 FastAPI/Pydantic 参数错误转换为统一 envelope。"""

    errors = [
        {
            "location": [str(item) for item in error.get("loc", ())],
            "message": str(error.get("msg", "invalid value")),
            "type": str(error.get("type", "validation_error")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "data": {"errors": errors},
        },
    )


async def internal_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """记录未知异常并返回不泄露内部信息的 500 envelope。"""

    logger.exception(
        "未处理的服务器异常",
        exc_info=exc,
        extra={
            "request_id": get_request_id(),
            "business_module": "api",
            "action": "request",
            "code": "INTERNAL_ERROR",
        },
    )
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "服务器内部错误", "data": None},
    )


def http_error(status_code: int, message: str, code: str = "HTTP_ERROR") -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
