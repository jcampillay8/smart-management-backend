# src/routers.py
from src.authentication.router import auth_router
from src.authentication.google_oauth_router import google_router
from src.authentication.user_details_router import user_details_router
from src.registration.router import account_router
from src.inventory.router import inventory_router
from src.operations.router import operations_router
from src.sales.router import sales_router

routers = [
    auth_router,
    google_router,
    user_details_router,
    account_router,
    inventory_router,
    operations_router,
    sales_router
]