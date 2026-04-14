# src/ai_management/config.py
from typing import Dict, Any

GEMINI_PRICING: Dict[str, Dict[str, Any]] = {
    "gemini-2.5-flash": {
        "input_price_per_million": 0.30,
        "output_price_per_million": 2.50,
    },
    "gemini-2.5-flash-lite": {
        "input_price_per_million": 0.10,
        "output_price_per_million": 0.40,
    }
}

# Configuración por defecto
DEFAULT_MODEL = "gemini-2.5-flash-lite"
GEMINI_TIMEOUT = 60.0