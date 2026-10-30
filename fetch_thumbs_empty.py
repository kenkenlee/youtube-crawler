#!/usr/bin/env python3
"""Fill empty channel thumbnail_url only, with per-channel timeout."""
import logging, signal
from contextlib import contextmanager
from app.database import SessionLocal
from app.models.channel import Channel
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fetch_empty")

class Timeout(Exception):
    pass

@contextmanager
def time_limit(seconds):
    def handler(signum, frame):
        raise Timeout()
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

def fetch(channel_id, timeout=25):
    url = f"https://www.youtube.com/channel/{channel_id}"
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": True, "socket_timeout": 20}
    with time_limit(timeout):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False) or {}
    if info.get("thumbnails"):
        return info["thumbnails"][-1].get("url") or ""
    return info.get("thumbnail") or ""

def main():
    db = SessionLocal()
    try:
        channels = db.query(Channel).all()
        empty = [ch for ch in channels if not (ch.thumbnail_url or "").strip()]
        logger.info("total=%s empty=%s", len(channels), len(empty))
        ok = fail = 0
        for ch in empty:
            cid = ch.youtube_channel_id
            if not cid:
                logger.info("skip %s no id", ch.channel_name)
                continue
            try:
                thumb = fetch(cid)
                if not thumb:
                    thumb = f"https://yt3.ggpht.com/ytc/{cid}=s88-c-k-c0x00ffffff-no-rj"
                    logger.warning("fallback %s", ch.channel_name)
                ch.thumbnail_url = thumb
                ok += 1
                logger.info("ok %s", ch.channel_name)
            except Exception as e:
                fail += 1
                logger.error("fail %s: %s", ch.channel_name, e)
                try:
                    ch.thumbnail_url = f"https://yt3.ggpht.com/ytc/{cid}=s88-c-k-c0x00ffffff-no-rj"
                except Exception:
                    pass
            if (ok + fail) % 10 == 0:
                db.commit()
        db.commit()
        empty2 = sum(1 for ch in db.query(Channel).all() if not (ch.thumbnail_url or "").strip())
        logger.info("done ok=%s fail=%s empty_left=%s", ok, fail, empty2)
    finally:
        db.close()

if __name__ == "__main__":
    main()
