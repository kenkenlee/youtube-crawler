import os

from fastapi import HTTPException, Request

from app.services.settings_service import SettingsService

# No hardcoded production password. Set ADMIN_PASSWORD in the environment for
# first login (or change it from the Settings page after authenticating).
# Historical default was removed from the public tree for security.
_SESSION_KEY = "admin_authenticated"


def get_password() -> str:
    """Return the current admin password (DB override or ADMIN_PASSWORD env)."""
    stored = SettingsService.get("ADMIN_PASSWORD")
    if stored:
        return stored
    return os.environ.get("ADMIN_PASSWORD", "").strip()


def verify_password(candidate: str) -> bool:
    """Return True if ``candidate`` matches the current admin password."""
    expected = get_password()
    if not expected:
        return False
    return bool(candidate) and candidate == expected


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
