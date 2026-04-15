# src/authentication/dependencies.py
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_session
from src.dependencies import get_current_user

# ELIMINA la importación de User y RegistroStock de la parte superior
# from src.authentication.models import User  <-- QUITAR
# from src.operations.models import RegistroStock <-- QUITAR

async def get_valid_record_for_modification(
    record_id: UUID, 
    db: AsyncSession = Depends(get_async_session),
    current_user: "User" = Depends(get_current_user) # Usa comillas aquí
) -> "RegistroStock": # Usa comillas aquí
    
    # IMPORTACIÓN LOCAL (Rompe el círculo)
    from src.operations.models import RegistroStock
    
    record = await db.get(RegistroStock, record_id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Registro no encontrado"
        )
    
    # Si validate_modification_window no está, coméntalo por ahora para probar Postman
    # validate_modification_window(record, current_user.role)
    
    return record