# src/ai_management/services.py
import asyncio
import logging
import json
import time
from typing import Optional, List, Dict
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from json_repair import repair_json as repair

from .client import call_gemini_api
from .models import LLMRequestLog, AIModelConfig, AudioServiceConfig, AudioRequestLog
from .schemas import AIResponse
from .audio_client import tts_client

logger = logging.getLogger(__name__)

async def ask_oppy_ai(
    db: AsyncSession,
    messages: List[Dict[str, str]],
    user_id: int,
    caller: str,
    model_name: Optional[str] = None,
    expect_json: bool = False,
    retries: int = 2,
    temperature: float = 0.7,
    **kwargs
) -> str:
    """
    Orquestador de IA Evolucionado:
    - Procesa historial de mensajes (System/User/Assistant).
    - Configuración dinámica vía base de datos.
    - Reintentos con backoff exponencial.
    - Registro de métricas y costos (uso de flush para seguridad transaccional).
    """
    attempt = 0
    last_error = None

    # 1. Obtener la configuración del modelo desde la DB
    try:
        query = select(AIModelConfig).where(AIModelConfig.is_active == True)
        if model_name:
            query = query.where(AIModelConfig.model_name == model_name)
        else:
            query = query.where(AIModelConfig.is_default == True)
        
        result = await db.execute(query)
        model_cfg = result.scalar_one_or_none()
        
        if not model_cfg:
            raise ValueError(f"Configuración de IA '{model_name or 'Default'}' no encontrada.")
            
    except Exception as e:
        logger.error(f"Error crítico consultando AIModelConfig: {e}")
        return _fallback_message(expect_json)

    # 2. Preparar el contexto para la API de Gemini
    # Extraemos instrucciones de sistema y concatenamos el historial
    system_instruction = "\n".join([m["content"] for m in messages if m["role"] == "system"])
    user_prompts = [f"{m['role']}: {m['content']}" for m in messages if m["role"] != "system"]
    final_user_prompt = "\n".join(user_prompts)

    # 3. Bucle de ejecución con reintentos
    while attempt <= retries:
        try:
            ai_res: AIResponse = await call_gemini_api(
                system_instruction=system_instruction,
                user_prompt=final_user_prompt,
                model_cfg=model_cfg,
                temperature=temperature,
                expect_json=expect_json
            )

            # Reparación de JSON si es necesario
            final_content = ai_res.content
            if expect_json:
                final_content = repair(ai_res.content)

            # 4. Registrar éxito
            log = LLMRequestLog(
                user_id=user_id,
                caller=caller,
                model_name=model_cfg.model_name,
                input_tokens=ai_res.input_tokens,
                output_tokens=ai_res.output_tokens,
                total_tokens=ai_res.total_tokens,
                estimated_cost=ai_res.estimated_cost,
                request_duration_ms=ai_res.duration_ms,
                api_success=True,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            db.add(log)
            # Flush para que el log se envíe pero dependa del commit del servicio padre
            await db.flush() 
            
            return final_content

        except Exception as e:
            attempt += 1
            last_error = str(e)
            logger.warning(f"Intento {attempt}/{retries+1} fallido para {caller}: {e}")
            
            if attempt <= retries:
                await asyncio.sleep(2 ** attempt)
            else:
                # 5. Registro de fallo final
                log = LLMRequestLog(
                    user_id=user_id,
                    caller=caller,
                    model_name=model_cfg.model_name,
                    api_success=False,
                    error_message=last_error,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    estimated_cost=0.0,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                db.add(log)
                await db.flush()
                break
                
    return _fallback_message(expect_json)

def _fallback_message(expect_json: bool) -> str:
    if expect_json:
        return json.dumps({
            "error": "service_unavailable", 
            "message": "No se pudo obtener una respuesta válida.",
            "score": 0,
            "feedback": "Error de conexión con el motor de análisis."
        })
    return "Lo siento, tuve un problema técnico al conectar con mi cerebro. ¿Podrías repetir eso?"

async def generate_oppy_voice(
    db: AsyncSession,
    text: str,
    user_id: int,
    caller: str,
    voice_key: str = "us_female"
) -> bytes:
    """Genera audio y registra métricas/costos."""
    start_time = time.monotonic()
    
    stmt = select(AudioServiceConfig).where(
        AudioServiceConfig.service_name == "google_tts_standard",
        AudioServiceConfig.is_active == True
    )
    
    try:
        result = await db.execute(stmt)
        cfg = result.scalar_one_or_none()
        price_per_million = cfg.price_per_million if cfg else 4.0
        
        audio_content = await tts_client.synthesize(text, voice_key)
        
        duration_ms = int((time.monotonic() - start_time) * 1000)
        char_count = len(text)
        
        log = AudioRequestLog(
            user_id=user_id,
            caller=caller,
            service_name="google_tts_standard",
            input_units=char_count,
            estimated_cost=char_count * (price_per_million / 1_000_000),
            request_duration_ms=duration_ms,
            api_success=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(log)
        await db.flush()
        
        return audio_content

    except Exception as e:
        logger.error(f"Error en TTS Service: {e}")
        error_log = AudioRequestLog(
            user_id=user_id,
            caller=caller,
            service_name="google_tts_standard",
            api_success=False,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        db.add(error_log)
        await db.flush()
        return b""