"""
graph/nodes_user_data.py
Behandlung von Anfragen zur Anpassung von Nutzerdaten (z. B. Adress- oder Stammdatenänderung).
"""

from typing import Any, Dict
from langchain_core.messages import AIMessage

from models import AgentState
import i18n
from .utils import log_action, log_node


def node_user_data(state: AgentState) -> Dict[str, Any]:
    """
    Behandelt Anfragen zur Anpassung von Kundendaten.
    Prüft, ob der Kunde im Kundenkonto authentifiziert ist:
    - Nicht angemeldet: Fordert über ein interaktives Login-Widget zur Anmeldung auf (Zero-LLM-Leakage).
    - Bereits angemeldet: Zeigt die bearbeitbaren Stammdaten an. Anmeldedaten sind geschützt.
    """
    log_node("node_user_data", "Verarbeite Anfrage zur Nutzerdatenanpassung...")
    logs = ["[LOG][NODE][node_user_data] Verarbeite Anfrage zur Nutzerdatenanpassung..."]
    lang = state.language or i18n.DEFAULT_LANGUAGE

    if not state.account_authenticated:
        response_text = i18n.get_text("user_data_login_prompt", lang=lang)
        log_action("AUTH_WIDGET_REQUESTED", f"Login-Widget für Kundenkonto angefordert (Sprache: {lang}).")
        logs.append(f"[LOG][ACTION][AUTH_WIDGET_REQUESTED] Login-Widget für Kundenkonto angefordert ({lang}).")
        return {
            "messages": [AIMessage(content=response_text)],
            "auth_widget_requested": True,
            "next_step": "wait_for_input",
            "last_active_node": "node_user_data",
            "execution_logs": logs,
        }
    else:
        acc = state.account_data or {}
        name = acc.get("name", "")
        nachname = acc.get("nachname", "")
        account_id = acc.get("account_id", state.account_id or "")

        response_text = i18n.get_text(
            "user_data_authenticated",
            lang=lang,
            name=name,
            nachname=nachname,
            account_id=account_id
        )
        log_action("USER_DATA_VIEWED", f"Profildaten für {account_id} angezeigt (Sprache: {lang}).")
        logs.append(f"[LOG][ACTION][USER_DATA_VIEWED] Profildaten für {account_id} angezeigt ({lang}).")
        return {
            "messages": [AIMessage(content=response_text)],
            "auth_widget_requested": False,
            "next_step": "wait_for_input",
            "last_active_node": "node_user_data",
            "execution_logs": logs,
        }

