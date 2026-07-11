from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    app_name: str = "auto-clip"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

settings = Settings()