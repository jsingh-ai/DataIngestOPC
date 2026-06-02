from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.security import verify_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def authenticate_user(username: str, password: str, settings: Settings) -> bool:
    if username != settings.admin_username:
        return False
    if settings.admin_password_hash:
        return verify_password(password, settings.admin_password_hash)
    return bool(settings.admin_password) and password == settings.admin_password


def create_access_token(username: str, settings: Settings) -> str:
    expires = datetime.now(UTC) + timedelta(minutes=settings.api_token_expire_minutes)
    payload = {"sub": username, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def build_token_response(form: OAuth2PasswordRequestForm, settings: Settings) -> TokenResponse:
    if not authenticate_user(form.username, form.password, settings):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(form.username, settings))


def get_current_user(
    token: str = Depends(oauth2_scheme), settings: Settings = Depends(get_settings)
) -> str:
    if settings.api_auth_disabled:
        return settings.admin_username
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    username = payload.get("sub")
    if not isinstance(username, str) or not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return username
