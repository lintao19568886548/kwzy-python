from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings

UTC = timezone.utc
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_BYTES = 72
_COMMON_PASSWORD_FRAGMENTS = ("password", "qwerty", "123456", "admin123")


def password_policy_violation(password: str, *, username: str = "") -> str | None:
    """Return a user-safe reason when a newly assigned password is too weak."""

    if len(password) < PASSWORD_MIN_LENGTH:
        return f"密码至少 {PASSWORD_MIN_LENGTH} 位"
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return f"密码 UTF-8 编码后不能超过 {PASSWORD_MAX_BYTES} 字节"
    categories = sum(
        (
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        )
    )
    if categories < 3:
        return "密码须包含大写字母、小写字母、数字、特殊字符中的至少三类"
    lowered = password.casefold()
    normalized_username = username.strip().casefold()
    if len(normalized_username) >= 3 and normalized_username in lowered:
        return "密码不得包含完整账号名"
    if any(fragment in lowered for fragment in _COMMON_PASSWORD_FRAGMENTS):
        return "密码包含常见弱口令片段"
    return None


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


class TokenError(Exception):
    pass


def safe_decode(token: str) -> dict[str, Any]:
    try:
        return decode_access_token(token)
    except InvalidTokenError as exc:
        raise TokenError("invalid token") from exc
