"""
routes/system.py
System-Endpunkte für Healthchecks, LLM-Verbindungstests, Session-Resets und statisches Frontend.
"""

from datetime import datetime
import os
from uuid import uuid4
from fastapi import APIRouter
from fastapi.responses import FileResponse

from api_schemas import ResetRequest, TestConnectionRequest
from session_manager import sessions
import i18n

WELCOME_TEXT = i18n.get_text("welcome_initial", lang="de")

router = APIRouter(tags=["system"])

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


@router.post("/api/test-connection")
async def test_connection_endpoint(req: TestConnectionRequest):
    """Testet die Verbindung zu einem externen LLM-Endpunkt (OpenAI/vLLM/Ollama)."""
    key = (req.api_key or "").strip()
    if not key:
        return {"success": False, "message": "API-Key darf nicht leer sein."}

    try:
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": (req.model or "gpt-4o-mini").strip(),
            "api_key": key,
            "max_tokens": 15,
            "timeout": 10.0,
        }
        if req.api_url and req.api_url.strip():
            kwargs["base_url"] = req.api_url.strip()

        client = ChatOpenAI(**kwargs)
        res = client.invoke("Antworte mit 'OK'.")
        return {"success": True, "message": f"Verbindung erfolgreich! Antwort: {res.content.strip()}"}
    except Exception as e:
        return {"success": False, "message": f"Verbindungsfehler: {str(e)}"}


@router.post("/api/reset")
async def reset_endpoint(req: ResetRequest):
    """Setzt den Konversationsverlauf und Agenten-State für eine Session zurück."""
    session_id = req.session_id or f"session-{uuid4().hex[:8]}"
    new_id, _, _ = sessions.reset(session_id)
    return {
        "session_id": new_id,
        "status": "reset_successful",
        "welcome_message": {
            "id": "msg-welcome",
            "role": "bot",
            "content": WELCOME_TEXT,
            "time": datetime.now().strftime("%H:%M")
        }
    }


@router.get("/api/health")
async def health_check():
    """Liveness- & Healthcheck-Endpunkt."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/")
async def serve_index():
    """Liefert die Hauptseite des Frontends aus."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "index.html nicht gefunden."}
