from fastapi import HTTPException, Request

from app.services.settings_service import SettingsService

# Default admin password. Stored in the settings DB once changed, so it can be
# rotated from the Settings page without editing code or .env.
DEFAULT_ADMIN_PASSWORD = "HKPC-AI-100"

_SESSION_KEY = "admin_authenticated"


def get_password() -> str:
    """Return the current admin password (DB override or the default)."""
    return SettingsService.get("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD


def verify_password(candidate: str) -> bool:
    """Return True if ``candidate`` matches the current admin password."""
    return bool(candidate) and candidate == get_password()


def set_password(new_password: str) -> None:
    """Persist a new admin password."""
    SettingsService.set("ADMIN_PASSWORD", new_password)


def is_authenticated(request: Request) -> bool:
    """Return True if the current session has been admin-authenticated."""
    return bool(request.session.get(_SESSION_KEY))


def require_admin(request: Request) -> None:
    """FastAPI dependency — raises 401 unless the session is admin-authenticated."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Admin authentication required")
