import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

try:
    from . import models
except ImportError as exc:  # pragma: no cover
    if "attempted relative import with no known parent package" not in str(exc):
        raise
    import models

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-this")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
DEFAULT_GITHUB_SCOPE = "read:user"


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expires = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expires}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if isinstance(value, str) and value.strip():
        return value.strip()

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Server misconfiguration: {name} is not set.",
    )


def github_client_id() -> str:
    return _required_env("GITHUB_CLIENT_ID")


def github_client_secret() -> str:
    return _required_env("GITHUB_CLIENT_SECRET")


def build_github_oauth_url(
    *,
    redirect_uri: str,
    state: str | None = None,
    scope: str = DEFAULT_GITHUB_SCOPE,
) -> str:
    params = {
        "client_id": github_client_id(),
        "redirect_uri": redirect_uri,
        "scope": scope,
    }
    if state:
        params["state"] = state

    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_oauth_code_for_token(*, code: str, redirect_uri: str) -> str:
    payload = {
        "client_id": github_client_id(),
        "client_secret": github_client_secret(),
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(GITHUB_TOKEN_URL, data=payload, headers=headers)

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub token endpoint returned an invalid response.",
        ) from exc

    if response.status_code != status.HTTP_200_OK:
        description = data.get("error_description") if isinstance(data, dict) else None
        detail = description if isinstance(description, str) and description else "OAuth exchange failed."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    if isinstance(data, dict) and data.get("error"):
        description = data.get("error_description")
        detail = description if isinstance(description, str) and description else "OAuth exchange failed."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub OAuth response did not include an access token.",
        )
    return token.strip()


async def fetch_github_user(token: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get(GITHUB_USER_URL, headers=headers)

    if response.status_code != status.HTTP_200_OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    payload = response.json()
    if "id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to load GitHub user profile from token.",
        )
    return payload


def upsert_user_from_github(db: Session, github_user: dict[str, Any]) -> "models.User":
    github_id = str(github_user["id"])
    raw_login = github_user.get("login")
    has_login = isinstance(raw_login, str) and bool(raw_login.strip())
    resolved_username = raw_login.strip() if has_login else f"github-id-{github_id}"
    avatar_url = github_user.get("avatar_url") or ""

    user = db.query(models.User).filter(models.User.github_id == github_id).first()
    if user is None:
        user = models.User(
            github_id=github_id,
            username=resolved_username,
            avatar_url=avatar_url,
        )
    else:
        # Preserve an existing username when GitHub omits "login".
        if has_login:
            user.username = resolved_username
        user.avatar_url = avatar_url

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def user_from_jwt(db: Session, token: str) -> "models.User | None":
    payload = decode_access_token(token)
    if not payload:
        return None

    subject = payload.get("sub")
    if not subject:
        return None

    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None

    return db.query(models.User).filter(models.User.id == user_id).first()


async def authenticate_token(db: Session, token: str) -> "models.User":
    user = user_from_jwt(db, token)
    if user:
        return user

    github_user = await fetch_github_user(token)
    user = upsert_user_from_github(db, github_user)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )
    return user
