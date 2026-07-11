from neo4j import Driver
from auto_clip.db.repositories.video_repo import get_video, set_video_status
from auto_clip.db.repositories.segment_repo import create_segment
from auto_clip.models.segment import SegmentCreate
from auto_clip.transcription.whisper_engine import transcribe_audio

def transcribe_video(driver: Driver, video_id: str) -> int:
    """Transkripsi audio -> simpan segmen ke graph. Kembalikan jumlah segmen."""
    video = get_video(driver, video_id)
    if not video:
        raise ValueError("video tidak ditemukan")
    audio_path = video.get("audio_path")
    if not audio_path:
        raise ValueError("audio belum di-ingest")
    try:
        set_video_status(driver, video_id, "transcribing", audio_path=audio_path)
        segments = transcribe_audio(audio_path)
        for i, seg in enumerate(segments):
            create_segment(
                driver, video_id,
                SegmentCreate(ordinal=i, start_s=float(seg["start"]), end_s=float(seg["end"]), text=seg["text"]),
            )
        set_video_status(driver, video_id, "transcribed", audio_path=audio_path)
        return len(segments)
    except Exception as e:
        set_video_status(driver, video_id, "failed", error=str(e))
        raise