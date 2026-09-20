import secrets
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import Settings, get_settings


@dataclass(frozen=True)
class HRIdentity:
    name: str


bearer = HTTPBearer(auto_error=False)


def require_hr_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    hr_user: str | None = Header(default=None, alias="X-HR-User"),
    settings: Settings = Depends(get_settings),
) -> HRIdentity:
    if not settings.hr_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HR mutation API authentication is not configured",
        )
    if (
        credentials is None
        or credentials.scheme.casefold() != "bearer"
        or not secrets.compare_digest(credentials.credentials, settings.hr_api_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid HR authorization is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not hr_user or not hr_user.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-HR-User is required for audit attribution",
        )
    return HRIdentity(name=hr_user.strip()[:255])
