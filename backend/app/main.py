from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import ROOT_DIR, get_settings
from app.core.dependencies import get_retriever
from app.db.analytics import init_analytics_db
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    init_analytics_db()
    get_retriever().ensure_index()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)

frontend_dist_path = ROOT_DIR / "frontend" / "dist"
frontend_assets_path = frontend_dist_path / "assets"

if frontend_assets_path.exists():
    app.mount("/assets", StaticFiles(directory=frontend_assets_path), name="frontend-assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    index_file = frontend_dist_path / "index.html"
    requested = frontend_dist_path / full_path

    if not index_file.exists():
        return {"status": "ok", "message": "NyayaSetu backend is running. Frontend build not found in this environment."}

    if full_path and requested.exists() and requested.is_file():
        return FileResponse(requested)

    return FileResponse(index_file)
