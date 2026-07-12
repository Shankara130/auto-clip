from neo4j import Driver
from auto_clip.core.config import settings

def score_and_rank(driver: Driver, video_id: str) -> list[dict]:
    """Skor tiap segmen by graph features. Simpan graph_score. Return ranked"""
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(
            """
            MATCH (v:Video {id: $vid})-[:HAS_SEGMENT]->(s:Segment)
            OPTIONAL MATCH (s)-[:MENTIONS]->(e:Entity)
            WITH s, count(DISTINCT e) AS numEntities
            OPTIONAL MATCH (s)-[:MENTIONS]->(shared:Entity)<-[:MENTIONS]-(other:Segment)
            WITH s, numEntities, count(DISTINCT other) AS entityReach
            OPTIONAL MATCH (s)-[:HAS_KEYWORD]->(k:Keyword)
            WITH s, numEntities, entityReach, count(DISTINCT k) AS numKeywords
            WITH s, numEntities, entityReach, numKeywords, numEntities + numKeywords + entityReach AS graphScore
            SET s.graph_score = graphScore
            RETURN s.id AS id, s.ordinal AS ordinal, s.text AS text, graphScore, entityReach, numEntities, numKeywords
            ORDER BY graphScore DESC, s.ordinal
            """,
            vid=video_id,
        )   
        return [dict(r) for r in result]

def recommend(driver: Driver, video_id: str, k: int = 3) -> list[dict]:
    top = score_and_rank(driver, video_id)[:k]
    for seg in top:
        seg["reasons"] = [
            f"mentions {seg['numEntities']} entities",
            f"{seg['numKeywords']} keywords (info density)",
            f"entity reach: {seg['entityReach']}",
        ]
    return top
