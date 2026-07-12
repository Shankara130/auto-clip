from neo4j import Driver
from auto_clip.db.repositories.video_repo import set_video_status
from auto_clip.db.repositories.segment_repo import get_segments_by_video
from auto_clip.db.repositories.entity_repo import link_entity
from auto_clip.db.repositories.keyword_repo import link_keyword
from auto_clip.analysis.stub_analyser import analyze_text

def analyze_video(driver: Driver, video_id: str) -> int:
    """Analisis tiap segmen -> node Entity/Keyword + relasi"""
    try:
        set_video_status(driver, video_id, "analyzing")
        for seg in get_segments_by_video(driver, video_id):
            sid = seg["id"]
            result = analyze_text(seg.get("text", ""))
            for entity in result["entities"]:
                link_entity(driver, sid, entity)
            for kw in result["keywords"]:
                link_keyword(driver, sid, kw)
        set_video_status(driver, video_id, "analyzed")
        return len(get_segments_by_video(driver, video_id))
    except Exception as e:
        set_video_status(driver, video_id, "failed", error=str(e))
        raise