"""
routes/auth.py
Endpunkte für sichere Authentifizierung (Login-Widget) und Aktualisierung von Stammdaten.
"""

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage

from api_schemas import AccountUpdateRequest, AuthLoginRequest, CancelAuthRequest
from payload_helpers import build_chat_response_payload
from repository import get_repository
from session_manager import sessions

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login")
async def auth_login_endpoint(req: AuthLoginRequest):
    """Authentifiziert Kundenkonto per Login & Passwort (Zero-LLM-Leakage)."""
    session_id, graph_app, _ = sessions.get_or_create(session_id=req.session_id)
    config = {"configurable": {"thread_id": session_id}}

    repo = get_repository()
    account = repo.authenticate_account(req.login, req.password)

    if not account:
        return {
            "success": False,
            "message": "Ungültige Anmeldedaten. Bitte prüfen Sie Ihre Eingaben."
        }

    login_confirm_msg = (
        f"Anmeldung erfolgreich! Willkommen zurück, {account['name']} {account['nachname']}.\n"
        f"Ihre Profildaten wurden geladen. Sie können Ihre Lieferadresse, Telefonnummer und Namen anpassen."
    )

    graph_app.update_state(
        config,
        {
            "messages": [AIMessage(content=login_confirm_msg)],
            "account_id": account["account_id"],
            "account_authenticated": True,
            "account_data": account,
            "auth_widget_requested": False,
            "email": account.get("email"),
            "current_intent": "nutzerdaten",
            "last_active_node": "node_user_data",
            "execution_logs": [
                f"[LOG][AUTH] Account {account['account_id']} erfolgreich authentifiziert.",
                f"[LOG][ACTION][USER_DATA_VIEWED] Profildaten geladen."
            ]
        }
    )

    st_val = graph_app.get_state(config).values
    resp = build_chat_response_payload(session_id, st_val)
    resp["success"] = True
    resp["account"] = account
    return resp


@router.post("/auth/cancel")
async def auth_cancel_endpoint(req: CancelAuthRequest):
    """Bricht das Login-Widget ab und blendet es aus."""
    session_id, graph_app, _ = sessions.get_or_create(session_id=req.session_id)
    config = {"configurable": {"thread_id": session_id}}
    graph_app.update_state(
        config,
        {
            "auth_widget_requested": False,
            "last_active_node": "node_user_data_dismissed",
            "execution_logs": ["[LOG][ACTION][AUTH_DISMISSED] Login-Widget vom Nutzer geschlossen."],
        }
    )
    return {"success": True}


@router.post("/account/update")
async def account_update_endpoint(req: AccountUpdateRequest):
    """Aktualisiert veränderliche Stammdaten (Adresse, Telefon, Name). Anmeldedaten sind geschützt."""
    session_id, graph_app, _ = sessions.get_or_create(session_id=req.session_id)
    config = {"configurable": {"thread_id": session_id}}

    st_val = graph_app.get_state(config).values
    if not st_val.get("account_authenticated") or not st_val.get("account_id"):
        raise HTTPException(status_code=401, detail="Nicht authentifiziert. Bitte melden Sie sich an.")

    account_id = st_val["account_id"]
    repo = get_repository()

    try:
        updated_account = repo.update_account_data(account_id, req.updates)
    except ValueError as e:
        return {
            "success": False,
            "message": str(e)
        }

    update_confirm_msg = (
        f"Ihre Profildaten wurden erfolgreich aktualisiert.\n"
        f"- Name: {updated_account['name']} {updated_account['nachname']}\n"
        f"- Adresse: {updated_account.get('adresse', '')}, {updated_account.get('land', '')}\n"
        f"- Telefon: {updated_account.get('telefonnummer', '')}"
    )

    graph_app.update_state(
        config,
        {
            "messages": [AIMessage(content=update_confirm_msg)],
            "account_data": updated_account,
            "current_intent": "nutzerdaten",
            "last_active_node": "node_account_updated",
            "execution_logs": [
                f"[LOG][UPDATE] Profildaten für Account {account_id} erfolgreich aktualisiert.",
            ]
        }
    )

    new_st = graph_app.get_state(config).values
    resp = build_chat_response_payload(session_id, new_st)
    resp["success"] = True
    resp["account"] = updated_account
    return resp
