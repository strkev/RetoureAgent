"""
graph/builder.py
Zusammensetzung und Kompilierung des LangGraph StateGraph für die Retourenabwicklung.
"""

from typing import Any
from langgraph.graph import END, START, StateGraph

from models import AgentState
from llm_factory import get_llm
from .extraction import build_node_process_input
from .nodes_agb import build_node_agb_rag
from .nodes_fulfillment import (
    node_auth_retry,
    node_book_return,
    node_policy_check,
    node_verify_auth,
)
from .nodes_handoff import build_node_escalate, build_node_respond_success
from .nodes_user_data import node_user_data
from .routing import route_after_auth, route_after_input, route_after_policy


def create_return_graph(checkpointer: Any = None, llm_instance: Any = None):
    """
    Erstellt, verdrahtet und kompiliert den StateGraph für den Kundenservice-Agenten.
    
    :param checkpointer: Optionaler LangGraph-Checkpointer (z. B. MemorySaver) für Multi-Turn Session-State.
    :param llm_instance: Optionales konkretes BaseChatModel (standardmäßig MockCustomerServiceLLM bzw. get_llm()).
    :return: Kompilierter LangGraph StateGraph.
    """
    active_llm = llm_instance if llm_instance is not None else get_llm()

    workflow = StateGraph(AgentState)

    # 1. Knoten registrieren
    workflow.add_node("node_process_input", build_node_process_input(active_llm))
    workflow.add_node("node_verify_auth", node_verify_auth)
    workflow.add_node("node_auth_retry", node_auth_retry)
    workflow.add_node("node_policy_check", node_policy_check)
    workflow.add_node("node_book_return", node_book_return)
    workflow.add_node("node_respond_success", build_node_respond_success(active_llm))
    workflow.add_node("node_escalate", build_node_escalate(active_llm))
    workflow.add_node("node_agb_rag", build_node_agb_rag(active_llm))
    workflow.add_node("node_user_data", node_user_data)

    # 2. Startpunkt
    workflow.add_edge(START, "node_process_input")

    # 3. Kanten und Verzweigungen
    workflow.add_conditional_edges("node_process_input", route_after_input)

    workflow.add_edge("node_agb_rag", END)
    workflow.add_edge("node_user_data", END)

    workflow.add_conditional_edges("node_verify_auth", route_after_auth)

    workflow.add_edge("node_auth_retry", END)

    workflow.add_conditional_edges("node_policy_check", route_after_policy)

    workflow.add_edge("node_book_return", "node_respond_success")
    workflow.add_edge("node_respond_success", END)
    workflow.add_edge("node_escalate", END)

    return workflow.compile(checkpointer=checkpointer)
