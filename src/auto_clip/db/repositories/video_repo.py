import hashlib
from neo4j import Driver
from auto_clip.core.config import settings
from auto_clip.models.video import VideoCreate

def _video_id(source_uri: str) -> str:
    return hashlib.sha256(source_uri.encode()).hexdigest()[:16]

def create_video(driver: Driver, data: VideoCreate) -> str:
    video_id = _video_id(data.source_uri)
    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            """
            MERGE (v:Video {id: $id})
            ON CREATE SET v.source_uri = $source_uri,
                          v.title = $title,
                          v.language = $language,
                          v.duration_s = $duration_s,
                          v.created_at = timestamp()
            """,
            id=video_id,
            source_uri=data.source_uri,
            title=data.title,
            language=data.language,
            duration_s=data.duration_s,
        )
    return video_id

def get_video(driver: Driver, video_id: str) -> dict | None:
    with driver.session(database=settings.neo4j_database) as session:
        record = session.run("MATCH (v:Video {id: $id}) RETURN v", id=video_id).single()
        return dict(record["v"]) if record else None
    
def set_video_status(driver: Driver, video_id: str, status: str, audio_path: str | None = None, error: str | None = None) -> None:
    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            """
            MATCH (v:Video {id:$id})
            SET v.status = $status,
                v.audio_path = $audio_path,
                v.error = $error,
                v.updated_at = timestamp()
            """,
            id=video_id, status=status, audio_path=audio_path, error=error,
        )