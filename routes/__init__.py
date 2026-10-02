"""
routes/__init__.py
Zentrale Exportstelle für alle FastAPI-Router des Retourensupport-Backends.
"""

from routes.auth import router as auth_router
from routes.chat import router as chat_router
from routes.returns import router as returns_router
from routes.system import router as system_router

__all__ = [
    "auth_router",
    "chat_router",
    "returns_router",
    "system_router",
]
