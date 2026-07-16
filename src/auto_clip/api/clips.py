from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from auto_clip.core.config import settings
from auto_clip.db.neo4j_driver import get_driver
from auto_clip.db.repositories.video_repo import create_video
from auto_clip.models.video import VideoCreate
from auto_clip.pipeline.process import process_and_render

router = APIRouter(prefix="/clips", tags=["clips"])

class GenerateRequest(BaseModel):
    source_uri: str
    aspect: str = "vertical"
    
@router.post("/generate")
def generate(req: GenerateRequest, background_task: BackgroundTasks):
    driver = get_driver()
    vid = create_video(driver, VideoCreate(source_uri=req.source_uri, title="Generated"))
    background_task.add_task(process_and_render, driver, vid, req.aspect)
    return {"video_id": vid, "status": "processing"}

@router.get("/{clip_id}/download")
def download(clip_id: str):
    with get_driver().session(database=settings.neo4j_database) as s:
        rec = s.run("MATCH (c:Clip {id: $cid}) RETURN c.render_path AS p", cid=clip_id).single()
    if not rec or not rec["p"]:
        raise HTTPException(status_code=404, detail="clip not found")
    return FileResponse(rec["p"], media_type="video/mp4")