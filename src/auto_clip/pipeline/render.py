import os
from neo4j import Driver
from auto_clip.core.config import settings
from auto_clip.db.repositories.clip_repo import create_clip
from auto_clip.rendering.ffmpeg_clipper import cut_clip

def render_segment(driver: Driver, video_id: str, ordinal: int) -> str:
    seg_id = f"{video_id}:{ordinal}"
    with driver.session(database=settings.neo4j_database) as session:
        row = session.run(
            """
            MATCH (v:Video {id: $vid})-[:HAS_SEGMENT]->(s:Segment {id: $sid})
            RETURN s.start_s AS start_s, s.end_s as end_s, v.source_uri AS source_uri
            """,
            vid=video_id, sid=seg_id,
        ).single()
    if not row:
        raise ValueError("segment/video tidak ditemukan")
    clips_dir = os.path.join(settings.data_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    out_path = os.path.join(clips_dir, f"{seg_id}.mp4")
    cut_clip(row["source_uri"], float(row["start_s"]), float(row["end_s"]), out_path)
    return create_clip(driver, seg_id, out_path, float(row["start_s"]), float(row["end_s"]))