from neo4j import Driver
from auto_clip.core.config import settings

def link_entity(driver: Driver, segment_id: str, name: str) -> None:
    eid = name.lower().replace(" ", "_")
    with driver.session(database=settings.neo4j_database) as session:
        session.run(
            """
            MATCH (s:Segment {id: $sid})
            MERGE (e:Entity {id: $eid})
            ON CREATE SET e.name = $name, e.kind = "UNKNOWN"
            MERGE (s)-[:MENTIONS]->(e)
            """,
            sid=segment_id, eid=eid, name=name,
        )