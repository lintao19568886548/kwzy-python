from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    tenant_code: str | None = Field(default=None, min_length=1, max_length=64)


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class UserInfo(BaseModel):
    id: int
    tenant_id: int
    username: str
    real_name: str = ""
    phone: str | None = None
    permissions: list[str] = Field(default_factory=list)
    park_ids: list[int] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6)
    real_name: str = ""
    phone: str | None = None
    role_ids: list[int] = Field(default_factory=list)
    park_ids: list[int] = Field(default_factory=list)
    all_parks: bool = False


class UserUpdateRequest(BaseModel):
    real_name: str | None = None
    phone: str | None = None
    status: str | None = None
    role_ids: list[int] | None = None
    park_ids: list[int] | None = None
    all_parks: bool | None = None
    password: str | None = Field(default=None, min_length=6)


class RoleCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    remark: str | None = None
    all_parks: bool = False
    permission_codes: list[str] = Field(default_factory=list)
    park_ids: list[int] = Field(default_factory=list)
    menu_ids: list[int] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    name: str | None = None
    remark: str | None = None
    status: str | None = None
    all_parks: bool | None = None
    permission_codes: list[str] | None = None
    park_ids: list[int] | None = None
    menu_ids: list[int] | None = None


class MenuCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    path: str = ""
    parent_id: int | None = None
    component: str | None = None
    icon: str | None = None
    sort_order: int = 0
    menu_type: str = "MENU"
    permission_code: str | None = None
