import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings


Role = Literal["read", "operator", "admin"]
ROLE_LEVELS: dict[str, int] = {"read": 1, "operator": 2, "admin": 3}
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    role: Role


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _decode_hs256_jwt(token: str, secret: str) -> dict[str, object]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token") from exc
    if header.get("alg") != "HS256":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unsupported token algorithm")
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    provided = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")
    exp = payload.get("exp")
    if exp is not None and datetime.fromtimestamp(float(exp), tz=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired bearer token")
    return payload


def require_role(required: Role):
    def dependency(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> Principal:
        if not settings.jwt_secret:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API authentication is not configured")
        if not credentials or credentials.scheme.lower() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
        payload = _decode_hs256_jwt(credentials.credentials, settings.jwt_secret)
        role = str(payload.get("role", "")).lower()
        if role not in ROLE_LEVELS:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="unknown role")
        if ROLE_LEVELS[role] < ROLE_LEVELS[required]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient role")
        return Principal(subject=str(payload.get("sub", "unknown")), role=role)  # type: ignore[arg-type]

    return dependency
