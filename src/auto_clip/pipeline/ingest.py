import os
import subprocess
import httpx
from neo4j import Driver
from auto_clip.core.config import settings
from auto_clip.db.repositories.video_repo import set_video_status

def _resolve_source(source_uri: str, video_id: str) -> str:
    """URL -> download ke lokal; path lokal -> pakai apa adanya"""
    if source_uri.startswith(("http://", "https://")):
        uploads = os.path.join(settings.data_dir, "uploads")
        os.makedirs(uploads, exist_ok=True)
        local = os.path.join(uploads, f"{video_id}.mp4")
        with httpx.stream("GET", source_uri, follow_redirects=True, timeout=httpx.Timeout(300.0)) as resp:
            resp.raise_for_status()
            with open(local, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        return local
    return source_uri

def ingest_video(driver: Driver, video_id: str, source_uri: str) -> None:
    """Ekstrak audio dari video (download bila URL). Perbarui status"""
    audio_dir = os.path.join(settings.data_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    out_path = os.path.join(audio_dir, f"{video_id}.wav")
    try:
        local = _resolve_source(source_uri, video_id)
        set_video_status(driver, video_id, "ingesting", source_path=local)
        subprocess.run(
            ["ffmpeg", "-y", "-i", local, "-ac", "1", "-ar", "16000", out_path],
            check=True, capture_output=True,
        )
        set_video_status(driver, video_id, "ingested", audio_path=out_path, source_path=local)
    except Exception as e:
        set_video_status(driver, video_id, "failed", error=str(e))
        raise