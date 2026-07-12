import os
import subprocess
import httpx
import glob
import yt_dlp
from neo4j import Driver
from auto_clip.core.config import settings
from auto_clip.db.repositories.video_repo import set_video_status

_VIDEO_EXTS = (".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v")

def _is_direct_video(url: str) -> bool:
    return url.lower().split("?")[0].endswith(_VIDEO_EXTS)

def _resolve_source(source_uri: str, video_id: str) -> str:
    if not source_uri.startswith(("http://", "https://")):
        return source_uri
    
    uploads = os.path.join(settings.data_dir, "uploads")
    os.makedirs(uploads, exist_ok=True)
    
    if _is_direct_video(source_uri):
        local = os.path.join(uploads, f"{video_id}.mp4")
        with httpx.stream("GET", source_uri, follow_redirects=True, timeout=httpx.Timeout(300.0)) as resp:
            resp.raise_for_status()
            with open(local, "wb") as f:
                for chunk in resp.iter_bytes():
                    f.write(chunk)
        return local
    
    base = os.path.join(uploads, video_id)
    with yt_dlp.YoutubeDL({
        "outtmpl": f"{base}.%(ext)s",
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }) as ydl :
        ydl.download([source_uri])
    matches = glob.glob(f"{base}.*")
    if not matches:
        raise RuntimeError("yt-dlp tidak menghasilkan file")
    return matches[0]

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