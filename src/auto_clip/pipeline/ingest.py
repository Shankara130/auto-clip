import os
import subprocess
from neo4j import Driver
from auto_clip.core.config import settings
from auto_clip.db.repositories.video_repo import set_video_status

def ingest_video(driver: Driver, video_id: str, source_path: str) -> None:
    """Ekstrak audio 16kHz mono WAV dari video. Perbarui status."""
    audio_dir = os.path.join(settings.data_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    out_path = os.path.join(audio_dir, f"{video_id}.wav")
    try:
        set_video_status(driver, video_id, "ingesting")
        subprocess.run(
            ["ffmpeg", "-y", "-i", source_path, "-ac", "1", "-ar", "16000", out_path],
            check=True, capture_output=True,
        )
        set_video_status(driver, video_id, "ingested", audio_path=out_path)
    except Exception as e:
        set_video_status(driver, video_id, "failed", error=str(e))
        raise