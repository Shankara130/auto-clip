from fastapi import APIRouter, HTTPException
from auto_clip.db.neo4j_driver import get_driver
from auto_clip.db.repositories.video_repo import create_video, get_video
from auto_clip.models.video import VideoCreate

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