"""
Package: graph
Modulare LangGraph-Implementierung für den Kundenservice-Agenten.
Bietet 100%ige Abwärtskompatibilität durch Re-Export der zentralen Fabrikfunktion.
"""

from .builder import create_return_graph
from .utils import clean_chat_output

__all__ = [
    "create_return_graph",
    "clean_chat_output",
]
