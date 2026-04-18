# src/settings/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID

class ConfiguracionRestauranteOut(BaseModel):
    id: UUID
    nombre: str
    logo_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class ConfiguracionRestauranteUpdate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
