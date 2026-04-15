# src/authentication/dependencies.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_async_session
from src.dependencies import get_current_user # Tu dependencia de auth

async def get_valid_record_for_modification(
    record_id: UUID, 
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
) -> RegistroStock:
    # En async, usamos .get() pero con await
    record = await db.get(RegistroStock, record_id)
    
    if not record:
        raise HTTPException(status_code=404, detail="Registro no encontrado")
    
    # La lógica de fechas sigue siendo síncrona (es cálculo interno)
    validate_modification_window(record, current_user.role)
    
    return record