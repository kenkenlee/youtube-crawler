from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio

from app.database import get_db
from app.models.crawl_session import CrawlSession, SessionVideo
from app.models.channel import Channel
from app.schemas.session import SessionCreate, SessionResponse, SessionProgress
from app.services.crawler_service import CrawlerService

router = APIRouter()


@router.post("/", response_model=SessionResponse, status_code=201)
def create_session(session: SessionCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Create a new crawl session"""
    # Verify channels exist
    channels = db.query(Channel).filter(Channel.id.in_(session.channel_ids)).all()
    if len(channels) != len(session.channel_ids):
        raise HTTPException(status_code=400, detail="One or more channels not found")

    # Create session
    db_session = CrawlSession(
        session_name=session.session_name,
        session_type=session.session_type,
        channel_ids=session.channel_ids,
        filter_keywords=session.filter_keywords,
        max_videos=session.max_videos,
        recurrence_hours=session.recurrence_hours,
        recurrence_active=bool(session.recurrence_hours),
        status="pending"
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # Start crawling in background
    background_tasks.add_task(run_crawl_session, db_session.id)

    return db_session


@router.put("/{session_id}/recurrence/pause")
def pause_recurrence(session_id: int, db: Session = Depends(get_db)):
    """Stop a session from recurring (future runs cancelled, history kept)"""
    session = db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.recurrence_hours:
        raise HTTPException(status_code=400, detail="Session is not recurring")

    session.recurrence_active = False
    db.commit()
    return {"message": f"Recurrence paused for session {session_id}"}


@router.put("/{session_id}/recurrence/resume")
def resume_recurrence(session_id: int, db: Session = Depends(get_db)):
    """Resume recurrence for a paused recurring session"""
    session = db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.recurrence_hours:
        raise HTTPException(status_code=400, detail="Session is not recurring")

    session.recurrence_active = True
    db.commit()
    return {"message": f"Recurrence resumed for session {session_id}"}


def run_crawl_session(session_id: int):
    """Background task to run crawl session"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        crawler_service = CrawlerService(db)
        asyncio.run(crawler_service.start_crawl_session(session_id))
    finally:
        db.close()


@router.get("/", response_model=List[SessionResponse])
def list_sessions(
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1),
    status: Optional[str] = Query(None),
    recurring: Optional[bool] = Query(
        None,
        description="When true, return only recurring templates (not child runs)",
    ),
    db: Session = Depends(get_db),
):
    """List crawl sessions, newest first.

    Page size defaults to 10 (``skip`` / ``limit``). The total matching rows
    is returned in the ``X-Total-Count`` header so clients can page through
    older sessions. ``status`` filters the list. ``recurring=true`` returns
    only recurring templates (an interval is set and the row is not a child run).
    """
    query = db.query(CrawlSession)

    if status:
        query = query.filter(CrawlSession.status == status)

    if recurring:
        query = query.filter(
            CrawlSession.recurrence_hours.isnot(None),
            CrawlSession.recurrence_hours > 0,
            CrawlSession.parent_session_id.is_(None),
        )

    total = query.count()
    sessions = (
        query.order_by(CrawlSession.created_at.desc(), CrawlSession.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    response.headers["X-Total-Count"] = str(total)

    return sessions


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: int, db: Session = Depends(get_db)):
    """Get a specific session"""
    session = db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.get("/{session_id}/progress", response_model=SessionProgress)
def get_session_progress(session_id: int, db: Session = Depends(get_db)):
    """Get real-time progress of a session"""
    session = db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Calculate progress
    total_work = session.total_channels if session.total_channels > 0 else 1
    progress_percentage = (session.processed_channels / total_work) * 100

    channels_progress = f"{session.processed_channels}/{session.total_channels}"
    videos_progress = f"{session.videos_processed}/{session.total_videos_found}"

    # Determine current activity
    if session.status == "pending":
        current_activity = "Waiting to start..."
    elif session.status == "running":
        current_activity = f"Crawling channels... ({channels_progress})"
    elif session.status == "completed":
        current_activity = "Completed"
    elif session.status == "failed":
        current_activity = "Failed"
    elif session.status == "cancelled":
        current_activity = "Cancelled"
    else:
        current_activity = "Unknown"

    return SessionProgress(
        session_id=session.id,
        status=session.status,
        progress_percentage=progress_percentage,
        channels_progress=channels_progress,
        videos_progress=videos_progress,
        current_activity=current_activity,
        errors=session.error_count
    )


@router.put("/{session_id}/cancel")
def cancel_session(session_id: int, db: Session = Depends(get_db)):
    """Cancel a running session"""
    crawler_service = CrawlerService(db)
    success = crawler_service.cancel_session(session_id)

    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel session")

    return {"message": "Session cancelled successfully"}


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    """Delete a session"""
    session = db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.delete(session)
    db.commit()

    return None


@router.get("/{session_id}/videos")
def get_session_videos(session_id: int, db: Session = Depends(get_db)):
    """Get all videos from a session"""
    session = db.query(CrawlSession).filter(CrawlSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_videos = db.query(SessionVideo).filter(SessionVideo.session_id == session_id).all()

    result = []
    for sv in session_videos:
        video = sv.video
        result.append({
            'id': video.id,
            'video_id': video.video_id,
            'title': video.title,
            'channel_name': video.channel.channel_name,
            'processing_status': sv.processing_status,
            'has_summary': video.summary_text is not None,
            'error_message': sv.error_message
        })

    return result
