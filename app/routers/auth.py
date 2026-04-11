import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, PasswordResetToken
from app.schemas import (
    SignupRequest, LoginRequest, ChangePasswordRequest,
    ForgotPasswordRequest, ResetPasswordRequest, TokenResponse,
)
from app.deps import (
    hash_password, verify_password, create_access_token, get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.email == body.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),   # ← now requires auth token
):
    """Change password for the currently authenticated user."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = hash_password(body.new_password)
    session.add(current_user)
    session.commit()
    return {"message": "Password updated successfully"}


# ─── Forgot Password Flow ────────────────────────────────────────────────────

@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, session: Session = Depends(get_session)):
    """
    Step 1 — Request a password reset OTP.
    In production, send this code via email (e.g. SendGrid / Brevo).
    For now the OTP is returned in the response body for development testing.
    """
    user = session.exec(select(User).where(User.email == body.email)).first()
    # Always return 200 to avoid email enumeration attacks
    if not user:
        return {"message": "If that email exists, a reset code has been sent."}

    # Invalidate any previous unused tokens for this email
    old_tokens = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.email == body.email,
            PasswordResetToken.used == False,
        )
    ).all()
    for t in old_tokens:
        t.used = True
        session.add(t)

    otp = secrets.token_hex(3).upper()  # 6-char hex OTP, e.g. "A1B2C3"
    reset_token = PasswordResetToken(
        email=body.email,
        token=otp,
        expires_at=datetime.utcnow() + timedelta(minutes=15),
    )
    session.add(reset_token)
    session.commit()

    # TODO: Send `otp` via email service (SendGrid / Brevo / etc.)
    # For dev: return OTP directly (remove this in production!)
    return {
        "message": "If that email exists, a reset code has been sent.",
        "dev_otp": otp,   # ← REMOVE IN PRODUCTION
    }


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, session: Session = Depends(get_session)):
    """
    Step 2 — Submit OTP + new password to complete the reset.
    """
    record = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.email == body.email,
            PasswordResetToken.token == body.token,
            PasswordResetToken.used == False,
        )
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    if datetime.utcnow() > record.expires_at:
        record.used = True
        session.add(record)
        session.commit()
        raise HTTPException(status_code=400, detail="Reset code has expired. Request a new one.")

    user = session.exec(select(User).where(User.email == body.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(body.new_password)
    record.used = True
    session.add(user)
    session.add(record)
    session.commit()
    return {"message": "Password reset successfully. Please sign in."}
