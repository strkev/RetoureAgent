"""
Package: rag
Modulares RAG-System für AGB und Kundenservice-Wissensquellen.
"""

from .retriever import AGBRetriever, get_agb_retriever

__all__ = [
    "AGBRetriever",
    "get_agb_retriever",
]
