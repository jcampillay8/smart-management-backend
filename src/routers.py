# src/routers.py
from src.authentication.router import auth_router
from src.authentication.google_oauth_router import google_router
from src.authentication.user_details_router import user_details_router
from src.registration.router import account_router

# Solo activamos lo necesario para el flujo inicial de Oppy2
routers = [
    auth_router,
    google_router,
    user_details_router,
    account_router
]