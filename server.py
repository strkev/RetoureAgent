"""
server.py
FastAPI-Einstiegspunkt für das Retourensupport-System.
Routet Anfragen über modulare Router (Chat, Returns, Auth, System)
und liefert statische Frontend-Dateien aus.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes import auth_router, chat_router, returns_router, system_router
from session_manager import sessions, SessionManager
from payload_helpers import build_chat_response_payload, format_action_card

app = FastAPI(title="Retourensupport API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router einbinden
app.include_router(chat_router)
app.include_router(returns_router)
app.include_router(auth_router)
app.include_router(system_router)

# Statische Dateien mounten
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

__all__ = [
    "app",
    "sessions",
    "SessionManager",
    "build_chat_response_payload",
    "format_action_card",
]
