from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict

from app.config import settings
from app.services.settings_service import SettingsService
from app.services.admin_auth import require_admin, verify_password, set_password

# Every endpoint in this router requires an authenticated admin session.
router = APIRouter(dependencies=[Depends(require_admin)])

# Keys that may be written through the settings page. Anything else is rejected.
EDITABLE_KEYS = {
    "YOUTUBE_API_KEY",
    "LLM_PROVIDER",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_MODEL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "AUTO_FETCH_TRANSCRIPT",
    "AUTO_SUMMARIZE",
    "MAX_VIDEOS_PER_CHANNEL",
    "CRAWL_DELAY_SECONDS",
}


def _default_provider() -> str:
    """Derive the LLM provider from legacy .env flags when none is stored."""
    if settings.USE_OPENROUTER and settings.OPENROUTER_API_KEY:
        return "openrouter"
    if settings.USE_DEEPSEEK and settings.DEEPSEEK_API_KEY:
        return "deepseek"
    return "openai"


def _get_payload() -> Dict[str, Any]:
    return {
        "youtube_api_key": SettingsService.get("YOUTUBE_API_KEY", settings.YOUTUBE_API_KEY),
        "llm_provider": SettingsService.get("LLM_PROVIDER") or _default_provider(),
        "openrouter_api_key": SettingsService.get("OPENROUTER_API_KEY", settings.OPENROUTER_API_KEY),
        "openrouter_base_url": SettingsService.get("OPENROUTER_BASE_URL", settings.OPENROUTER_BASE_URL) or settings.OPENROUTER_BASE_URL,
        "openrouter_model": SettingsService.get("OPENROUTER_MODEL", settings.OPENROUTER_MODEL) or settings.OPENROUTER_MODEL,
        "deepseek_api_key": SettingsService.get("DEEPSEEK_API_KEY", settings.DEEPSEEK_API_KEY),
        "deepseek_base_url": SettingsService.get("DEEPSEEK_BASE_URL", settings.DEEPSEEK_BASE_URL) or settings.DEEPSEEK_BASE_URL,
        "deepseek_model": SettingsService.get("DEEPSEEK_MODEL", settings.DEEPSEEK_MODEL) or settings.DEEPSEEK_MODEL,
        "openai_api_key": SettingsService.get("OPENAI_API_KEY", settings.OPENAI_API_KEY),
        "openai_model": SettingsService.get("OPENAI_MODEL", settings.OPENAI_MODEL) or settings.OPENAI_MODEL,
        "auto_fetch_transcript": SettingsService.get("AUTO_FETCH_TRANSCRIPT", settings.AUTO_FETCH_TRANSCRIPT),
        "auto_summarize": SettingsService.get("AUTO_SUMMARIZE", settings.AUTO_SUMMARIZE),
        "max_videos_per_channel": SettingsService.get("MAX_VIDEOS_PER_CHANNEL", settings.MAX_VIDEOS_PER_CHANNEL),
        "crawl_delay_seconds": SettingsService.get("CRAWL_DELAY_SECONDS", settings.CRAWL_DELAY_SECONDS),
    }


@router.get("")
def get_settings():
    """Return all user-editable settings (resolved against .env defaults)."""
    return _get_payload()


@router.post("")
def update_settings(payload: Dict[str, Any]):
    """Persist user-editable settings. Unknown keys are rejected."""
    invalid = [k for k in payload if k not in EDITABLE_KEYS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown setting(s): {', '.join(invalid)}")

    SettingsService.set_many(payload)
    return _get_payload()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: ChangePasswordRequest):
    """Rotate the admin password (requires the current password)."""
    if not verify_password(body.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_password = body.new_password.strip()
    if len(new_password) < 4:
        raise HTTPException(status_code=400, detail="New password must be at least 4 characters")

    set_password(new_password)
    return {"message": "Password updated"}


@router.get("/youtube-quota")
def youtube_quota_stats():
    """Today's estimated YouTube Data API usage (PT quota day) and crawl fetch stats."""
    from app.services.youtube_quota_service import get_today_summary

    return get_today_summary()


@router.get("/catalog-stats")
def catalog_stats():
    """Summary of categories / channels / videos fetched (catalog content stats)."""
    from app.services.catalog_stats_service import get_catalog_stats

    return get_catalog_stats()

