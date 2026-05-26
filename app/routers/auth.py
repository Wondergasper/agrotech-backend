import secrets
import json
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
    get_user_public, ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(tags=["Auth"])


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
        roles=[body.role]
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(user),
        roles=user.roles,
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
    # Handle cases where roles/active_role might be missing
    legacy_role = getattr(user, "role", None)

    # IMPORTANT: always use list() to create a NEW object so SQLAlchemy
    # detects the mutation and flushes it to Postgres.
    roles = list(user.get_roles())   # get_roles() is now hardened — always returns ≥1 item
    active_role = getattr(user, "active_role", None)

    changed = False

    if not active_role:
        active_role = legacy_role or roles[0]
        user.active_role = active_role
        changed = True

    # Ensure active_role is always a member of roles
    if user.active_role not in roles:
        user.active_role = roles[0]
        changed = True

    # Back-fill roles list if it was empty / None in the DB
    current_db_roles = list(user.roles) if user.roles else []
    if not current_db_roles:
        user.roles = list(roles)   # force new list object → SQLAlchemy dirty flag
        changed = True

    if changed:
        try:
            session.add(user)
            session.commit()
            session.refresh(user)
        except Exception:
            session.rollback()
            # Continue even if the write fails — the response values are already correct
            pass

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(user),
        roles=user.get_roles(),
        activeRole=user.active_role
    )


@router.patch("/switch-role", response_model=TokenResponse)
def switch_role(
    body: SwitchRoleRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    target_role = body.role.lower()
    if target_role == "farmer":
        target_role = "vendor"

    roles = list(current_user.get_roles())  # NEW list object for dirty tracking

    if target_role not in roles:
        # Auto-grant if the user has already completed onboarding for that role
        # This fixes the bug where a vendor who finished consumer onboarding is blocked.
        consumer_done = bool(getattr(current_user, "consumer_onboarding_completed", False))
        vendor_done = bool(getattr(current_user, "vendor_onboarding_completed", False))

        can_auto_grant = (
            (target_role == "consumer" and consumer_done)
            or (target_role == "vendor" and vendor_done)
        )

        if can_auto_grant:
            roles.append(target_role)
            current_user.roles = list(roles)  # force new list → SQLAlchemy detects change
        else:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": f"User does not have role: {target_role}",
                    "availableRoles": roles,
                    "requiresOnboarding": True,
                    "role": target_role,
                }
            )

    current_user.active_role = target_role
    current_user.role = target_role  # Sync legacy field
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

@router.get("/me", response_model=TokenResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the currently authenticated user's profile and a fresh token.
    The frontend uses this to sync role state after app launch or role switch.
    Aliased here under /auth so the frontend only needs one base URL.
    """
    token = create_access_token({"sub": str(current_user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(current_user),
        roles=current_user.get_roles(),
        activeRole=current_user.active_role,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(current_user: User = Depends(get_current_user)):
    """
    Issue a fresh token for the current user without requiring re-login.
    Useful when the frontend detects a near-expiry token.
    """
    token = create_access_token({"sub": str(current_user.id)})
    return TokenResponse(
        access_token=token,
        user=get_user_public(current_user),
        roles=current_user.get_roles(),
        activeRole=current_user.active_role,
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
    
    roles = list(current_user.get_roles())
    if "consumer" not in roles:
        roles.append("consumer")
        current_user.roles = roles
    
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
    
    roles = list(current_user.get_roles())
    if "vendor" not in roles:
        roles.append("vendor")
        current_user.roles = roles
    
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


