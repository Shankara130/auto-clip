from neo4j import Driver, GraphDatabase
from auto_clip.core.config import settings

_driver: Driver | None = None
def get_driver() -> Driver:
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
    return _driver

def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None

def ping() -> bool:
    with get_driver().session(database=settings.neo4j_database) as session:
        record = session.run("RETURN 1 AS n").single()
        return record is not None and record["n"] == 1