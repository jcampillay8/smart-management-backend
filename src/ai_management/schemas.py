# src/ai_management/schemas.py
from pydantic import BaseModel, Field
from typing import Optional

class AIResponse(BaseModel):
    """Metadatos técnicos de la respuesta de la IA (Capa de Infraestructura)"""
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    duration_ms: int

class EvaluationResponse(BaseModel):
    """
    Estructura esperada dentro del JSON generado por la IA (Capa de Negocio).
    Se usa junto con json-repair para validar el contenido de writing/speaking.
    """
    score: float = Field(..., ge=0, le=100) # Valida que sea 0-100
    feedback: str
    detected_level: str = Field(..., pattern="^(A1|A2|B1|B2|C1|C2)$")