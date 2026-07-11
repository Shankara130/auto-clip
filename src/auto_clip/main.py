from fastapi import FastAPI
from auto_clip.core.config import settings

app = FastAPI(title=settings.app_name, version=settings.app_version)

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}