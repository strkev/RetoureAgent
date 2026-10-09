"""
graph/nodes_agb.py
RAG-basierte Beantwortung von Kundenanfragen zu den Allgemeinen Geschäftsbedingungen (AGB).
"""

from typing import Any, Dict
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from models import AgentState
from rag import get_agb_retriever
import i18n
from .utils import clean_chat_output, log_action, log_node


def build_node_agb_rag(active_llm):
    """Erstellt den RAG-Knoten zur AGB-Auskunft."""
    def node_agb_rag(state: AgentState) -> Dict[str, Any]:
        log_node("node_agb_rag", "Beantworte Kundenfrage zu AGB / Shop-Richtlinien mittels RAG...")
        logs = ["[LOG][NODE][node_agb_rag] Beantworte Kundenfrage zu AGB / Richtlinien mittels RAG..."]

        # Letzte Nutzernachricht ermitteln
        user_question = ""
        for m in reversed(state.messages):
            if isinstance(m, HumanMessage):
                user_question = str(m.content)
                break
            elif isinstance(m, dict) and m.get("role") in ["user", "human"]:
                user_question = str(m.get("content", ""))
                break

        lang = state.language or i18n.DEFAULT_LANGUAGE

        # Retrieval ausführen
        retriever = get_agb_retriever()
        docs = retriever.invoke(user_question)

        context_text = ""
        for d in docs:
            title = d.metadata.get("title", "")
            context_text += f"\n--- {title} ---\n{d.page_content}\n"

        retrieved_titles = [d.metadata.get("title", "") for d in docs]
        log_action("AGB_RETRIEVAL", f"Relevante AGB-Paragraphen abgerufen: {retrieved_titles}")
        logs.append(f"[LOG][ACTION][AGB_RETRIEVAL] Relevante Abschnitte: {retrieved_titles}")

        prompt = [
            SystemMessage(content=(
                "Role: You are an expert e-commerce customer support chatbot chatting directly with the customer.\n"
                f"LANGUAGE REQUIREMENT: You MUST reply directly in the customer's language ({lang.upper()}).\n\n"
                "OFFICIAL TERMS & CONDITIONS (AGB) CONTEXT:\n"
                f"{context_text}\n\n"
                "INSTRUCTIONS:\n"
                "1. Answer the customer's question directly, clearly and politely based on the provided AGB context.\n"
                "2. Reference the relevant section or paragraph (e.g. § 4 or § 6) if helpful.\n"
                "3. If the context does not answer the question, state politely what is known and offer further assistance.\n"
                "4. OUTPUT ONLY the direct customer reply. No meta-talk, headers, or draft notes."
            )),
            HumanMessage(content=user_question or "Welche Regelungen gelten?")
        ]

        response = active_llm.invoke(prompt)
        raw_content = response.content if isinstance(response.content, str) else str(response.content)
        content = clean_chat_output(raw_content)

        log_action("AGB_ANSWERED", f"Antwort aus AGB-Kontext generiert ({len(content)} Zeichen).")
        logs.append(f"[LOG][ACTION][AGB_ANSWERED] Antwort aus AGB-Kontext generiert ({len(content)} Zeichen).")

        return {
            "messages": [AIMessage(content=content)],
            "agb_context": docs,
            "next_step": "wait_for_input",
            "last_active_node": "node_agb_rag",
            "execution_logs": logs,
        }

    return node_agb_rag
