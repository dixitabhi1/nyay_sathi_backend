from fastapi import APIRouter

from app.api.routes import admin, analysis, chat, documents, fir, health, research


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(fir.router, prefix="/fir", tags=["fir"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
