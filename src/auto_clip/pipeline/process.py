from neo4j import Driver
from auto_clip.db.repositories.video_repo import get_video, set_video_status
from auto_clip.pipeline.ingest import ingest_video
from auto_clip.pipeline.transcribe import transcribe_video
from auto_clip.pipeline.analyze import analyze_video
from auto_clip.recommend.recommend import recommend
from auto_clip.pipeline.render import render_segment

def process_and_render(driver: Driver, video_id: str, aspect: str = "vertical") -> str:
    try:
        source_uri = get_video(driver, video_id)["source_uri"]
        set_video_status(driver, video_id, "processing")
        ingest_video(driver, video_id, source_uri)
        transcribe_video(driver, video_id)
        analyze_video(driver, video_id)
        top = recommend(driver, video_id, k=1)
        ordinal = top[0]["ordinal"]
        clip_id = render_segment(driver, video_id, ordinal, captions=True, aspect=aspect)
        set_video_status(driver, video_id, "done")
        return clip_id
    except Exception as e:
        set_video_status(driver, video_id, "failed", error=str(e))