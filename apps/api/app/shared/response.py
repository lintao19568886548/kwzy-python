from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T | None = None


class PageMeta(BaseModel):
    total: int = 0
    page: int = 1
    page_size: int = 20


class PageResult(BaseModel, Generic[T]):
    total: int = 0
    page: int = 1
    page_size: int = 20
    items: list[T] = Field(default_factory=list)


def ok(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {"code": "OK", "message": message, "data": data}
