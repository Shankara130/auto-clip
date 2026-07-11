from pydantic import BaseModel, Field

class SegmentCreate(BaseModel):
    ordinal: int = Field(ge=0)
    start_s: float = Field(ge=0)
    end_s: float = Field(ge=0)
    text: str