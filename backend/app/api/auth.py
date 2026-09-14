"""
Step 17: Authentication API endpoints.

Endpoints:
  POST /api/auth/login    — public, issues JWT
  GET  /api/auth/me       — requires valid JWT, returns current user identity
  POST /api/auth/register — requires ADMIN role, creates a new user account

Design invariants:
  - password_hash is NEVER present in any response body.
  - TokenResponse payload contains only: access_token, token_type, expires_in_seconds, role.
  - Registration is ADMIN-only; no public sign-up is exposed.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.core.rate_limiter import rate_limit_login
from app.models.app_user import AppUser, UserRole
from app.schemas.auth import CurrentUserResponse, LoginRequest, TokenResponse, UserCreateRequest
from app.services.auth_service import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_login)],
    summary="Authenticate and obtain a JWT access token",
    description=(
        "Submit email and password. "
        "Returns a signed JWT bearer token valid for the configured duration. "
        "Same error response for unknown email and wrong password (no oracle). "
        "Protected by application-level sliding-window rate limiting."
    ),
)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return auth_service.login(db, request)



@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Return the authenticated user's identity",
    description=(
        "Returns id, email, role, patient_id (for PATIENT accounts), and is_active. "
        "password_hash is never included in the response."
    ),
)
def get_me(current_user: AppUser = Depends(get_current_user)) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        patient_id=current_user.patient_id,
        is_active=current_user.is_active,
    )


@router.post(
    "/register",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new application user (ADMIN only)",
    description=(
        "Create a new user account. Requires ADMIN role. "
        "PATIENT accounts must include patient_id. "
        "DOCTOR/STAFF/ADMIN accounts must NOT include patient_id. "
        "password_hash is never returned."
    ),
)
def register(
    request: UserCreateRequest,
    db: Session = Depends(get_db),
    _current_user: AppUser = Depends(require_roles(UserRole.ADMIN)),
) -> CurrentUserResponse:
    created = auth_service.register_user(db, request)
    return CurrentUserResponse(
        id=created.id,
        email=created.email,
        role=created.role,
        patient_id=created.patient_id,
        is_active=created.is_active,
    )
