from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    app_name: str = "auto-clip"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "autoclipdev"
    neo4j_database: str = "neo4j"

settings = Settings()