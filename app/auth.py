from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AdminUser

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


def verify_admin_password(plain: str, configured: str) -> bool:
    # Demo-friendly: plain compare when hash not used; also supports bcrypt hashes in env
    if configured.startswith("$2"):
        return pwd_context.verify(plain, configured)
    return plain == configured


def _admin_by_email(db: Session, email: str) -> AdminUser | None:
    normalized = email.strip().lower()
    return db.scalar(select(AdminUser).where(func.lower(AdminUser.email) == normalized))


def authenticate_admin(db: Session, email: str, password: str) -> str | None:
    """Return the admin email if credentials are valid."""
    user = _admin_by_email(db, email)
    if user and verify_admin_password(password, user.password_hash):
        return user.email

    settings = get_settings()
    if email.strip().lower() == settings.admin_email.lower() and verify_admin_password(
        password, settings.admin_password
    ):
        return settings.admin_email
    return None


def is_admin_email(db: Session, email: str) -> bool:
    settings = get_settings()
    if email.strip().lower() == settings.admin_email.lower():
        return True
    return _admin_by_email(db, email) is not None


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    settings = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if not email or not is_admin_email(db, email):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return email
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
