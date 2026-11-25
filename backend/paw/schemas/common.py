from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)


class Item[T](BaseModel):
    data: T


class Page[T](BaseModel):
    data: list[T]
    next_cursor: str | None = None
