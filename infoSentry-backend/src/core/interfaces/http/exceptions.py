"""HTTP exception handlers.

提供统一的异常处理机制，将领域异常转换为标准 HTTP 响应。
各模块的异常类通过定义 http_status_code 和 error_code 类属性来自定义响应。
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from loguru import logger

from src.core.domain.exceptions import DomainException


class BizException(Exception):
    """Business logic exception."""

    def __init__(
        self,
        message: str = "业务逻辑错误",
        code: int = 400,
        error_code: str = "BIZ_ERROR",
    ):
        self.message = message
        self.code = code
        self.error_code = error_code
        super().__init__(message)


async def biz_exception_handler(_request: Request, exc: BizException) -> JSONResponse:
    """Handle business exceptions."""
    return JSONResponse(
        status_code=exc.code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
            }
        },
    )


async def domain_exception_handler(
    _request: Request, exc: DomainException
) -> JSONResponse:
    """Handle domain exceptions.

    通过读取异常类的 http_status_code 和 error_code 类属性来确定响应。
    这样各模块可以定义自己的异常类而不需要修改 core 层代码。
    """
    # 从异常类获取 HTTP 状态码和错误代码
    status_code = getattr(exc, "http_status_code", 400)
    error_code = getattr(exc, "error_code", "DOMAIN_ERROR")

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": exc.message,
            }
        },
    )


async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
            }
        },
    )
