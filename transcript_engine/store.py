"""
SQLite-backed persistent cache and state store for transcript resilience.

Tables:
- transcripts: cached successful + negative results
- failures: circuit breaker state and error history
- throttle_state: persisted rate governor values
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class TranscriptStore:
    """Persistent storage for transcripts, failures, and throttle state."""

    def __init__(self, db_path: str = "data/transcript_cache.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Main transcript cache
        c.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                video_id TEXT NOT NULL,
                lang TEXT NOT NULL,
                source_tier TEXT NOT NULL,
                json TEXT NOT NULL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (video_id, lang)
            )
        """)

        # Circuit breaker + failure tracking
        c.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                video_id TEXT NOT NULL,
                error_class TEXT NOT NULL,
                tier TEXT NOT NULL,
                ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cooldown_until TIMESTAMP,
                consecutive_blocks INTEGER DEFAULT 0
            )
        """)

        # Rate governor state (token bucket, backoff, etc.)
        c.execute("""
            CREATE TABLE IF NOT EXISTS throttle_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def get_transcript(self, video_id: str, lang: str = "en") -> Optional[Dict]:
        """Return cached transcript or None."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT json, source_tier, fetched_at FROM transcripts
            WHERE video_id = ? AND lang = ?
        """, (video_id, lang))
        row = c.fetchone()
        conn.close()

        if row:
            data = json.loads(row[0])
            data["_meta"] = {
                "source_tier": row[1],
                "cached_at": row[2]
            }
            return data
        return None

    def save_transcript(self, video_id: str, lang: str, source_tier: str, data: Dict):
        """Persist a successful transcript fetch."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO transcripts (video_id, lang, source_tier, json, fetched_at)
            VALUES (?, ?, ?, ?, ?)
        """, (video_id, lang, source_tier, json.dumps(data), datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    def save_negative(self, video_id: str, lang: str, error_class: str, tier: str, ttl_days: int = 7):
        """Cache a negative result (no transcript) with TTL."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        expiry = (datetime.utcnow() + timedelta(days=ttl_days)).isoformat()
        c.execute("""
            INSERT OR REPLACE INTO failures (video_id, error_class, tier, ts, cooldown_until)
            VALUES (?, ?, ?, ?, ?)
        """, (video_id, error_class, tier, datetime.utcnow().isoformat(), expiry))
        conn.commit()
        conn.close()

    def is_circuit_open(self, tier: str) -> bool:
        """Check if circuit breaker for this tier is currently open."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT cooldown_until FROM failures
            WHERE tier = ? AND error_class = 'BLOCKED'
            ORDER BY ts DESC LIMIT 1
        """, (tier,))
        row = c.fetchone()
        conn.close()

        if row and row[0]:
            return datetime.fromisoformat(row[0]) > datetime.utcnow()
        return False

    def record_block(self, tier: str, consecutive: int = 1, cooldown_minutes: int = 45):
        """Record a block event and open the circuit breaker."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        cooldown = (datetime.utcnow() + timedelta(minutes=cooldown_minutes)).isoformat()
        c.execute("""
            INSERT INTO failures (video_id, error_class, tier, ts, cooldown_until, consecutive_blocks)
            VALUES ('__GLOBAL__', 'BLOCKED', ?, ?, ?, ?)
        """, (tier, datetime.utcnow().isoformat(), cooldown, consecutive))
        conn.commit()
        conn.close()

    def get_throttle_value(self, key: str, default: Any = None) -> Any:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT value FROM throttle_state WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()
        return json.loads(row[0]) if row else default

    def set_throttle_value(self, key: str, value: Any):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO throttle_state (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, json.dumps(value), datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    def get_status(self) -> Dict:
        """Return current breaker and queue state for CLI/status reporting."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT tier, cooldown_until, consecutive_blocks FROM failures
            WHERE error_class = 'BLOCKED' AND cooldown_until > ?
        """, (datetime.utcnow().isoformat(),))
        breakers = c.fetchall()
        conn.close()

        return {
            "open_breakers": [
                {"tier": b[0], "cooldown_until": b[1], "consecutive": b[2]}
                for b in breakers
            ],
            "cache_size": self._count_transcripts()
        }

    def _count_transcripts(self) -> int:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM transcripts")
        count = c.fetchone()[0]
        conn.close()
        return count