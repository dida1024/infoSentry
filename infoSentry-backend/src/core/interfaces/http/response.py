"""Standard API response models."""

from typing import Any, Self, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiResponse[T](BaseModel):
    """Standard API response model."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    code: int = 200
    message: str = "Operation successful"
    data: T | None = None
    meta: dict | None = None

    @classmethod
    def success(
        cls,
        data: T = None,
        message: str = "Operation successful",
        code: int = 200,
        meta: dict | None = None,
    ) -> "ApiResponse[T]":
        return cls(code=code, message=message, data=data, meta=meta)

    @classmethod
    def error(
        cls,
        message: str = "操作失败",
        code: int = 400,
        data: Any = None,
    ) -> "ApiResponse[T]":
        if isinstance(data, Exception):
            data = {"error_type": type(data).__name__, "error_detail": str(data)}
        if isinstance(message, Exception):
            message = str(message)
        return cls(code=code, message=message, data=data)


class PaginatedResponse[T](ApiResponse[list[T]]):
    """Paginated API response model."""

    data: list[T] | None = None
    meta: dict = {"total": 0, "page": 1, "page_size": 10}

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int = 1,
        page_size: int = 10,
    ) -> Self:
        return cls(
            data=items,
            meta={
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            },
        )


class CursorPaginatedResponse[T](ApiResponse[list[T]]):
    """Cursor-based paginated response for infinite scroll."""

    data: list[T] | None = None
    next_cursor: str | None = None
    has_more: bool = False

    @classmethod
    def create(
        cls,
        items: list[T],
        next_cursor: str | None = None,
        has_more: bool = False,
    ) -> Self:
        return cls(data=items, next_cursor=next_cursor, has_more=has_more)


class ErrorResponse(BaseModel):
    """Error response model matching API spec."""

    error: dict

    @classmethod
    def create(
        cls,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> "ErrorResponse":
        error_dict = {"code": code, "message": message}
        if details:
            error_dict["details"] = details
        return cls(error=error_dict)
