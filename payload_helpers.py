"""
payload_helpers.py
Formatierungsfunktionen für Action-Cards, State-Inspector-Metadaten
und standardisierte Frontend-JSON-Payloads.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from langchain_core.messages import HumanMessage
import i18n
from session_manager import sessions

WELCOME_TEXT = i18n.get_text("welcome_initial", lang="de")


def format_action_card(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Generiert spezifische interaktive Action-Cards basierend auf dem aktuellen State."""
    last_node = state.get("last_active_node")
    booking = state.get("return_booking")
    handoff = state.get("handoff_payload")
    auth_requested = state.get("auth_widget_requested", False)
    acc_auth = state.get("account_authenticated", False)
    current_intent = state.get("current_intent")

    # 0. Interaktive Produktauswahl & Retourenbestätigung (vor der finalen Buchung)
    if not state.get("return_completed") and state.get("next_step") == "await_confirmation" and last_node == "node_policy_check":
        order_data = state.get("order_data") or {}
        order_id = state.get("order_id", "")
        return_type = order_data.get("return_type", "refund")
        items = order_data.get("items", [])
        return {
            "type": "return_selection_confirm",
            "title": "Produktauswahl & Retoure bestätigen",
            "meta": f"Bestellung {order_id} · Bitte wählen Sie die gewünschten Artikel aus",
            "order_id": order_id,
            "return_type": return_type,
            "policy": order_data.get("policy", ""),
            "policy_desc": "Volle Rückerstattung (14-Tage-Frist)" if return_type == "refund" else "Store-Credit Warengutschein (15-30 Tage Kulanz)",
            "items": items,
            "badge": "Bestätigung erforderlich"
        }

    # 1. Retouren-Label & PDF-Beleg: Bei erfolgreicher Buchung
    if booking and last_node == "node_respond_success":
        ret_type = booking.get("return_type", "refund")
        ret_id = booking.get("return_id", "RET-XXXX")
        label_url = booking.get("label_url", f"/api/returns/{ret_id}/label.pdf")
        returned_items = booking.get("items", [])
        total_refund = booking.get("total_refund", 0.0)
        items_cnt = len(returned_items)

        if ret_type == "refund":
            return {
                "type": "return_booking_refund",
                "title": "Retourenschein & Label generiert (Erstattung)",
                "meta": f"ID: {ret_id} · {items_cnt} Artikel · Erstattung: {total_refund:.2f} €",
                "link_text": "Retourenschein herunterladen (PDF) →",
                "link_url": label_url,
                "badge": "Erstattung gebucht"
            }
        else:
            return {
                "type": "return_booking_credit",
                "title": "Gutschrift vorbereitet (Store Credits)",
                "meta": f"ID: {ret_id} · {items_cnt} Artikel · Guthaben: {total_refund:.2f} € (Kulanzzeitraum)",
                "link_text": "Retourenschein herunterladen (PDF) →",
                "link_url": label_url,
                "badge": "Store Credit aktiviert"
            }

    # 2. Eskalations-Ticket: NUR beim Eskalations-Knoten
    if handoff and last_node == "node_escalate":
        reason = handoff.get("escalation_reason", "SYSTEM_ERROR")
        case_id = str(handoff.get("case_id", ""))[:8]
        rec = handoff.get("recommended_action", "")
        return {
            "type": "handoff_escalation",
            "title": "Support-Ticket erstellt (Human-in-the-Loop)",
            "meta": f"Ticket #{case_id} · Grund: {reason}\nEmpfohlene Aktion: {rec}",
            "link_text": "Ticket-Details anzeigen →",
            "link_url": "#",
            "badge": "An Support übergeben"
        }

    # 3. Interaktives Login-Widget (Kundenkonto)
    if auth_requested and not acc_auth and current_intent == "nutzerdaten" and last_node == "node_user_data":
        return {
            "type": "account_login",
            "title": "Kundenkonto Anmeldung",
            "meta": "Melden Sie sich mit E-Mail oder Account-ID und Passwort an.",
            "badge": "Authentifizierung erforderlich"
        }

    # 4. Kundenkonto Profildaten anzeigen & bearbeiten
    if acc_auth and current_intent == "nutzerdaten" and last_node == "node_user_data":
        acc = state.get("account_data") or {}
        return {
            "type": "account_profile",
            "title": "Kundenkonto Profildaten",
            "meta": f"Account {acc.get('account_id', '')} · {acc.get('name', '')} {acc.get('nachname', '')}",
            "account": acc,
            "badge": "Angemeldet"
        }

    return None


def format_decision_logic(state_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extrahiert lesbare Entscheidungslogik für den State Inspector."""
    current_intent = state_result.get("current_intent")
    order_data = state_result.get("order_data")
    acc_auth = state_result.get("account_authenticated", False)
    account_id = state_result.get("account_id")

    handoff = state_result.get("handoff_payload")
    if handoff:
        reason = handoff.get("escalation_reason")
        return {
            "status": f"Eskaliert an Support ({reason})",
            "escalation_reason": reason,
            "case_id": str(handoff.get("case_id", ""))[:8],
            "recommended_action": handoff.get("recommended_action")
        }

    if current_intent == "agb":
        return {
            "intent": "agb",
            "rag_source": "data/agb.md",
            "retrieved_sections": [c.get("title") for c in (state_result.get("agb_context") or [])],
            "status": "Auskunft aus AGB-Dokument beantwortet"
        }
    if current_intent == "nutzerdaten":
        if acc_auth:
            return {
                "intent": "nutzerdaten",
                "account_id": account_id,
                "authenticated": True,
                "status": "Kundenkonto verifiziert · Profildaten freigegeben"
            }
        return {
            "intent": "nutzerdaten",
            "authenticated": False,
            "status": "Login-Widget angefordert (Zero-LLM-Leakage)"
        }
    if order_data:
        if state_result.get("next_step") == "await_confirmation":
            return {
                "intent": "retoure",
                "order_id": order_data.get("order_id"),
                "customer_email": order_data.get("customer_email"),
                "purchase_date": order_data.get("purchase_date"),
                "days_since_order": order_data.get("days_since_purchase"),
                "policy": order_data.get("policy", "Prüfung"),
                "return_type": order_data.get("return_type", "n/a"),
                "status": "Warte auf Bestätigung der Artikelauswahl durch Kunden"
            }
        return {
            "intent": "retoure",
            "order_id": order_data.get("order_id"),
            "customer_email": order_data.get("customer_email"),
            "purchase_date": order_data.get("purchase_date"),
            "days_since_order": order_data.get("days_since_purchase"),
            "policy": order_data.get("policy", "Prüfung"),
            "return_type": order_data.get("return_type", "n/a"),
        }
    if state_result.get("order_id"):
        return {
            "intent": "retoure",
            "order_id": state_result.get("order_id"),
            "customer_email": state_result.get("email"),
            "status": "In Verifizierung"
        }
    return {}


def format_tool_execution(state_result: Dict[str, Any]) -> str:
    """Formatiert Tool- und RAG-Aktivitäten für den State Inspector."""
    last_node = state_result.get("last_active_node")
    booking = state_result.get("return_booking")
    handoff = state_result.get("handoff_payload")

    if last_node == "node_agb_rag" and state_result.get("agb_context"):
        chunks_info = "\n".join([f"-> {c.get('title')} (Score: {c.get('score')})" for c in state_result["agb_context"]])
        return f"[RAG RETRIEVAL] AGB-Abschnitte aus data/agb.md geladen:\n{chunks_info}"

    if last_node == "node_respond_success" and booking:
        items_cnt = len(booking.get("items", []))
        return (
            f"[CALL] book_return(order_id=\"{booking.get('order_id')}\", return_type=\"{booking.get('return_type')}\", items={items_cnt})\n"
            f"-> Status: SUCCESS ({booking.get('status')})\n"
            f"-> Return-ID: {booking.get('return_id')}\n"
            f"-> Artikel retourniert: {items_cnt}\n"
            f"-> Erstattungsbetrag: {booking.get('total_refund', 0.0):.2f} EUR\n"
            f"-> Label-URL: {booking.get('label_url')}"
        )

    if handoff:
        return (
            f"[HANDOFF ESCALATION] Human-in-the-Loop eingeleitet!\n"
            f"-> Tools Locked: {state_result.get('tools_locked', True)}\n"
            f"-> Case-ID: {handoff.get('case_id')}\n"
            f"-> Reason: {handoff.get('escalation_reason')}\n"
            f"-> Recommended Action: {handoff.get('recommended_action')}\n"
            f"-> Summary: {handoff.get('summary')}"
        )

    return "Keine schreibenden Tool-Aufrufe aktiv."


def build_chat_response_payload(session_id: str, state_result: Dict[str, Any]) -> Dict[str, Any]:
    """Generiert konsistente JSON-Struktur für Frontend (Chat, Login, Profilupdate)."""
    now_str = datetime.now().strftime("%H:%M")
    start_time = sessions.start_times.get(session_id, now_str)

    chat_messages = [
        {
            "id": "msg-welcome",
            "role": "bot",
            "content": WELCOME_TEXT,
            "time": start_time,
            "action_card": None
        }
    ]

    messages_list = state_result.get("messages", [])
    for i, msg in enumerate(messages_list):
        is_user = isinstance(msg, HumanMessage)
        role = "user" if is_user else "bot"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)

        if not is_user and content.strip() == WELCOME_TEXT.strip():
            continue

        card = None
        if not is_user and i == len(messages_list) - 1:
            card = format_action_card(state_result)

        chat_messages.append({
            "id": f"msg-{len(chat_messages)}",
            "role": role,
            "content": content,
            "time": now_str,
            "action_card": card
        })

    response_state = {
        "order_id": state_result.get("order_id"),
        "email": state_result.get("email"),
        "current_intent": state_result.get("current_intent"),
        "agb_context": state_result.get("agb_context"),
        "auth_status": state_result.get("auth_status", False),
        "auth_attempts": state_result.get("auth_attempts", 0),
        "last_active_node": state_result.get("last_active_node", "node_process_input"),
        "next_step": state_result.get("next_step", ""),
        "tools_locked": state_result.get("tools_locked", False),
        "account_id": state_result.get("account_id"),
        "account_authenticated": state_result.get("account_authenticated", False),
        "account_data": state_result.get("account_data"),
        "auth_widget_requested": state_result.get("auth_widget_requested", False),
        "return_completed": state_result.get("return_completed", False),
        "selected_items": state_result.get("selected_items"),
        "return_confirmed": state_result.get("return_confirmed", False),
        "pending_return_summary": state_result.get("pending_return_summary"),
        "decision_logic": format_decision_logic(state_result),
        "tool_execution": format_tool_execution(state_result),
        "execution_logs": state_result.get("execution_logs", []),
        "handoff_payload": state_result.get("handoff_payload"),
        "return_booking": state_result.get("return_booking"),
        "intent_confidence": state_result.get("intent_confidence"),
        "emotional_messages_count": state_result.get("emotional_messages_count", 0),
        "is_frustrated": state_result.get("is_frustrated", False),
    }

    return {
        "session_id": session_id,
        "messages": chat_messages,
        "state": response_state,
    }
