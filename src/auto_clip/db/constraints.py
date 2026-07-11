from neo4j import Driver
from auto_clip.core.config import settings

SCHEMA_CYPHER = [
    "CREATE CONSTRAINT video_id   IF NOT EXISTS FOR (v:Video) REQUIRE v.id IS UNIQUE",
    "CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE",
    "CREATE INDEX segment_video   IF NOT EXISTS FOR (s:Segment) ON (s.video_id)",
]

def init_schema(driver: Driver) -> None:
    with driver.session(database=settings.neo4j_database) as session:
        for cypher in SCHEMA_CYPHER:
            session.run(cypher)