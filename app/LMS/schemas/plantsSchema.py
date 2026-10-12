from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

# Data create karte waqt (Request Body)
class PlantCreate(BaseModel):
    plantName: str = Field(..., min_length=1, max_length=150, description="Plant name")

# Data update karte waqt
class PlantUpdate(BaseModel):
    plantName: Optional[str] = Field(None, min_length=1, max_length=150, description="Updated plant name")

# API se response bhejte waqt
class PlantResponse(BaseModel):
    id: int
    plantName: str

    model_config = ConfigDict(from_attributes=True)
