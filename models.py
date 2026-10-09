"""
models.py
Definiert alle Datenmodelle, Enums und den AgentState für den Kundenservice-Agenten.
"""

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class EscalationReason(str, Enum):
    """Mögliche Gründe für eine Eskalation an den menschlichen Support."""
    AUTH_FAILED_MAX_ATTEMPTS = "AUTH_FAILED_MAX_ATTEMPTS"
    RETURN_DEADLINE_EXCEEDED = "RETURN_DEADLINE_EXCEEDED"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    EMOTIONAL_ESCALATION = "EMOTIONAL_ESCALATION"


class HandoffPayload(BaseModel):
    """
    Strukturierter Payload für ein externes Ticketing-System (z. B. Zendesk, Salesforce).
    Wird bei einer geordneten Eskalation (Human-in-the-Loop Handoff) erzeugt.
    """
    case_id: UUID = Field(default_factory=uuid4, description="Eindeutige ID des Supportfalls")
    order_id: Optional[str] = Field(default=None, description="Bestellnummer (falls vorhanden)")
    customer_email: Optional[str] = Field(default=None, description="E-Mail-Adresse des Kunden")
    escalation_reason: EscalationReason = Field(..., description="Grund der Eskalation")
    summary: str = Field(..., description="LLM-Zusammenfassung des Dialogs und des Kernproblems")
    recommended_action: str = Field(..., description="Handlungsempfehlung für den Support-Agenten")
    chat_history: List[Dict[str, Any]] = Field(default_factory=list, description="Vollständiger Dialogverlauf")


class ExtractedReturnInfo(BaseModel):
    """
    Strukturierte semantische Ausgabe des LLM bei Intent- und Datenextraktion.
    Sprachunabhängig: Das LLM erkennt Sprache und Absicht semantisch.
    Kern-Intents: 'retoure', 'agb', 'nutzerdaten' (sowie 'greeting' und 'off_topic').
    """
    intent: Literal["retoure", "agb", "nutzerdaten", "return_request", "status_check", "greeting", "off_topic"] = Field(
        ...,
        description="Customer intent: 'retoure' (return/refund), 'agb' (questions about terms/policies), 'nutzerdaten' (updating user profile/address), 'greeting', or 'off_topic'"
    )
    language: Optional[str] = Field(
        default="de",
        description="Detected customer language (ISO 639-1 code, e.g. 'de', 'en')"
    )
    order_id: Optional[str] = Field(
        default=None,
        description="Extracted order ID (e.g. ORD-1001), null if not provided by customer"
    )
    email: Optional[str] = Field(
        default=None,
        description="Extracted email address, null if not provided by customer"
    )
    intent_confidence: Optional[float] = Field(
        default=None,
        description="Model's confidence in the classified intent, as a value between 0.0 and 1.0 (e.g. 0.95 = 95%)"
    )
    is_frustrated: bool = Field(
        default=False,
        description="Whether the customer expresses frustration, anger, or strong dissatisfaction"
    )


def combine_logs(left: List[str], right: List[str]) -> List[str]:
    """Hilfsfunktion zum Kombinieren von Execution-Logs in LangGraph State."""
    if not left:
        return list(right)
    if not right:
        return list(left)
    return list(left) + list(right)


class AgentState(BaseModel):
    """
    Zustand (State) des Kundenservice-Graphen.
    Pydantic-basierter State kompatibel mit LangGraph.
    """
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)
    order_id: Optional[str] = None
    email: Optional[str] = None
    auth_status: bool = False
    auth_attempts: int = 0
    language: str = "de"
    current_intent: Optional[str] = None
    agb_context: Optional[List[Document]] = None
    order_data: Optional[Dict[str, Any]] = None
    selected_items: Optional[List[str]] = None
    return_confirmed: bool = False
    pending_return_summary: Optional[Dict[str, Any]] = None
    return_booking: Optional[Dict[str, Any]] = None
    return_completed: bool = False
    handoff_payload: Optional[Dict[str, Any]] = None
    tools_locked: bool = False
    account_id: Optional[str] = None
    account_authenticated: bool = False
    account_data: Optional[Dict[str, Any]] = None
    auth_widget_requested: bool = False
    next_step: str = ""
    last_active_node: Optional[str] = None
    execution_logs: Annotated[List[str], combine_logs] = Field(default_factory=list)
    intent_confidence: Optional[float] = None
    emotional_messages_count: int = 0
    is_frustrated: bool = False


