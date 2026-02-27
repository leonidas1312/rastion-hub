import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

try:
    from . import models
except ImportError:  # pragma: no cover
    import models

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-this")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
GITHUB_USER_URL = "https://api.github.com/user"


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
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token.",
        )
    return user
