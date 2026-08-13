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
    refresh_token: str | None = Field(default=None, min_length=10)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)


class PageAccessSendRequest(BaseModel):
    purpose: str = Field(min_length=3, max_length=64)


class PageAccessVerifyRequest(BaseModel):
    purpose: str = Field(min_length=3, max_length=64)
    code: str = Field(pattern=r"^\d{6}$")


class PageAccessConsumeRequest(BaseModel):
    purpose: str = Field(min_length=3, max_length=64)
    proof: str = Field(min_length=32, max_length=256)


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


class MenuUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    path: str | None = Field(default=None, max_length=255)
    parent_id: int | None = None
    component: str | None = Field(default=None, max_length=255)
    icon: str | None = Field(default=None, max_length=64)
    sort_order: int | None = None
    menu_type: str | None = None
    status: str | None = None
    permission_code: str | None = Field(default=None, max_length=128)
    remark: str | None = Field(default=None, max_length=1000)


class OrgUnitCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    parent_id: int | None = None
    sort_order: int = 0
    status: str = "ACTIVE"
    remark: str | None = None


class OrgUnitUpdateRequest(BaseModel):
    name: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None
    status: str | None = None
    remark: str | None = None


class DictTypeCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    status: str = "ACTIVE"
    remark: str | None = None


class DictItemCreateRequest(BaseModel):
    item_label: str = Field(min_length=1, max_length=128)
    item_value: str = Field(min_length=1, max_length=128)
    sort_order: int = 0
    status: str = "ACTIVE"
    remark: str | None = None


class SystemParamUpsertRequest(BaseModel):
    param_key: str = Field(min_length=1, max_length=128)
    param_value: str
    value_type: str = "STRING"
    is_secret: bool = False
    remark: str | None = None
