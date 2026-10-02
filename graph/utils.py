"""
graph/utils.py
Hilfsfunktionen für Logging und sprachunabhängige Textbereinigung von LLM-Antworten.
"""

import re


def log_node(node_name: str, message: str) -> None:
    """Standardisiertes Logging für Graph-Knoten."""
    print(f"\n[LOG][NODE][{node_name}] {message}")


def log_action(action_name: str, details: str) -> None:
    """Standardisiertes Logging für deterministische Aktionen und Tool-Aufrufe."""
    print(f"  [LOG][ACTION][{action_name}] {details}")


def clean_chat_output(text: str) -> str:
    """
    Sprachunabhängige, rein strukturelle Bereinigung von LLM-Chat-Antworten.
    Entfernt generisch Markdown-Codeblöcke sowie RFC822-artige Header (z. B. Subject:, Betreff:, Asunto:, To:)
    völlig ohne hardcodierte Sprachwörter.
    """
    if not text:
        return ""
    cleaned = text.strip()

    # 1. Entferne führende / umschließende Markdown-Codeblöcke
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:markdown|text)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    # 2. Entferne generische Header-Zeilen (z. B. Key: Value am Textanfang)
    cleaned = re.sub(r"^(?:[A-Za-z\-]{2,25}:\s+[^\n]+\n+)+", "", cleaned).strip()

    # 3. Entferne einleitende Meta-Labels mit Doppelpunkt (z.B. "Response:", "Draft message:", "Antwort:")
    cleaned = re.sub(
        r"^(?:(?:hier ist (?:die|eine)?|draft|entwurf|response|reply|answer|nachricht|message|output|antwort)[^\n]{0,40}):\s*\n+",
        "",
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    return cleaned
