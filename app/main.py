from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import Channel, Video, CrawlSession, SessionVideo, AppSetting
from app.services.admin_auth import verify_password, is_authenticated


# Create database tables
def init_db():
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations():
    """Add columns that exist in the models but not in older database files.

    SQLite supports ALTER TABLE ADD COLUMN, so missing columns can be added
    in place without a full migration framework. Backfills sensible values
    where applicable.
    """
    from sqlalchemy import text, inspect

    migrations = {
        "videos": [
            ("video_url", "ALTER TABLE videos ADD COLUMN video_url VARCHAR(500)"),
            ("thumbnail_url", "ALTER TABLE videos ADD COLUMN thumbnail_url VARCHAR(500)"),
            ("tags_checked_at", "ALTER TABLE videos ADD COLUMN tags_checked_at DATETIME"),
        ],
        "channels": [
            ("thumbnail_url", "ALTER TABLE channels ADD COLUMN thumbnail_url VARCHAR(500)"),
        ],
        "crawl_sessions": [
            ("max_videos", "ALTER TABLE crawl_sessions ADD COLUMN max_videos INTEGER DEFAULT 5"),
            ("recurrence_hours", "ALTER TABLE crawl_sessions ADD COLUMN recurrence_hours INTEGER"),
            ("recurrence_active", "ALTER TABLE crawl_sessions ADD COLUMN recurrence_active BOOLEAN DEFAULT 1"),
            ("parent_session_id", "ALTER TABLE crawl_sessions ADD COLUMN parent_session_id INTEGER"),
        ],
    }

    with engine.connect() as conn:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        for table, columns in migrations.items():
            if table not in existing_tables:
                continue
            existing_columns = {c["name"] for c in inspector.get_columns(table)}
            for column, ddl in columns:
                if column not in existing_columns:
                    print(f"Applying migration: {ddl}")
                    conn.execute(text(ddl))
        # Backfill video URLs for pre-existing rows
        conn.execute(text(
            "UPDATE videos SET video_url = 'https://www.youtube.com/watch?v=' || video_id "
            "WHERE video_url IS NULL AND video_id IS NOT NULL"
        ))
        conn.commit()

    # Backfill real channel logos: channels created before logo storage have a
    # NULL thumbnail_url, which made every logo render as the same placeholder.
    # Fetch each missing avatar once from the YouTube Data API (channels.list).
    try:
        with SessionLocal() as db:
            from app.services.youtube_service import YouTubeService
            from app.models.channel import Channel as ChannelModel
            svc = YouTubeService()
            missing = db.query(ChannelModel).filter(
                (ChannelModel.thumbnail_url.is_(None)) | (ChannelModel.thumbnail_url == '')
            ).all()
            for ch in missing:
                yt_id = ch.youtube_channel_id
                if not yt_id and ch.channel_url:
                    yt_id = svc.extract_channel_id(ch.channel_url)
                if not yt_id:
                    continue
                info = svc.get_channel_info(yt_id)
                if info and info.get('thumbnail'):
                    ch.thumbnail_url = info['thumbnail']
                    db.commit()
                    print(f"Backfilled logo for channel '{ch.channel_name}'")
    except Exception as e:
        print(f"Channel logo backfill skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Initializing database...")
    init_db()
    print("Database initialized successfully")

    # Initialize scheduler if enabled
    if settings.ENABLE_SCHEDULER:
        try:
            from app.tasks.scheduler import start_scheduler
            start_scheduler()
            print("Scheduler started successfully")
        except Exception as e:
            print(f"Failed to start scheduler: {e}")

    yield

    # Shutdown
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware (signed cookies) for admin authentication
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# Mount static files
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)


# Root endpoint - redirect to dashboard
@app.get("/")
async def root():
    return RedirectResponse(url="/videos")


# Web interface routes
@app.get("/dashboard")
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/channels")
async def channels_page(request: Request):
    return templates.TemplateResponse("channels.html", {"request": request})


@app.get("/sessions")
async def sessions_page(request: Request):
    return templates.TemplateResponse("sessions.html", {"request": request})


@app.get("/videos")
async def videos_page(request: Request):
    return templates.TemplateResponse("videos.html", {"request": request})


@app.get("/settings")
async def settings_page(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/settings/login", status_code=303)
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/settings/login")
async def settings_login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse(url="/settings", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/settings/login")
async def settings_login(request: Request, password: str = Form(...)):
    if verify_password(password):
        request.session["admin_authenticated"] = True
        return RedirectResponse(url="/settings", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Incorrect admin password."},
        status_code=401,
    )


@app.get("/settings/logout")
async def settings_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/settings/login", status_code=303)


# API info endpoint
@app.get("/api")
async def api_info():
    return {
        "message": "YouTube Crawler API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Import and include routers
from app.api import channels, videos, sessions, dashboard, websocket, settings as settings_api

app.include_router(channels.router, prefix="/api/channels", tags=["channels"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
