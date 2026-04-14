# src/utils.py
import bcrypt # <-- Nueva importación para bcrypt
from uuid import UUID
import redis.asyncio as aioredis
import difflib
from typing import List, Dict, Any

# Se eliminan las siguientes líneas que usaban passlib:
# from passlib.context import CryptContext
# password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

from src.models import User # Mantener si es necesario para otras funciones como clear_cache_for_get_direct_chats

def get_hashed_password(password: str) -> str:
    """
    Hashea una contraseña usando bcrypt.
    """
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8') # Decodifica a string para guardar en la DB

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica si una contraseña en texto plano coincide con un hash bcrypt.
    """
    plain_pwd_bytes = plain_password.encode('utf-8')
    hashed_pwd_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password=plain_pwd_bytes, hashed_password=hashed_pwd_bytes)

async def clear_cache_for_get_messages(cache: aioredis.Redis, chat_guid: UUID):
    pattern_for_get_messages = f"messages_{chat_guid}_*"
    keys_found = cache.scan_iter(match=pattern_for_get_messages)
    async for key in keys_found:
        await cache.delete(key)


async def clear_cache_for_get_direct_chats(cache: aioredis.Redis, user: User):
    pattern_for_get_direct_chats = f"direct_chats_{user.guid}"
    keys_found = cache.scan_iter(match=pattern_for_get_direct_chats)
    async for key in keys_found:
        await cache.delete(key)


async def clear_cache_for_all_users(cache: aioredis.Redis):
    keys_found = cache.scan_iter(match="*all_users")
    async for key in keys_found:
        await cache.delete(key)

def highlight_differences(original_text: str, corrected_text: str) -> List[Dict[str, Any]]:
    """
    Compara dos cadenas de texto y devuelve una lista de diccionarios
    que describen las diferencias palabra por palabra para su resaltado.

    Args:
        original_text (str): La cadena de texto original (ej. el mensaje del usuario).
        corrected_text (str): La cadena de texto corregida (ej. la versión de la IA).

    Returns:
        List[Dict[str, Any]]: Una lista de diccionarios, donde cada diccionario
                                tiene 'type' ('default', 'removed', 'added') y 'text'.
    """
    s = difflib.SequenceMatcher(None, original_text.split(), corrected_text.split())
    result = []
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == 'equal':
            # Palabras idénticas en ambas versiones
            for word in original_text.split()[i1:i2]:
                result.append({'type': 'default', 'text': word})
        elif tag == 'replace':
            # Palabras reemplazadas: marcamos las originales como eliminadas y las nuevas como añadidas
            for word in original_text.split()[i1:i2]:
                result.append({'type': 'removed', 'text': word})
            for word in corrected_text.split()[j1:j2]:
                result.append({'type': 'added', 'text': word})
        elif tag == 'delete':
            # Palabras presentes solo en el texto original (eliminadas en la corrección)
            for word in original_text.split()[i1:i2]:
                result.append({'type': 'removed', 'text': word})
        elif tag == 'insert':
            # Palabras presentes solo en el texto corregido (añadidas en la corrección)
            for word in corrected_text.split()[j1:j2]:
                result.append({'type': 'added', 'text': word})
    return result