from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import os
import tempfile

from app.database import get_db
from app.models.video import Video
from app.models.channel import Channel
from app.models.crawl_session import SessionVideo
from app.schemas.video import VideoResponse, VideoWithChannel, VideoSummaryRequest
from app.services.crawler_service import CrawlerService
from app.services.export_service import ExportService

router = APIRouter()


@router.get("/", response_model=List[VideoResponse])
def list_videos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    channel_id: Optional[int] = None,
    has_summary: Optional[bool] = None,
    keyword: Optional[str] = None,
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

    videos = query.order_by(Video.published_at.desc()).offset(skip).limit(limit).all()

    return videos


@router.get("/search", response_model=List[VideoWithChannel])
def search_videos(
    q: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Search videos by keyword"""
    query = db.query(Video).join(Channel)

    search_term = f'%{q.lower()}%'
    query = query.filter(
        (Video.title.ilike(search_term)) |
        (Video.description.ilike(search_term)) |
        (Video.summary_text.ilike(search_term))
    )

    videos = query.order_by(Video.published_at.desc()).offset(skip).limit(limit).all()

    # Add channel info
    result = []
    for video in videos:
        video_dict = {
            **video.__dict__,
            'channel_name': video.channel.channel_name,
            'channel_url': video.channel.channel_url
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
        'channel_name': video.channel.channel_name,
        'channel_url': video.channel.channel_url
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

    # Generate summary in background
    crawler_service = CrawlerService(db)
    background_tasks.add_task(crawler_service.summarize_video, video)

    return {
        "message": "Summary generation started",
        "video_id": video_id
    }


@router.get("/{video_id}/transcript")
def get_video_transcript(video_id: int, db: Session = Depends(get_db)):
    """Get video transcript"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.transcript_text:
        # Try to extract transcript
        from app.services.transcript_service import TranscriptService
        transcript_service = TranscriptService()
        transcript = transcript_service.get_transcript(video.video_id)

        if transcript:
            video.transcript_text = transcript
            db.commit()
        else:
            raise HTTPException(status_code=404, detail="Transcript not available for this video")

    return {
        "video_id": video.video_id,
        "title": video.title,
        "transcript": video.transcript_text
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
    """Download a video using yt-dlp"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        import yt_dlp

        # Create a temporary directory for downloads
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

        # Configure yt-dlp options
        ydl_opts = {
            'format': 'best[ext=mp4]/best',  # Prefer mp4 format
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
        }

        # Download the video
        video_url = f"https://www.youtube.com/watch?v={video.video_id}"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)

        # Return the file as a download
        if os.path.exists(filename):
            return FileResponse(
                path=filename,
                filename=os.path.basename(filename),
                media_type='video/mp4',
                headers={
                    "Content-Disposition": f"attachment; filename={os.path.basename(filename)}"
                }
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to download video")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


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

