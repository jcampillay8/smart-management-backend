# src/ai_management/router.py
from fastapi import APIRouter, Depends
from src.purchases import schemas
from src.purchases.ai_service import scan_recipe_ai
from src.dependencies import get_current_user
from src.models import User

router = APIRouter(prefix="/ai", tags=["AI"])

@router.post("/scan-recipe")
async def scan_recipe(
    request: schemas.ScanRecipeRequest,
    current_user: User = Depends(get_current_user)
):
    return await scan_recipe_ai(request.imageBase64, request.mimeType)
