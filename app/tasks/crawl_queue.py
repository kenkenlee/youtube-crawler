"""Global single-worker crawl queue with priority.

Ensures at most one crawl session runs at a time so YouTube API quota
is not exhausted by parallel recurring runs.

Lower priority number = runs sooner:
  0 = news slots
  1 = daily / manual / default
  2 = weekly
"""
from __future__ import annotations

import itertools
import logging
import queue
import threading
from typing import Optional, Set

logger = logging.getLogger(__name__)

_queue: "queue.PriorityQueue[tuple]" = queue.PriorityQueue()
_seq = itertools.count()
_queued_ids: Set[int] = set()
_queued_lock = threading.Lock()
_worker_started = False
_worker_lock = threading.Lock()
_busy = False
_busy_lock = threading.Lock()
_current_session_id: Optional[int] = None


def is_busy() -> bool:
    """True if a crawl is running or the queue has waiting work."""
    with _busy_lock:
        running = _busy
    with _queued_lock:
        waiting = bool(_queued_ids) or not _queue.empty()
    return running or waiting


def queue_size() -> int:
    with _queued_lock:
        return len(_queued_ids)


def current_session_id() -> Optional[int]:
    with _busy_lock:
        return _current_session_id


def enqueue_crawl(session_id: int, priority: int = 1) -> bool:
    """Enqueue a session id for serial crawl. Idempotent for duplicate ids.

    priority: 0=news (highest), 1=default/daily, 2=weekly (lowest).
    Returns True if newly enqueued, False if already queued or running.
    """
    _ensure_worker()
    with _queued_lock:
        with _busy_lock:
            if _current_session_id == session_id:
                logger.info("Crawl queue: session %s already running — skip", session_id)
                return False
        if session_id in _queued_ids:
            logger.info("Crawl queue: session %s already queued — skip", session_id)
            return False
        _queued_ids.add(session_id)
        seq = next(_seq)
        _queue.put((int(priority), seq, session_id))
    logger.info(
        "Crawl queue: enqueued session %s prio=%s (queue size ~%s)",
        session_id,
        priority,
        queue_size(),
    )
    return True


def _ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker_loop, name="crawl-queue-worker", daemon=True)
        t.start()
        _worker_started = True
        logger.info("Crawl queue: worker thread started (priority queue)")


def _worker_loop() -> None:
    global _busy, _current_session_id
    from app.api.sessions import run_crawl_session

    while True:
        priority, seq, session_id = _queue.get()
        with _queued_lock:
            _queued_ids.discard(session_id)
        with _busy_lock:
            _busy = True
            _current_session_id = session_id
        logger.info("Crawl queue: starting session %s (prio=%s)", session_id, priority)
        try:
            run_crawl_session(session_id)
            logger.info("Crawl queue: finished session %s", session_id)
        except Exception as e:
            logger.error("Crawl queue: session %s failed: %s", session_id, e)
        finally:
            with _busy_lock:
                _busy = False
                _current_session_id = None
            _queue.task_done()
