from fastapi import APIRouter, HTTPException, BackgroundTasks
from auto_clip.db.neo4j_driver import get_driver
from auto_clip.db.repositories.video_repo import create_video, get_video
from auto_clip.db.repositories.segment_repo import create_segment, get_segments_by_video
from auto_clip.models.video import VideoCreate
from auto_clip.models.segment import SegmentCreate
from auto_clip.pipeline.ingest import ingest_video
from auto_clip.pipeline.transcribe import transcribe_video
from auto_clip.pipeline.render import render_segment
from auto_clip.pipeline.analyze import analyze_video
from auto_clip.recommend.recommend import recommend

router = APIRouter(prefix="/videos", tags=["videos"])

@router.post("")
def create_video_endpoint(data: VideoCreate):
    driver = get_driver()
    video_id = create_video(driver, data)
    return {"id": video_id, **data.model_dump()}

@router.get("/{video_id}")
def get_video_endpoint(video_id: str):
    driver = get_driver()
    video = get_video(driver, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@router.post("/{video_id}/segments")
def create_segment_endpoint(video_id: str, data: SegmentCreate):
    seg_id = create_segment(get_driver(), video_id, data)
    return {"id": seg_id, "video_id": video_id, **data.model_dump()}

@router.get("/{video_id}/segments")
def list_segments(video_id: str):
    return get_segments_by_video(get_driver(), video_id)

@router.post("/{video_id}/ingest")
def ingest_endpoint(video_id: str, background_tasks: BackgroundTasks):
    video = get_video(get_driver(), video_id)
    if video is None:
      raise HTTPException(status_code=404, detail="Video not found")
    source = video["source_uri"]        # untuk sekarang: path lokal
    background_tasks.add_task(ingest_video, get_driver(), video_id, source)
    return {"id": video_id, "message": "ingest queued"}

@router.post("/{video_id}/transcribe")
def transcribe_endpoint(video_id: str, background_tasks: BackgroundTasks):
    video = get_video(get_driver(), video_id)
    if video is None:
      raise HTTPException(status_code=404, detail="Video not found")
    background_tasks.add_task(transcribe_video, get_driver(), video_id)
    return {"id": video_id, "message": "transcribe queued"}

@router.post("/{video_id}/segments/{ordinal}/render")
def render_endpoint(video_id: str, ordinal: int):
    clip_id = render_segment(get_driver(), video_id, ordinal)
    return {"clip_id": clip_id, "message": "rendered"}

@router.post("/{video_id}/analyze")
def analyze_endpoint(video_id: str, background_tasks: BackgroundTasks):
    video = get_video(get_driver(), video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    background_tasks.add_task(analyze_video, get_driver(), video_id)
    return {"id": video_id, "message": "analyze queued"}

@router.get("/{video_id}/recommend")
def recommend_endpoint(video_id: str, k: int = 3):
    video = get_video(get_driver(), video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"video_id": video_id, "recommendations": recommend(get_driver(), video_id, k)}

@router.post("/{video_id}/segments/{ordinal}/render")
def render_endpoint(video_id: str, ordinal: int, captions: bool = False):
    clip_id = render_segment(get_driver(), video_id, ordinal, captions=captions)
    return {"clip_id": clip_id, "captions": captions}