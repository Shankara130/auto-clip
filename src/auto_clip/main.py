from fastapi import FastAPI
from auto_clip.core.config import settings
from auto_clip.db.neo4j_driver import ping

app = FastAPI(title=settings.app_name, version=settings.app_version)

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