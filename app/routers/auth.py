import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models import User, PasswordResetToken
from app.schemas import (
    SignupRequest, LoginRequest, ChangePasswordRequest,
    ForgotPasswordRequest, ResetPasswordRequest, TokenResponse,
    UnauthenticatedChangePasswordRequest, SwitchRoleRequest,
    BecomeConsumerRequest, BecomeVendorRequest,
)
from app.deps import (
    hash_password, verify_password, create_access_token, get_current_user,
    get_user_public,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(body: SignupRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=body.name,
        email=email,
        hashed_password=hash_password(body.password),
        role=body.role, # Backward compatibility
        active_role=body.role,
    )
    user.set_roles([body.role])
    
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(user),
        roles=user.get_roles(),
        activeRole=user.active_role
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # --- Robust Migration for Old Users ---
    # We use getattr safely in case the columns don't exist in DB yet or are NULL
    try:
        raw_roles = getattr(user, "roles_json", None)
        roles = json.loads(raw_roles) if raw_roles else []
    except Exception:
        roles = []

    if not roles:
        # Fallback to the old 'role' field or default to consumer
        legacy_role = getattr(user, "role", None) or "consumer"
        roles = [legacy_role]
        try:
            user.set_roles(roles)
            user.active_role = legacy_role
            session.add(user)
            session.commit()
            session.refresh(user)
        except Exception:
            session.rollback()
            # If DB columns are missing, we still want to return a successful response
            # with these values in memory for the response schema
            user.roles_json = json.dumps(roles)
            user.active_role = legacy_role

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(user),
        roles=roles,
        activeRole=user.active_role
    )


@router.patch("/switch-role", response_model=TokenResponse)
def switch_role(
    body: SwitchRoleRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    roles = current_user.get_roles()
    if body.role not in roles:
        raise HTTPException(status_code=400, detail=f"User does not have role: {body.role}")
    
    current_user.active_role = body.role
    current_user.role = body.role  # Sync legacy field
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    token = create_access_token({"sub": str(current_user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(current_user),
        roles=current_user.get_roles(),
        activeRole=current_user.active_role
    )


@router.post("/become-consumer", response_model=TokenResponse)
def become_consumer(
    body: BecomeConsumerRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Consumer Onboarding Completion: saves profile data and grants consumer role."""
    if body.budget is not None:
        current_user.budget = body.budget
    if body.health_tags is not None:
        current_user.set_health_tags(body.health_tags)
    if body.preferences is not None:
        current_user.set_preferences(body.preferences)
    
    roles = current_user.get_roles()
    if "consumer" not in roles:
        roles.append("consumer")
        current_user.set_roles(roles)
    
    current_user.active_role = "consumer"
    current_user.role = "consumer"  # Sync legacy field
    current_user.consumer_onboarding_completed = True
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    token = create_access_token({"sub": str(current_user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(current_user),
        roles=current_user.get_roles(),
        activeRole=current_user.active_role
    )


@router.post("/become-vendor", response_model=TokenResponse)
@router.post("/become-farmer", response_model=TokenResponse)
def become_vendor(
    body: BecomeVendorRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Vendor Onboarding Completion: saves farm data and grants vendor role."""
    current_user.farm_name = body.farm_name
    current_user.farm_location = body.farm_location
    current_user.farm_type = body.farm_type
    
    roles = current_user.get_roles()
    if "vendor" not in roles:
        roles.append("vendor")
        current_user.set_roles(roles)
    
    current_user.active_role = "vendor"
    current_user.vendor_onboarding_completed = True
    # Backward compatibility field
    current_user.role = "vendor"
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    token = create_access_token({"sub": str(current_user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(current_user),
        roles=current_user.get_roles(),
        activeRole=current_user.active_role
    )


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Change password for the currently authenticated user."""
    if body.new_password != body.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")

    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    current_user.hashed_password = hash_password(body.new_password)
    session.add(current_user)
    session.commit()
    return {"message": "Password updated successfully"}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, session: Session = Depends(get_session)):
    """
    Reset password using only email.
    WARNING: This is highly insecure as it allows anyone to reset any user's password
    knowing only their email address. Recommended only for development/local testing.
    """
    email = body.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(body.new_password)
    session.add(user)
    session.commit()
    return {"message": "Password updated successfully. Please sign in."}




# ─── Deprecated OTP Flow (To be removed) ──────────────────────────────────────

@router.post("/forgot-password", include_in_schema=False)
def forgot_password(body: ForgotPasswordRequest, session: Session = Depends(get_session)):
    """
    Deprecated: The system now uses old password verification for resets.
    """
    return {"message": "Please use the reset-password endpoint with your current password."}


