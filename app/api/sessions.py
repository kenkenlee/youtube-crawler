from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
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
        status="pending"
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    # Start crawling in background
    background_tasks.add_task(run_crawl_session, db_session.id)

    return db_session


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
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    db: Session = Depends(get_db)
):
    """List all crawl sessions"""
    query = db.query(CrawlSession)

    if status:
        query = query.filter(CrawlSession.status == status)

    sessions = query.order_by(CrawlSession.created_at.desc()).offset(skip).limit(limit).all()

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
