import os
from neo4j import Driver
from auto_clip.core.config import settings
from auto_clip.db.repositories.clip_repo import create_clip
from auto_clip.rendering.ffmpeg_clipper import cut_clip, attach_subtitles
from auto_clip.transcription.whisper_engine import transcribe_words
from auto_clip.captions.srt_writer import words_to_srt

ASPECT_FILTERS = {
    "vertical": "scale=-2:1920, crop=1080:1920",
    "horizontal": "scale=1920:-2, crop=1920:1080",
}

def render_segment(driver: Driver, video_id: str, ordinal: int, captions: bool = False, aspect: str = "original") -> str:
    seg_id = f"{video_id}:{ordinal}"
    with driver.session(database=settings.neo4j_database) as session:
        row = session.run(
            """
            MATCH (v:Video {id: $vid})-[:HAS_SEGMENT]->(s:Segment {id: $sid})
            RETURN s.start_s AS start_s, s.end_s as end_s, v.source_uri AS source_uri, v.audio_path AS audio_path
            """,
            vid=video_id, sid=seg_id,
        ).single()
    if not row:
        raise ValueError("segment/video tidak ditemukan")
    
    start, end = float(row["start_s"]), float(row["end_s"])
    clips_dir = os.path.join(settings.data_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    safe = seg_id.replace(":", "_")
    out_path = os.path.join(clips_dir, f"{safe}.mp4")
    vf = ASPECT_FILTERS.get(aspect)
    cut_clip(row["source_uri"], start, end, out_path, vf=vf)
    
    if captions and row.get("audio_path"):
        words = transcribe_words(row["audio_path"])
        clip_words = [w for w in words if start <= w["start"] < end]
        if clip_words:
            srt = words_to_srt(clip_words, clip_start=start)
            srt_path = os.path.join(clips_dir, f"{safe}.srt")
            with open(srt_path, "w") as f:
                f.write(srt)
            attach_subtitles(out_path, srt_path)
    return create_clip(driver, seg_id, out_path, start, end, aspect=aspect)