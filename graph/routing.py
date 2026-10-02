"""
graph/routing.py
Deterministische Routing-Funktionen für bedingte Kanten (Conditional Edges) im StateGraph.
"""

from typing import Literal
from models import AgentState
from .nodes_fulfillment import MAX_AUTH_ATTEMPTS


def route_after_input(state: AgentState) -> Literal["node_verify_auth", "node_agb_rag", "node_user_data", "node_escalate", "__end__"]:
    """Entscheidet nach der Eingabeanalyse über den nächsten Workflow-Schritt (Retouren-Auth, AGB-RAG, Nutzerdaten, Eskalation oder Warten)."""
    if state.next_step == "escalate":
        return "node_escalate"
    if state.next_step == "verify_auth":
        return "node_verify_auth"
    if state.next_step == "agb_rag":
        return "node_agb_rag"
    if state.next_step == "user_data":
        return "node_user_data"
    return "__end__"


def route_after_auth(state: AgentState) -> Literal["node_policy_check", "node_auth_retry", "node_escalate"]:
    """Entscheidet nach der Authentifizierung über Weiterleitung zu Policy-Prüfung, Retry oder Eskalation."""
    if state.auth_status:
        return "node_policy_check"
    if state.auth_attempts < MAX_AUTH_ATTEMPTS:
        return "node_auth_retry"
    return "node_escalate"


def route_after_policy(state: AgentState) -> Literal["node_book_return", "node_escalate", "__end__"]:
    """Entscheidet nach der Fristenprüfung über Retourenbuchung, Bestätigungswartezeit oder Frist-Eskalation."""
    if state.next_step == "escalate":
        return "node_escalate"
    if state.next_step == "book_return" or state.return_confirmed:
        return "node_book_return"
    return "__end__"
