# src/purchases/ai_service.py
import os
import json
import base64
from google import genai
from google.genai import types
from typing import List, Dict, Any
from json_repair import repair_json as repair

async def scan_invoice_ai(image_base64: str, mime_type: str) -> Dict[str, Any]:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    system_prompt = """You are an invoice/receipt OCR system. Extract product lines from the image.
Return a JSON object with a 'products' key containing an array of objects with these fields:
- nombre: product name (string)
- cantidad: quantity (number)
- precio: unit price (number)
- iva_incluido: whether the price includes VAT (boolean, usually false for Chilean invoices where IVA is separate at bottom)

Rules:
- Extract ALL product lines visible
- Prices should be numeric (no currency symbols)
- If quantity is not visible, default to 1
- For Chilean invoices (facturas), prices are typically NET (without IVA), so iva_incluido should be false
- Return ONLY valid JSON."""

    image_data = base64.b64decode(image_base64)
    
    try:
        async with client.aio as aclient:
            response = await aclient.models.generate_content(
                model="gemini-1.5-flash",
                contents=[
                    system_prompt,
                    types.Part.from_bytes(data=image_data, mime_type=mime_type),
                    "Extract all products from this invoice/receipt."
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            
            content = response.text
            parsed = json.loads(repair(content))
            return parsed
    except Exception as e:
        print(f"AI Scan Error: {e}")
        return {"products": [], "error": str(e)}

async def scan_recipe_ai(image_base64: str, mime_type: str) -> Dict[str, Any]:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    
    system_prompt = """You are a recipe OCR system. Extract ingredients and recipe name from the image.
Return a JSON object with:
- recipe_name: name of the recipe (string)
- ingredients: array of objects with:
    - nombre: ingredient name (string)
    - cantidad: quantity (number)
    - unidad: unit (string, e.g., gr, kg, l, ml, unidad)

Return ONLY valid JSON."""

    image_data = base64.b64decode(image_base64)
    
    try:
        async with client.aio as aclient:
            response = await aclient.models.generate_content(
                model="gemini-1.5-flash",
                contents=[
                    system_prompt,
                    types.Part.from_bytes(data=image_data, mime_type=mime_type),
                    "Extract recipe name and ingredients from this image."
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                )
            )
            
            content = response.text
            parsed = json.loads(repair(content))
            return parsed
    except Exception as e:
        print(f"AI Recipe Scan Error: {e}")
        return {"ingredients": [], "error": str(e)}
