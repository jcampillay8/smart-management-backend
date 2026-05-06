# src/ai_management/client.py
import os
import time
from typing import Any
from google import genai
from google.genai import types
from .schemas import AIResponse

async def call_gemini_api(
    system_instruction: str,
    user_prompt: str,
    model_cfg: Any, # Viene de la DB (AIModelConfig)
    temperature: float = 0.7,
    expect_json: bool = False 
) -> AIResponse:
    """Llamada directa a la API de Gemini con cálculo de costos dinámico."""
    
    start_time = time.monotonic()
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )
    if expect_json:
        config.response_mime_type = "application/json"
    
    try:
        async with client.aio as aclient:
            # Ejecución única con timeout (el SDK nuevo maneja timeouts de forma distinta, pero por ahora lo dejamos así)
            response = await aclient.models.generate_content(
                model=model_cfg.model_name,
                contents=user_prompt,
                config=config
            )
            
            content = response.text
            
            # Metadatos de tokens
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count if usage else 0
            output_tokens = usage.candidates_token_count if usage else 0
            
    except Exception as e:
        content = f"Error: {str(e)}"
        if expect_json:
            content = "{}"
        input_tokens = 0
        output_tokens = 0
    
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