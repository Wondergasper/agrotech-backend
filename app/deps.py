from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from app.database import get_session
from app.models import User
from app.schemas import UserPublic
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_public(user: User) -> UserPublic:
    """Helper to convert User model to UserPublic schema consistently."""
    data = user.model_dump()
    
    # Safe fallbacks for new fields in case DB columns are missing or NULL
    data["roles"] = user.get_roles() if hasattr(user, "get_roles") else [getattr(user, "role", "consumer") or "consumer"]
    data["activeRole"] = getattr(user, "active_role", None) or getattr(user, "role", "consumer") or "consumer"
    
    # Ensure boolean flags are actually bool, not None
    data["consumerOnboardingCompleted"] = bool(getattr(user, "consumer_onboarding_completed", False))
    data["vendorOnboardingCompleted"] = bool(getattr(user, "vendor_onboarding_completed", False))
    
    # Handle JSON lists
    data["health_tags"] = user.get_health_tags() if hasattr(user, "get_health_tags") else []
    data["preferences"] = user.get_preferences() if hasattr(user, "get_preferences") else []
    
    return UserPublic(**data)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        user = session.get(User, int(user_id))
    except (ValueError, TypeError):
        raise credentials_exception

    if user is None:
        raise credentials_exception
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    session: Session = Depends(get_session),
) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            return None
        return session.get(User, int(user_id))
    except (JWTError, ValueError, TypeError):
        return None


def require_vendor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.active_role != "vendor":
        raise HTTPException(
            status_code=403, 
            detail={
                "message": "User does not have role: vendor",
                "availableRoles": current_user.get_roles(),
                "requiresOnboarding": not current_user.vendor_onboarding_completed,
                "role": "vendor"
            }
        )
    return current_user


def require_consumer(current_user: User = Depends(get_current_user)) -> User:
    if current_user.active_role != "consumer":
        raise HTTPException(
            status_code=403, 
            detail={
                "message": "User does not have role: consumer",
                "availableRoles": current_user.get_roles(),
                "requiresOnboarding": not current_user.consumer_onboarding_completed,
                "role": "consumer"
            }
        )
    return current_user
