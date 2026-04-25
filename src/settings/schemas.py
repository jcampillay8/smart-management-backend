# src/settings/schemas.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID

class ConfiguracionRestauranteOut(BaseModel):
    id: UUID
    nombre: str
    logo_url: Optional[str] = None
    dias_alerta_vencimiento: float = 5.0
    
    model_config = ConfigDict(from_attributes=True)

class ConfiguracionRestauranteUpdate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    logo_url: Optional[str] = None
    dias_alerta_vencimiento: float = Field(default=5.0, ge=0)
