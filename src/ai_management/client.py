# src/ai_management/client.py
import os
import time
from typing import Any # Añadido
import google.generativeai as genai
from .schemas import AIResponse

# Configuración global de la API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

async def call_gemini_api(
    system_instruction: str,
    user_prompt: str,
    model_cfg: Any, # Viene de la DB (AIModelConfig)
    temperature: float = 0.7,
    expect_json: bool = False 
) -> AIResponse:
    """Llamada directa a la API de Gemini con cálculo de costos dinámico."""
    
    start_time = time.monotonic()
    
    # Usamos el nombre del modelo que viene de la DB
    model = genai.GenerativeModel(
        model_name=model_cfg.model_name,
        system_instruction=system_instruction
    )
    
    generation_config = {"temperature": temperature}
    if expect_json:
        generation_config["response_mime_type"] = "application/json"
    
    # Ejecución única con timeout
    response = await model.generate_content_async(
        user_prompt,
        generation_config=generation_config,
        request_options={"timeout": 60.0} 
    )
    
    # Manejo de seguridad (Safety Filter)
    try:
        content = response.text
    except ValueError:
        content = "{}" if expect_json else "Error: Respuesta bloqueada por filtros de seguridad."
    
    # Metadatos de tokens
    usage = response.usage_metadata
    input_tokens = getattr(usage, 'prompt_token_count', 0)
    output_tokens = getattr(usage, 'candidates_token_count', 0)
    
    # CÁLCULO DE COSTO usando los precios de la DB (model_cfg)
    cost = (input_tokens * (model_cfg.input_price_per_million / 1_000_000)) + \
           (output_tokens * (model_cfg.output_price_per_million / 1_000_000))
           
    return AIResponse(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        estimated_cost=cost,
        duration_ms=int((time.monotonic() - start_time) * 1000)
    )