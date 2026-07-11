from pydantic import BaseModel, Field

class VideoCreate(BaseModel):
    source_uri: str
    title: str
    language: str = "en"
    duration_s: int = Field(default=0, ge=0) # ge = ">= 0" (validasi!)