"""
graph/nodes_fulfillment.py
Geschäftslogik für Authentifizierung, Fristen-/Policy-Prüfung und Retourenbuchung.
"""

from typing import Any, Dict
from langchain_core.messages import AIMessage

from models import AgentState
from repository import get_repository
import i18n
from .utils import log_action, log_node

# Singleton Mock-Repository und Konfiguration
repository = get_repository()
MAX_AUTH_ATTEMPTS = 3


def node_verify_auth(state: AgentState) -> Dict[str, Any]:
    """Prüft Authentizität von Bestellnummer und E-Mail-Adresse im Backend-Repository."""
    log_node("node_verify_auth", "Prüfe Authentizität von Bestellnummer und E-Mail-Adresse...")
    order_id = state.order_id or ""
    email = state.email or ""
    current_attempts = state.auth_attempts
    logs = ["[LOG][NODE][node_verify_auth] Prüfe Authentizität von Bestellnummer und E-Mail-Adresse..."]

    is_valid = repository.verify_order(order_id, email)

    if is_valid:
        auth_msg = f"Bestellung {order_id} erfolgreich authentifiziert für {email}."
        log_action("AUTH_SUCCESS", auth_msg)
        logs.append(f"[LOG][ACTION][AUTH_SUCCESS] {auth_msg}")
        return {
            "auth_status": True,
            "next_step": "policy_check",
            "last_active_node": "node_verify_auth",
            "execution_logs": logs,
        }
    else:
        new_attempts = current_attempts + 1
        fail_msg = (
            f"Authentifizierung fehlgeschlagen für {order_id} / {email}. "
            f"Fehlversuche: {new_attempts}/{MAX_AUTH_ATTEMPTS}"
        )
        log_action("AUTH_FAILED", fail_msg)
        logs.append(f"[LOG][ACTION][AUTH_FAILED] {fail_msg}")
        return {
            "auth_status": False,
            "auth_attempts": new_attempts,
            "next_step": "auth_failed",
            "last_active_node": "node_verify_auth",
            "execution_logs": logs,
        }


def node_auth_retry(state: AgentState) -> Dict[str, Any]:
    """Fordert den Kunden zur erneuten Eingabe der Zugangsdaten auf."""
    log_node("node_auth_retry", "Sende Aufforderung zur erneuten Eingabe...")
    logs = ["[LOG][NODE][node_auth_retry] Sende Aufforderung zur erneuten Eingabe..."]
    attempts = state.auth_attempts
    lang = state.language or i18n.DEFAULT_LANGUAGE
    retry_message = AIMessage(
        content=i18n.get_text(
            "auth_retry",
            lang=lang,
            attempt=attempts,
            max_attempts=MAX_AUTH_ATTEMPTS
        )
    )
    return {
        "messages": [retry_message],
        "next_step": "wait_for_input",
        "last_active_node": "node_auth_retry",
        "execution_logs": logs,
    }


def node_policy_check(state: AgentState) -> Dict[str, Any]:
    """Ermittelt Bestelldaten und prüft die Rückgabefristen (14 Tage / 30 Tage)."""
    log_node("node_policy_check", "Ermittle Bestelldaten und prüfe Rückgabefristen...")
    order_id = state.order_id or ""
    order_details = repository.get_order_details(order_id)
    logs = ["[LOG][NODE][node_policy_check] Ermittle Bestelldaten und prüfe Rückgabefristen..."]

    if not order_details:
        log_action("POLICY_ERROR", f"Keine Bestelldaten für {order_id} gefunden.")
        logs.append(f"[LOG][ACTION][POLICY_ERROR] Keine Bestelldaten für {order_id} gefunden.")
        return {
            "order_data": None,
            "next_step": "escalate",
            "last_active_node": "node_policy_check",
            "execution_logs": logs,
        }

    days = order_details["days_since_purchase"]
    eval_msg = f"Bestellung {order_id}: Kauf liegt {days} Tage zurück."
    log_action("POLICY_EVALUATION", eval_msg)
    logs.append(f"[LOG][ACTION][POLICY_EVALUATION] {eval_msg}")

    if days <= 14:
        return_type = "refund"
        policy_label = "<= 14 Tage (Volle Erstattung)"
        dec_msg = f"Kaufdatum <= 14 Tage ({days} Tage) -> Berechtigt für volle Rückerstattung (refund)."
    elif days <= 30:
        return_type = "store_credit"
        policy_label = "15-30 Tage Kulanzfrist (Store Credit)"
        dec_msg = f"Kaufdatum 15-30 Tage ({days} Tage) -> Kulanzfrist: Berechtigt für Store-Guthaben (store_credit)."
    else:
        dec_msg = f"Kaufdatum > 30 Tage ({days} Tage) -> Reguläre Frist abgelaufen. Eskalation erforderlich."
        log_action("POLICY_DECISION", dec_msg)
        logs.append(f"[LOG][ACTION][POLICY_DECISION] {dec_msg}")
        order_details["policy"] = "> 30 Tage Frist abgelaufen"
        return {
            "order_data": order_details,
            "next_step": "escalate",
            "last_active_node": "node_policy_check",
            "execution_logs": logs,
        }

    log_action("POLICY_DECISION", dec_msg)
    logs.append(f"[LOG][ACTION][POLICY_DECISION] {dec_msg}")
    order_details["return_type"] = return_type
    order_details["policy"] = policy_label

    # Falls Retoure bereits bestätigt ist (z. B. durch Button-Klick oder Chat-Bestätigung)
    if state.return_confirmed:
        return {
            "order_data": order_details,
            "next_step": "book_return",
            "last_active_node": "node_policy_check",
            "execution_logs": logs,
        }

    # Noch nicht bestätigt -> Zusammenfassung generieren und auf Nutzerbestätigung warten
    lang = state.language or i18n.DEFAULT_LANGUAGE
    items = order_details.get("items", [])

    if lang == "en":
        modality_text = (
            "100% full refund to original payment method (14-day statutory return period)"
            if return_type == "refund"
            else "Store credit voucher (15-30 days goodwill grace period)"
        )
        items_text = "\n".join([
            f"- **{it['name']}** (€{it['price']:.2f})" if isinstance(it, dict) else f"- **{it}**"
            for it in items
        ])
        summary_msg = (
            f"Your order **{order_id}** was found.\n\n"
            f"**Refund modality:** {modality_text}\n\n"
            f"**Available items for return:**\n{items_text}\n\n"
            "Please select which items you would like to return below and confirm your return."
        )
    else:
        modality_text = (
            "100% Kaufpreiserstattung auf das ursprüngliche Zahlungsmittel (14 Tage gesetzliches Widerrufsrecht)"
            if return_type == "refund"
            else "Warengutschein (Store Credit), da der Kauf zwischen 15 und 30 Tagen zurückliegt (Kulanzzeitraum)"
        )
        items_text = "\n".join([
            f"- **{it['name']}** ({it['price']:.2f} €)" if isinstance(it, dict) else f"- **{it}**"
            for it in items
        ])
        summary_msg = (
            f"Ihre Bestellung **{order_id}** wurde gefunden.\n\n"
            f"**Erstattungsart:** {modality_text}\n\n"
            f"**Enthaltene Artikel:**\n{items_text}\n\n"
            "Sie können alle oder einzelne Produkte zurücksenden. Bitte wählen Sie die Artikel unten aus und bestätigen Sie die Retoure."
        )

    pending_summary = {
        "order_id": order_id,
        "return_type": return_type,
        "policy": policy_label,
        "items": items,
        "total_amount": order_details.get("total_amount", 0.0),
    }

    return {
        "order_data": order_details,
        "pending_return_summary": pending_summary,
        "messages": [AIMessage(content=summary_msg)],
        "next_step": "await_confirmation",
        "last_active_node": "node_policy_check",
        "execution_logs": logs,
    }


def node_book_return(state: AgentState) -> Dict[str, Any]:
    """Führt die Buchung der Retoure im ERP/Backend-System durch, sofern schreibende Tools nicht gesperrt sind."""
    log_node("node_book_return", "Führe Retourenbuchung im Backend durch...")
    logs = ["[LOG][NODE][node_book_return] Führe Retourenbuchung im Backend durch..."]

    if state.tools_locked:
        block_msg = "Schreibende Operation blockiert: Session befindet sich im Eskalationsstatus!"
        log_action("TOOL_BLOCKED", block_msg)
        logs.append(f"[LOG][ACTION][TOOL_BLOCKED] {block_msg}")
        return {
            "next_step": "escalate",
            "last_active_node": "node_book_return",
            "execution_logs": logs,
        }

    order_id = state.order_id or ""
    order_data = state.order_data or {}
    return_type = order_data.get("return_type", "refund")
    all_items = order_data.get("items", [])

    selected_ids = state.selected_items
    if selected_ids and len(selected_ids) > 0:
        returned_items = [
            it for it in all_items
            if (isinstance(it, dict) and (it.get("item_id") in selected_ids or it.get("name") in selected_ids))
            or (isinstance(it, str) and it in selected_ids)
        ]
        if not returned_items:
            returned_items = all_items
    else:
        returned_items = all_items

    booking_result = repository.book_return(order_id, return_type, returned_items)
    exec_msg = (
        f"Retoure erfolgreich gebucht: Return-ID={booking_result['return_id']}, "
        f"Art={booking_result['return_type']}, Artikel={len(returned_items)}, "
        f"Erstattung={booking_result['total_refund']:.2f} EUR, Label={booking_result['label_url']}"
    )
    log_action("TOOL_EXECUTION", exec_msg)
    logs.append(f"[LOG][ACTION][TOOL_EXECUTION] {exec_msg}")

    return {
        "return_booking": booking_result,
        "next_step": "respond_success",
        "last_active_node": "node_book_return",
        "execution_logs": logs,
    }
