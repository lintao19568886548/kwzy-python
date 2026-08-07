from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    tenant_code: str | None = Field(default=None, min_length=1, max_length=64)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserInfo(BaseModel):
    id: int
    tenant_id: int
    username: str
    real_name: str = ""
    phone: str | None = None
    permissions: list[str] = Field(default_factory=list)
    park_ids: list[int] = Field(default_factory=list)
