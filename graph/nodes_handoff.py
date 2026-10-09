"""
graph/nodes_handoff.py
Erzeugung von Erfolgsbestätigungen und geordneter Human-in-the-Loop Eskalation inklusive Ticketing-Payload.
"""

import json
from typing import Any, Dict
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from models import AgentState, EscalationReason, HandoffPayload
import i18n
from .utils import clean_chat_output, log_action, log_node
from .nodes_fulfillment import MAX_AUTH_ATTEMPTS


def build_node_respond_success(active_llm):
    """Erstellt den Knoten zur Generierung der Erfolgsbestätigung nach erfolgreicher Retourenbuchung."""
    def node_respond_success(state: AgentState) -> Dict[str, Any]:
        log_node("node_respond_success", "Generiere Erfolgsnachricht für den Kunden...")
        logs = ["[LOG][NODE][node_respond_success] Generiere Erfolgsnachricht für den Kunden..."]

        booking = state.return_booking or {}
        return_type = booking.get("return_type", "refund")
        label_url = booking.get("label_url", "")
        return_id = booking.get("return_id", "")
        lang = state.language or i18n.DEFAULT_LANGUAGE

        is_refund = (return_type == "refund")
        policy_desc = (
            "full refund to original payment method"
            if is_refund else
            "store credit due to 15-30 days grace period"
        )

        prompt = [
            SystemMessage(content=(
                "Role: You are an e-commerce customer support chatbot chatting directly with the customer.\n"
                "The return was successfully booked in the backend.\n\n"
                f"LANGUAGE REQUIREMENT: You MUST reply directly in the customer's language ({lang.upper()}).\n\n"
                f"Booking details:\n"
                f"- Return-ID: {return_id}\n"
                f"- Return-Type: {return_type} ({policy_desc})\n"
                f"- Label-URL: {label_url}\n\n"
                "STRICT INSTRUCTIONS:\n"
                "1. Confirm the return warmly and clearly in the customer's language.\n"
                "2. State the Return-ID, the refund/store-credit modality, and provide the download link for the return label.\n"
                "3. OUTPUT ONLY the direct message text for the customer chat. NEVER include meta-comments, drafts, or headers."
            )),
            HumanMessage(content="Please confirm my return with the details.")
        ]

        response = active_llm.invoke(prompt)
        raw_content = response.content if isinstance(response.content, str) else str(response.content)
        content = clean_chat_output(raw_content)
        content = content.replace("{label_url}", label_url)

        cust_msg = f"Erfolgsnachricht gesendet (Länge: {len(content)} Zeichen, Sprache: {lang})."
        log_action("CUSTOMER_MESSAGE", cust_msg)
        logs.append(f"[LOG][ACTION][CUSTOMER_MESSAGE] {cust_msg}")

        return {
            "messages": [AIMessage(content=content)],
            "return_completed": True,
            "next_step": "END",
            "last_active_node": "node_respond_success",
            "execution_logs": logs,
        }

    return node_respond_success


def build_node_escalate(active_llm):
    """Erstellt den Knoten für den geordneten Human-in-the-Loop Handoff bei Fristablauf, Auth-Fehlversuchen oder Fehlern."""
    def node_escalate(state: AgentState) -> Dict[str, Any]:
        log_node("node_escalate", "Leite Human-in-the-Loop Eskalation ein...")
        logs = ["[LOG][NODE][node_escalate] Leite Human-in-the-Loop Eskalation ein..."]

        tools_locked = True
        lock_msg = "Schreibende Tools für die Session gesperrt."
        log_action("SECURITY_LOCK", lock_msg)
        logs.append(f"[LOG][ACTION][SECURITY_LOCK] {lock_msg}")

        lang = state.language or i18n.DEFAULT_LANGUAGE

        if not state.auth_status and state.auth_attempts >= MAX_AUTH_ATTEMPTS:
            reason = EscalationReason.AUTH_FAILED_MAX_ATTEMPTS
            recommended_action = i18n.get_text("recommended_action_auth", lang=lang, attempts=state.auth_attempts)
        elif state.order_data and state.order_data.get("days_since_purchase", 0) > 30:
            reason = EscalationReason.RETURN_DEADLINE_EXCEEDED
            days = state.order_data.get("days_since_purchase", 0)
            recommended_action = i18n.get_text("recommended_action_deadline", lang=lang, days=days)
        elif (state.emotional_messages_count or 0) >= 3 or state.is_frustrated:
            reason = EscalationReason.EMOTIONAL_ESCALATION
            recommended_action = i18n.get_text("recommended_action_emotional", lang=lang)
        else:
            reason = EscalationReason.SYSTEM_ERROR
            recommended_action = i18n.get_text("recommended_action_error", lang=lang)

        history_serialized = []
        dialog_text = ""
        for msg in state.messages:
            role = "customer" if isinstance(msg, HumanMessage) else "agent"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            history_serialized.append({"role": role, "content": content})
            dialog_text += f"{role.upper()}: {content}\n"

        summary_prompt = [
            SystemMessage(content=(
                "Summarize the customer's core problem and previous conversation concisely in 1-2 sentences "
                f"for an internal support ticket. Escalation reason: {reason.value}."
            )),
            HumanMessage(content=f"Dialog history:\n{dialog_text}")
        ]
        summary_response = active_llm.invoke(summary_prompt, config={"tags": ["internal_task"]})
        summary_text = summary_response.content if isinstance(summary_response.content, str) else str(summary_response.content)

        handoff = HandoffPayload(
            order_id=state.order_id,
            customer_email=state.email,
            escalation_reason=reason,
            summary=summary_text.strip(),
            recommended_action=recommended_action,
            chat_history=history_serialized,
        )

        customer_msg_prompt = [
            SystemMessage(content=(
                "Role: You are an empathetic customer support chatbot chatting directly with the customer.\n"
                f"LANGUAGE REQUIREMENT: You MUST reply directly in the customer's language ({lang.upper()}).\n"
                f"Reason for handoff: {reason.value}\n\n"
                "STRICT INSTRUCTIONS:\n"
                "1. Inform the customer kindly and transparently that their issue has been forwarded to a human colleague who will contact them shortly via email.\n"
                "2. Reassure the customer that we are handling their case with priority.\n"
                "3. OUTPUT ONLY the direct chat message to the customer. NEVER include meta-comments, drafts, or subject headers."
            )),
            HumanMessage(content="Please inform me about the handoff.")
        ]
        cust_response = active_llm.invoke(customer_msg_prompt)
        raw_cust = cust_response.content if isinstance(cust_response.content, str) else str(cust_response.content)
        customer_message_text = clean_chat_output(raw_cust)

        handoff_dict = json.loads(handoff.model_dump_json())
        print("\n" + "=" * 80)
        print(" [EVENT-LOG: HUMAN-IN-THE-LOOP TICKET HANDOFF PAYLOAD]")
        print("=" * 80)
        print(json.dumps(handoff_dict, indent=2, ensure_ascii=False))
        print("=" * 80 + "\n")

        emit_msg = f"Handoff-Ticket erzeugt. Case-ID: {handoff.case_id}, Grund: {reason.value}"
        log_action("HANDOFF_EMITTED", emit_msg)
        logs.append(f"[LOG][ACTION][HANDOFF_EMITTED] {emit_msg}")

        return {
            "tools_locked": tools_locked,
            "handoff_payload": handoff_dict,
            "messages": [AIMessage(content=customer_message_text)],
            "next_step": "END",
            "last_active_node": "node_escalate",
            "execution_logs": logs,
        }

    return node_escalate
