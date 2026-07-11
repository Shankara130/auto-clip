from contextlib import asynccontextmanager
from fastapi import FastAPI
from auto_clip.core.config import settings
from auto_clip.db.neo4j_driver import get_driver, close_driver, ping
from auto_clip.db.constraints import init_schema
from auto_clip.api.videos import router as videos_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    driver = get_driver()
    init_schema(driver)
    yield
    close_driver()

app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.include_router(videos_router)

@app.get("/health")
def health():
    try:
        neo4j_ok = ping()
    except Exception:
        neo4j_ok = False
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "neo4j": "connected" if neo4j_ok else "unavailable"
    }