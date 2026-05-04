# src/notes/schemas.py
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from src.notes.models import UrgenciaNota


class NotaMencionOut(BaseModel):
    id: uuid.UUID
    user_id: int
    model_config = ConfigDict(from_attributes=True)


class AutorOut(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    nombre_visible: Optional[str] = None
    avatar_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class NotaCreate(BaseModel):
    titulo: Optional[str] = None
    contenido: str
    urgencia: UrgenciaNota = UrgenciaNota.MEDIA
    fecha: Optional[datetime] = None
    menciones: List[int] = []  # lista de user_ids mencionados


class NotaUpdate(BaseModel):
    titulo: Optional[str] = None
    contenido: Optional[str] = None
    urgencia: Optional[UrgenciaNota] = None
    fecha: Optional[datetime] = None
    menciones: Optional[List[int]] = None


class NotaOut(BaseModel):
    id: uuid.UUID
    autor_id: int
    titulo: Optional[str] = None
    contenido: str
    urgencia: UrgenciaNota
    fecha: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    autor: Optional[AutorOut] = None
    menciones: List[NotaMencionOut] = []
    model_config = ConfigDict(from_attributes=True)
