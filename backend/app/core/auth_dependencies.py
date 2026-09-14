"""
Step 17: FastAPI authorization dependency functions.

Dependency chain:
  get_current_user → decode JWT → load AppUser from DB → check is_active
  require_roles(*roles) → factory that wraps get_current_user + role check
  require_patient_owner(patient_id, user) → PATIENT must own the resource

Response code rules (no enumeration leaks):
  Missing / bad token     → 401
  Valid token, wrong role → 403
  Valid PATIENT token accessing another patient's resource → 404
  Missing consent         → 403 (ConsentRequiredException, existing behaviour)
"""
import logging
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_db
from app.models.app_user import AppUser, UserRole
from app.models.patient_consent import PrivacyAuditAction
from app.services.auth_service import auth_service
from sqlalchemy.orm import Session

logger = logging.getLogger("medikiosk.auth")

# Use HTTPBearer so FastAPI renders the Authorize button in OpenAPI docs.
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AppUser:
    """
    Dependency: resolve the authenticated AppUser from the Bearer JWT.

    Raises 401 if:
    - No Authorization header / not a Bearer token
    - Token is expired, malformed, or signed with wrong key
    - User record not found in DB (deleted after token issuance)
    - User account is inactive (is_active = False)
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = auth_service.decode_access_token(credentials.credentials)

    user_id_str: str | None = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(
            "auth.inactive_account_rejected",
            extra={
                "action": PrivacyAuditAction.INACTIVE_ACCOUNT_REJECTED.value,
                "user_id": user.id,
                "role": user.role.value,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AppUser | None:
    """
    Dependency: resolves the authenticated AppUser if credentials are provided.
    If no credentials are provided, returns None (allowing unauthenticated legacy callers).
    If credentials are provided but invalid, raises 401.
    """
    if credentials is None:
        return None
    return get_current_user(credentials=credentials, db=db)



def require_roles(*allowed_roles: UserRole) -> Callable:
    """
    Dependency factory: enforce that the current user has one of the allowed roles.

    Usage in route:
        @router.post("/endpoint")
        def endpoint(
            current_user: AppUser = Depends(require_roles(UserRole.DOCTOR, UserRole.STAFF))
        ): ...

    Raises 401 if not authenticated.
    Raises 403 if authenticated but role not in allowed_roles.
    """
    def _dependency(
        current_user: AppUser = Depends(get_current_user),
    ) -> AppUser:
        if current_user.role not in allowed_roles:
            logger.warning(
                "auth.role_denied",
                extra={
                    "action": PrivacyAuditAction.UNAUTHORIZED_ROLE_ACCESS.value,
                    "user_id": current_user.id,
                    "user_role": current_user.role.value,
                    "required_roles": [r.value for r in allowed_roles],
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{current_user.role.value}' is not authorized for this endpoint. "
                    f"Required: {[r.value for r in allowed_roles]}."
                ),
            )
        return current_user

    return _dependency


def require_patient_owner(patient_id: int, current_user: AppUser) -> None:
    """
    Enforce patient resource ownership.

    Rules:
    - PATIENT role: current_user.patient_id MUST match patient_id.
      Mismatch returns 404 (not 403) to avoid confirming the resource exists.
    - DOCTOR / STAFF / ADMIN: allowed through at the auth layer.
      Downstream consent and service-layer ownership checks still apply.

    Usage in route:
        def my_endpoint(
            patient_id: int,
            current_user: AppUser = Depends(get_current_user),
        ):
            require_patient_owner(patient_id, current_user)
            ...
    """
    if current_user.role == UserRole.PATIENT:
        if current_user.patient_id != patient_id:
            logger.warning(
                "auth.forbidden_resource_access",
                extra={
                    "action": PrivacyAuditAction.FORBIDDEN_RESOURCE_ACCESS.value,
                    "user_id": current_user.id,
                    "requested_patient_id": patient_id,
                    "user_patient_id": current_user.patient_id,
                },
            )
            # Return 404 to avoid confirming whether the patient exists.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {patient_id} not found",
            )
