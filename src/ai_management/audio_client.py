# src/ai_management/audio_client.py
import os
import base64
import json
import logging
from google.cloud import texttospeech
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

# Configuración de Voces Standard
STANDARD_VOICES = {
    "us_female": {
        "language_code": "en-US",
        "voice_name": "en-US-Standard-C",
        "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE
    },
    "us_male": {
        "language_code": "en-US",
        "voice_name": "en-US-Standard-B",
        "ssml_gender": texttospeech.SsmlVoiceGender.MALE
    },
    "uk_male": {
        "language_code": "en-GB",
        "voice_name": "en-GB-Standard-B",
        "ssml_gender": texttospeech.SsmlVoiceGender.MALE
    },
    "uk_female": {
        "language_code": "en-GB",
        "voice_name": "en-GB-Standard-A",
        "ssml_gender": texttospeech.SsmlVoiceGender.FEMALE
    }
}

class TTSClient:
    def __init__(self):
        self.client = self._init_client()

    def _init_client(self):
        """
        Inicializa el cliente de Google TTS. 
        Si existe la variable Base64, crea el archivo físico para evitar conflictos de Docker
        y lo usa para autenticar.
        """
        creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_BASE64")
        # Ruta donde Docker/Google esperan el archivo (definida en tu docker-compose)
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/app/google_credentials.json")

        if creds_b64:
            try:
                # 1. Decodificar
                creds_json_str = base64.b64decode(creds_b64).decode('utf-8')
                creds_info = json.loads(creds_json_str)

                # 2. ⚡ FIX CRÍTICO: Crear el archivo físico si no existe (o si es una carpeta por error de Docker)
                if os.path.isdir(creds_path):
                    logger.warning(f"Se detectó un directorio en {creds_path}. Eliminando para crear archivo...")
                    os.rmdir(creds_path) # Solo funciona si está vacío

                with open(creds_path, "w") as f:
                    f.write(creds_json_str)
                
                logger.info(f"✅ Credenciales materializadas en {creds_path}")

                # 3. Retornar cliente usando la info directamente
                return texttospeech.TextToSpeechClient(
                    credentials=Credentials.from_service_account_info(creds_info)
                )
            except Exception as e:
                logger.error(f"❌ Error initializing TTS with B64: {e}")
        
        # Fallback a Application Default Credentials
        return texttospeech.TextToSpeechClient()

    async def synthesize(self, text: str, voice_key: str = "us_female") -> bytes:
        """Sintetiza texto a audio MP3."""
        try:
            voice_cfg = STANDARD_VOICES.get(voice_key, STANDARD_VOICES["us_female"])
            
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code=voice_cfg["language_code"],
                name=voice_cfg["voice_name"],
                ssml_gender=voice_cfg["ssml_gender"]
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            # Ejecución síncrona (Google SDK no es nativamente async)
            response = self.client.synthesize_speech(
                input=synthesis_input, 
                voice=voice, 
                audio_config=audio_config
            )
            return response.audio_content
        except Exception as e:
            logger.error(f"Error en synthesize_speech: {e}")
            raise e

# Instancia global
tts_client = TTSClient()