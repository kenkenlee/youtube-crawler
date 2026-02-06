from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import engine, Base
from app.models import Channel, Video, CrawlSession, SessionVideo


# Create database tables
def init_db():
    Base.metadata.create_all(bind=engine)


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

# Mount static files
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)


# Root endpoint - redirect to dashboard
@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard")


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
from app.api import channels, videos, sessions, dashboard, websocket

app.include_router(channels.router, prefix="/api/channels", tags=["channels"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])
