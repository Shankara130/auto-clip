from neo4j import Driver
from auto_clip.core.config import settings

def create_clip(driver: Driver, segment_id: str, render_path: str, start_s: float, end_s: float, aspect: str = "original") -> str:
    clip_id = f"clip:{segment_id}"
    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            """
            MATCH (s:Segment {id: $segment_id})
            MERGE (c:Clip {id: $clip_id})
            ON CREATE SET c.start_s = $start_s,
                          c.end_s = $end_s,
                          c.render_path = $render_path,
                          c.aspect = $aspect,
                          c.status = "rendered",
                          c.created_at = timestamp()
            MERGE (c)-[:DERIVED_FROM]->(s)
            """,
            segment_id=segment_id, clip_id=clip_id,
            start_s=start_s, end_s=end_s, render_path=render_path,
            aspect=aspect
        )
    return clip_id