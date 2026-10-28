from typing import Any, Dict, Optional
import logging

from app.database import SessionLocal
from app.models.setting import AppSetting

logger = logging.getLogger(__name__)


class SettingsService:
    """DB-backed runtime settings with fallback to defaults.

    Values set via the Settings page are stored in the ``app_settings`` table.
    When a key has no stored row, ``get`` returns the provided ``default``
    (normally the value loaded from .env via ``app.config.settings``).
    """

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Return the stored value for ``key``, or ``default`` if unset."""
        db = SessionLocal()
        try:
            row = db.query(AppSetting).filter(AppSetting.key == key).first()
            if row is not None:
                return cls._coerce(row.value, default)
            return default
        finally:
            db.close()

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Upsert a single setting. ``None`` is stored as an empty string."""
        db = SessionLocal()
        try:
            stored = "" if value is None else str(value)
            row = db.query(AppSetting).filter(AppSetting.key == key).first()
            if row:
                row.value = stored
            else:
                db.add(AppSetting(key=key, value=stored))
            db.commit()
        finally:
            db.close()

    @classmethod
    def set_many(cls, values: Dict[str, Any]) -> None:
        for key, value in values.items():
            cls.set(key, value)

    @staticmethod
    def _coerce(value: Any, default: Any) -> Any:
        """Coerce the stored string back to the type implied by ``default``."""
        if isinstance(default, bool):
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            try:
                return int(value)
            except (TypeError, ValueError):
                return default
        return value
