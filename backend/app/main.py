from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import health, jobs, youtube
from app.core.config import settings
from app.core.database import Base, engine
from app.core.exceptions import register_exception_handlers


def create_app() -> FastAPI:
    Base.metadata.create_all(bind=engine)
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(jobs.router, prefix=settings.api_prefix)
    app.include_router(youtube.router, prefix=settings.api_prefix)
    app.mount("/storage", StaticFiles(directory=settings.storage_path), name="storage")
    register_exception_handlers(app)
    return app


app = create_app()
