from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import logging
import os
import re
import tempfile

from app.database import get_db
from app.models.video import Video
from app.models.channel import Channel
from app.models.crawl_session import SessionVideo
from app.schemas.video import VideoResponse, VideoWithChannel, VideoSummaryRequest
from app.services.crawler_service import CrawlerService
from app.services.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter()


class AddSingleVideoRequest(BaseModel):
    video_url: str
    video_id: str
    channel_id: Optional[int] = None  # Optional — resolved automatically from YouTube when omitted
    auto_summarize: bool = False


@router.get("/search/youtube")
def search_youtube_videos(
    q: str = Query(..., min_length=2, description="Search keywords"),
    page_token: Optional[str] = Query(None, description="YouTube nextPageToken for the next page"),
    db: Session = Depends(get_db)
):
    """Search YouTube videos by keyword. Max 10 results per page with
    pagination via YouTube's pageToken. Results are marked already_added
    when the video is already in the local database."""
    from app.services.youtube_service import YouTubeService
    result = YouTubeService().search_videos(q, max_results=10, page_token=page_token)
    if result.get('error'):
        raise HTTPException(status_code=502, detail=result['error'])

    added_ids = {v.video_id for v in db.query(Video.video_id).all()}
    for v in result['videos']:
        v['already_added'] = v['video_id'] in added_ids

    return {
        'query': q,
        'videos': result['videos'],
        'next_page_token': result['next_page_token'],
        'total': result['total']
    }


@router.post("/add-single")
async def add_single_video(
    request: AddSingleVideoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Add a single video by URL (via YouTube Data API).

    When channel_id is omitted, the video's owning channel is looked up on
    YouTube and added to the database automatically (so it becomes selectable
    in future crawl sessions).
    """
    from app.api.channels import _generate_reference_id, _unique_reference_id

    # Check if video already exists
    existing_video = db.query(Video).filter(Video.video_id == request.video_id).first()
    if existing_video:
        raise HTTPException(status_code=400, detail="Video already exists in database")

    # Resolve the target channel: explicit selection wins, otherwise look it up on YouTube
    youtube_service = None
    channel = None
    info = None

    if request.channel_id:
        channel = db.query(Channel).filter(Channel.id == request.channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
    else:
        from app.services.youtube_service import YouTubeService
        youtube_service = YouTubeService()

        # Fetch video details now — reused below so we only hit the API once
        info = youtube_service.get_video_details(request.video_id)
        if not info:
            raise HTTPException(status_code=404, detail="Video not found on YouTube")

        yt_channel_id = info.get('channel_id')
        if not yt_channel_id:
            raise HTTPException(status_code=400, detail="Could not determine the video's channel from YouTube")

        # Get-or-create the channel record for this YouTube channel
        channel = db.query(Channel).filter(Channel.youtube_channel_id == yt_channel_id).first()
        if not channel:
            channel_info = youtube_service.get_channel_info(yt_channel_id)
            if not channel_info:
                raise HTTPException(status_code=404, detail="The video's channel could not be found on YouTube")

            channel = Channel(
                channel_id=_unique_reference_id(
                    db,
                    _generate_reference_id(channel_info['channel_name'], channel_info['channel_url'])
                ),
                youtube_channel_id=yt_channel_id,
                channel_name=channel_info['channel_name'],
                channel_url=channel_info['channel_url'],
                description=channel_info.get('description', ''),
                keywords=[],
                thumbnail_url=channel_info.get('thumbnail', ''),
                crawl_enabled=True,
                crawl_frequency='manual'
            )
            db.add(channel)
            db.commit()
            db.refresh(channel)
            logger.info(f"Auto-added channel '{channel.channel_name}' while adding video {request.video_id}")

    video_url = f"https://www.youtube.com/watch?v={request.video_id}"

    if youtube_service is None:
        from app.services.youtube_service import YouTubeService
        youtube_service = YouTubeService()

    if info is None:
        info = youtube_service.get_video_details(request.video_id)
        if not info:
            raise HTTPException(status_code=404, detail="Video not found on YouTube")

    from app.services.video_tags import resolve_tags
    resolved_tags = resolve_tags(request.video_id, info.get('tags') or [])

    try:
        # Create video object
        video = Video(
            video_id=request.video_id,
            channel_id=channel.id,
            title=info.get('title', ''),
            description=info.get('description', ''),
            duration=info.get('duration', 0),
            published_at=info.get('published_at'),
            view_count=info.get('view_count', 0),
            like_count=info.get('like_count', 0),
            comment_count=info.get('comment_count', 0),
            tags=resolved_tags.tags,
            tags_checked_at=datetime.utcnow() if resolved_tags.ok else None,
            video_url=video_url,
            thumbnail_url=info.get('thumbnail', '')
        )

        db.add(video)
        db.commit()
        db.refresh(video)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add video: {e}")

    # Generate summary if requested
    if request.auto_summarize:
        crawler_service = CrawlerService(db)
        background_tasks.add_task(crawler_service.summarize_video, video)

    return {
        "message": "Video added successfully",
        "video_id": video.id,
        "title": video.title,
        "channel_id": channel.id,
        "channel_name": channel.channel_name,
        "channel_created": request.channel_id is None,
        "auto_summarize": request.auto_summarize
    }


@router.get("/", response_model=List[VideoWithChannel])
def list_videos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    channel_id: Optional[int] = None,
    has_summary: Optional[bool] = None,
    keyword: Optional[str] = None,
    sort_by: str = Query("fetched", pattern="^(fetched|published)$", description="fetched = session fetch time (default), published = video upload time"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="desc (default) or asc sort direction"),
    db: Session = Depends(get_db)
):
    """List videos with filters"""
    query = db.query(Video)

    if channel_id:
        query = query.filter(Video.channel_id == channel_id)

    if has_summary is not None:
        if has_summary:
            query = query.filter(Video.summary_text.isnot(None))
        else:
            query = query.filter(Video.summary_text.is_(None))

    if keyword:
        keyword_lower = keyword.lower()
        query = query.filter(
            (Video.title.ilike(f'%{keyword_lower}%')) |
            (Video.description.ilike(f'%{keyword_lower}%'))
        )

    # Sort: "fetched" = when the video was pulled into the DB by a session
    # (Video.created_at); "published" = when the video was uploaded to YouTube.
    # `order` = asc/desc direction (default desc = newest first).
    if sort_by == "published":
        col = Video.published_at
    else:
        col = Video.created_at
    if order == "asc":
        query = query.order_by(col.asc().nullslast())
    else:
        query = query.order_by(col.desc().nullslast())

    videos = query.offset(skip).limit(limit).all()

    # Include channel info so the frontend can display the channel name
    result = []
    for video in videos:
        video_dict = {
            **video.__dict__,
            'channel_name': video.channel.channel_name if video.channel else 'Unknown Channel',
            'channel_url': video.channel.channel_url if video.channel else '',
            'channel_thumbnail_url': video.channel.thumbnail_url if video.channel else None
        }
        result.append(VideoWithChannel(**video_dict))

    return result


@router.get("/search", response_model=List[VideoWithChannel])
def search_videos(
    q: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    channel_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Search videos by keyword"""
    query = db.query(Video).join(Channel)

    # Filter by channel if specified
    if channel_id:
        query = query.filter(Video.channel_id == channel_id)

    search_term = f'%{q.lower()}%'
    query = query.filter(
        (Video.title.ilike(search_term)) |
        (Video.description.ilike(search_term)) |
        (Video.summary_text.ilike(search_term))
    )

    videos = query.order_by(Video.created_at.desc().nullslast()).offset(skip).limit(limit).all()

    # Add channel info
    result = []
    for video in videos:
        video_dict = {
            **video.__dict__,
            'channel_name': video.channel.channel_name if video.channel else 'Unknown Channel',
            'channel_url': video.channel.channel_url if video.channel else '',
            'channel_thumbnail_url': video.channel.thumbnail_url if video.channel else None
        }
        result.append(VideoWithChannel(**video_dict))

    return result


@router.get("/{video_id}", response_model=VideoWithChannel)
def get_video(video_id: int, db: Session = Depends(get_db)):
    """Get a specific video by ID"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_dict = {
        **video.__dict__,
        'channel_name': video.channel.channel_name if video.channel else 'Unknown Channel',
        'channel_url': video.channel.channel_url if video.channel else '',
        'channel_thumbnail_url': video.channel.thumbnail_url if video.channel else None
    }

    return VideoWithChannel(**video_dict)


@router.post("/{video_id}/summarize")
async def summarize_video(
    video_id: int,
    background_tasks: BackgroundTasks,
    force_regenerate: bool = False,
    db: Session = Depends(get_db)
):
    """Generate or regenerate summary for a video"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if summary already exists
    if video.summary_text and not force_regenerate:
        return {
            "message": "Summary already exists",
            "summary": video.summary_text,
            "generated_at": video.summary_generated_at
        }

    # Generate summary in background; open a fresh DB session because the
    # request session is closed before background tasks execute
    def _run_summarize_task(video_id: int):
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            crawler_service = CrawlerService(db)
            import asyncio
            asyncio.run(crawler_service.summarize_video(db.query(Video).filter(Video.id == video_id).first()))
        finally:
            db.close()

    background_tasks.add_task(_run_summarize_task, video_id)

    return {
        "message": "Summary generation started",
        "video_id": video_id
    }


@router.get("/{video_id}/transcript")
def get_video_transcript(video_id: int, db: Session = Depends(get_db)):
    """Get video transcript (fetch + format if not already stored)"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.transcript_text:
        # Try to extract transcript
        from app.services.transcript_service import TranscriptService
        from app.services.transcript_formatter import format_transcript
        transcript_service = TranscriptService()
        transcript = transcript_service.get_transcript(video.video_id)

        if transcript:
            video.transcript_text = format_transcript(transcript)
            db.commit()
        else:
            raise HTTPException(status_code=404, detail="Transcript not available for this video")

    return {
        "video_id": video.video_id,
        "title": video.title,
        "transcript": video.transcript_text
    }


@router.post("/{video_id}/detail-summary")
async def generate_detail_summary(video_id: int, force_regenerate: bool = False, db: Session = Depends(get_db)):
    """Generate a well-structured detail summary from the video's transcript (feature 5)."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.transcript_text:
        raise HTTPException(
            status_code=400,
            detail="Transcript not downloaded yet. Use 'Get Transcript' first."
        )

    if video.detail_summary and not force_regenerate:
        return {
            "message": "Detail summary already exists",
            "detail_summary": video.detail_summary,
            "generated_at": video.detail_summary_generated_at
        }

    from app.services.summarizer_service import SummarizerService
    summarizer = SummarizerService()
    channel_name = video.channel.channel_name if video.channel else ""
    detail_summary = summarizer.generate_detail_summary(
        video.transcript_text, title=video.title, channel_name=channel_name
    )

    if not detail_summary:
        raise HTTPException(status_code=502, detail="Summary generation failed — check that an LLM API key is configured")

    video.detail_summary = detail_summary
    video.detail_summary_generated_at = datetime.now()
    db.commit()

    return {
        "message": "Detail summary generated",
        "detail_summary": detail_summary,
        "generated_at": video.detail_summary_generated_at
    }


@router.post("/{video_id}/mindmap")
def generate_video_mindmap(video_id: int, db: Session = Depends(get_db)):
    """Generate a mind map from the video's detail summary (feature 6)."""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.detail_summary:
        raise HTTPException(
            status_code=400,
            detail="Detail summary not generated yet. Use 'Generate Summary' first."
        )

    from app.services.summarizer_service import SummarizerService
    summarizer = SummarizerService()
    mind_map = summarizer.generate_mind_map(video.detail_summary, title=video.title)

    if not mind_map:
        raise HTTPException(status_code=502, detail="Mind map generation failed — check that an LLM API key is configured")

    return {
        "message": "Mind map generated",
        "video_id": video_id,
        "mind_map": mind_map
    }


@router.delete("/{video_id}", status_code=204)
def delete_video(video_id: int, db: Session = Depends(get_db)):
    """Delete a video"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete related session_videos records first
    db.query(SessionVideo).filter(SessionVideo.video_id == video_id).delete()

    # Now delete the video
    db.delete(video)
    db.commit()

    return None


@router.get("/{video_id}/download")
async def download_video(video_id: int, db: Session = Depends(get_db)):
    """Download the video's data as a text file.

    The YouTube Data API does not provide video file downloads, so this
    exports everything stored for the video: metadata, transcript and
    summaries — as a downloadable .txt file.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    channel_name = video.channel.channel_name if video.channel else "Unknown"
    lines = [
        f"Title: {video.title}",
        f"URL: https://www.youtube.com/watch?v={video.video_id}",
        f"Channel: {channel_name}",
        f"Published: {video.published_at or 'Unknown'}",
        f"Duration: {video.duration or 0} seconds",
        f"Views: {video.view_count or 0}",
        f"Likes: {video.like_count or 0}",
        f"Tags: {', '.join(video.tags or []) or 'None'}",
        "",
        "=" * 60,
        "DESCRIPTION",
        "=" * 60,
        video.description or "No description",
        "",
        "=" * 60,
        "AI SUMMARY",
        "=" * 60,
        video.summary_text or "No summary generated",
        "",
        "=" * 60,
        "DETAIL SUMMARY",
        "=" * 60,
        video.detail_summary or "No detail summary generated",
        "",
        "=" * 60,
        "TRANSCRIPT",
        "=" * 60,
        video.transcript_text or "No transcript downloaded",
    ]

    filename = re.sub(r'[^A-Za-z0-9 _-]', '', video.title)[:50].strip().replace(' ', '_') or f"video_{video.video_id}"
    from fastapi.responses import Response
    return Response(
        content="\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.txt"'
        }
    )


@router.get("/export/csv")
def export_videos_csv(
    channel_id: Optional[int] = None,
    has_summary: Optional[bool] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export videos to CSV format"""
    query = db.query(Video).join(Channel)

    if channel_id:
        query = query.filter(Video.channel_id == channel_id)

    if has_summary is not None:
        if has_summary:
            query = query.filter(Video.summary_text.isnot(None))
        else:
            query = query.filter(Video.summary_text.is_(None))

    if keyword:
        keyword_lower = keyword.lower()
        query = query.filter(
            (Video.title.ilike(f'%{keyword_lower}%')) |
            (Video.description.ilike(f'%{keyword_lower}%'))
        )

    videos = query.order_by(Video.published_at.desc()).all()

    export_service = ExportService()
    csv_data = export_service.export_to_csv(videos)

    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=videos_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )


@router.get("/export/excel")
def export_videos_excel(
    channel_id: Optional[int] = None,
    has_summary: Optional[bool] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export videos to Excel format"""
    query = db.query(Video).join(Channel)

    if channel_id:
        query = query.filter(Video.channel_id == channel_id)

    if has_summary is not None:
        if has_summary:
            query = query.filter(Video.summary_text.isnot(None))
        else:
            query = query.filter(Video.summary_text.is_(None))

    if keyword:
        keyword_lower = keyword.lower()
        query = query.filter(
            (Video.title.ilike(f'%{keyword_lower}%')) |
            (Video.description.ilike(f'%{keyword_lower}%'))
        )

    videos = query.order_by(Video.published_at.desc()).all()

    export_service = ExportService()
    excel_data = export_service.export_to_excel(videos)

    if not excel_data:
        raise HTTPException(status_code=500, detail="Excel export not available. Install openpyxl package.")

    return StreamingResponse(
        iter([excel_data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=videos_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        }
    )


@router.get("/export/report")
def export_summary_report(
    channel_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Generate and export a summary report"""
    query = db.query(Video).join(Channel)

    if channel_id:
        query = query.filter(Video.channel_id == channel_id)

    videos = query.all()

    export_service = ExportService()
    report = export_service.export_summary_report(videos)

    return StreamingResponse(
        iter([report]),
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=video_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        }
    )


@router.post("/batch/summarize")
async def batch_summarize_videos(
    video_ids: List[int],
    background_tasks: BackgroundTasks,
    force_regenerate: bool = False,
    db: Session = Depends(get_db)
):
    """Generate summaries for multiple videos"""
    videos = db.query(Video).filter(Video.id.in_(video_ids)).all()

    if not videos:
        raise HTTPException(status_code=404, detail="No videos found")

    crawler_service = CrawlerService(db)

    for video in videos:
        if not video.summary_text or force_regenerate:
            background_tasks.add_task(crawler_service.summarize_video, video)

    return {
        "message": f"Batch summarization started for {len(videos)} videos",
        "video_count": len(videos)
    }


@router.post("/batch/delete")
def batch_delete_videos(
    video_ids: List[int],
    db: Session = Depends(get_db)
):
    """Delete multiple videos"""
    # Delete related session_videos records first
    db.query(SessionVideo).filter(SessionVideo.video_id.in_(video_ids)).delete(synchronize_session=False)

    # Delete videos
    deleted_count = db.query(Video).filter(Video.id.in_(video_ids)).delete(synchronize_session=False)
    db.commit()

    return {
        "message": f"Deleted {deleted_count} videos",
        "deleted_count": deleted_count
    }

