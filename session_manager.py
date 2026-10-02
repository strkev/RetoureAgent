"""
session_manager.py
Verwaltet Sessions, LangGraph Checkpointer (MemorySaver) und instanziiert
StateGraphs mit der jeweils konfigurierten LLM-Instanz.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4
from langgraph.checkpoint.memory import MemorySaver

from graph import create_return_graph
from llm_factory import get_llm


class SessionManager:
    """Verwaltet Sessions, Checkpointer und zugehörige StateGraphs mit spezifischer LLM-Konfiguration."""

    def __init__(self):
        self.checkpointers: Dict[str, MemorySaver] = {}
        self.graphs: Dict[str, Any] = {}
        self.llm_configs: Dict[str, Dict[str, Optional[str]]] = {}
        self.start_times: Dict[str, str] = {}

    def get_or_create(
        self,
        session_id: Optional[str] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None
    ) -> Tuple[str, Any, MemorySaver]:
        if not session_id:
            session_id = f"session-{uuid4().hex[:8]}"

        if session_id not in self.start_times:
            self.start_times[session_id] = datetime.now().strftime("%H:%M")

        new_config = {
            "api_key": (api_key or "").strip(),
            "api_url": (api_url or "").strip(),
            "model": (model or "").strip()
        }

        existing_config = self.llm_configs.get(session_id)
        config_changed = existing_config != new_config

        if session_id not in self.graphs or config_changed:
            cp = self.checkpointers.get(session_id) or MemorySaver()
            self.checkpointers[session_id] = cp
            self.llm_configs[session_id] = new_config

            active_llm = get_llm(
                api_key=new_config["api_key"] or None,
                base_url=new_config["api_url"] or None,
                model_name=new_config["model"] or None
            )
            self.graphs[session_id] = create_return_graph(checkpointer=cp, llm_instance=active_llm)

        return session_id, self.graphs[session_id], self.checkpointers[session_id]

    def reset(self, session_id: str) -> Tuple[str, Any, MemorySaver]:
        if session_id in self.checkpointers:
            del self.checkpointers[session_id]
        if session_id in self.graphs:
            del self.graphs[session_id]
        if session_id in self.llm_configs:
            del self.llm_configs[session_id]
        if session_id in self.start_times:
            del self.start_times[session_id]
        return self.get_or_create(session_id)


# Globales Singleton
sessions = SessionManager()
