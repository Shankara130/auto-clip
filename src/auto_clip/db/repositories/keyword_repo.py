from neo4j import Driver
from auto_clip.core.config import settings
  
def link_keyword(driver: Driver, segment_id: str, keyword: str) -> None:
    kid = keyword.lower().replace(" ", "_")
    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            """
            MATCH (s:Segment {id: $sid})
            MERGE (k:Keyword {id: $kid})
            ON CREATE SET k.text = $keyword
            MERGE (s)-[:HAS_KEYWORD]->(k)
            """,
            sid=segment_id, kid=kid, keyword=keyword,
        )