from neo4j import Driver
from auto_clip.core.config import settings
from auto_clip.models.segment import SegmentCreate

def create_segment(driver: Driver, video_id: str, data: SegmentCreate) -> str:
    seg_id = f"{video_id}:{data.ordinal}"
    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            """
            MATCH (v:Video {id: $video_id})
            MERGE (s:Segment {id: $seg_id})
            ON CREATE SET s.ordinal = $ordinal,
                          s.start_s = $start_s,
                          s.end_s = $end_s,
                          s.text = $text
            MERGE (v)-[r:HAS_SEGMENT]->(s)
            ON CREATE SET r.ordinal = $ordinal
            """,
            video_id=video_id, seg_id=seg_id,
            ordinal=data.ordinal, start_s=data.start_s,
            end_s=data.end_s, text=data.text,
        )
    return seg_id

def get_segments_by_video(driver: Driver, video_id: str) -> list[dict]:
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(
            """
            MATCH (v:Video {id: $video_id})-[:HAS_SEGMENT]->(s:Segment)
            RETURN s
            ORDER BY s.ordinal
            """,
            video_id=video_id,
        )
        return [dict(record["s"]) for record in result]
