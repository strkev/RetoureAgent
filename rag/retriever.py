"""
rag/retriever.py
Robuster N-Gram-basierter RAG-Retriever für AGB-Dokumente.
Verwendet Zeichen- (3-Gram, 4-Gram) und Wort-N-Gramme (Unigramme, Bigramme) kombiniert mit BM25-Scoring
für präzise Treffer auch bei deutschen Komposita, Tippfehlern und mehrsprachigen Anfragen.
100% offline, deterministisch und ohne externe C++-Abhängigkeiten.
"""

from collections import Counter
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple


def _normalize_text(text: str) -> str:
    """Bereinigt und normalisiert Text für konsistentes N-Gram-Matching."""
    text = text.lower()
    text = re.sub(r"[^\w\s§äöüÄÖÜß-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_ngrams(text: str) -> List[str]:
    """
    Extrahiert sowohl Wort-N-Gramme (1- und 2-Gramme) als auch Zeichen-N-Gramme (3- und 4-Gramme).
    Zeichen-N-Gramme ermöglichen die robuste Erkennung von deutschen Wortzusammensetzungen
    (Komposita wie 'Rücksendekosten', 'Zahlungsmodalität', 'Garantieanspruch') und Flexionen.
    """
    cleaned = _normalize_text(text)
    if not cleaned:
        return []

    words = re.findall(r"[a-z0-9äöüß§-]+", cleaned)
    ngrams: List[str] = []

    # 1. Wort-Unigramme
    for w in words:
        if len(w) >= 2:
            ngrams.append(f"w1:{w}")

    # 2. Wort-Bigramme
    for i in range(len(words) - 1):
        ngrams.append(f"w2:{words[i]}_{words[i+1]}")

    # 3. Zeichen-3-Gramme und Zeichen-4-Gramme (für Wortstämme & Komposita)
    for w in words:
        if len(w) >= 3:
            for j in range(len(w) - 2):
                ngrams.append(f"c3:{w[j:j+3]}")
        if len(w) >= 4:
            for j in range(len(w) - 3):
                ngrams.append(f"c4:{w[j:j+4]}")

    return ngrams


class AGBChunk:
    def __init__(self, title: str, content: str, section_id: str = ""):
        self.title = title.strip()
        self.content = content.strip()
        self.section_id = section_id.strip()

        # N-Gramme für Titel und Inhalt getrennt berechnen
        self.title_ngrams = extract_ngrams(self.title)
        self.content_ngrams = extract_ngrams(self.content)

        # Gesamte N-Gram-Häufigkeiten des Dokuments
        self.ngram_counts: Counter = Counter(self.content_ngrams)
        # Titel-N-Gramme erhalten ein erhöhtes Gewicht im Index
        for ng in self.title_ngrams:
            self.ngram_counts[ng] += 3

        self.doc_len = sum(self.ngram_counts.values()) or 1


class AGBRetriever:
    """Lädt, indexiert und findet AGB-Abschnitte mittels N-Gram BM25-Scoring."""

    def __init__(self, file_path: Optional[str] = None):
        if not file_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(base_dir, "data", "agb.md")
        self.file_path = file_path
        self.chunks: List[AGBChunk] = []
        self.df: Counter = Counter()  # Document Frequency pro N-Gram
        self.idf: Dict[str, float] = {}
        self.avg_doc_len: float = 1.0
        self._load_and_chunk()

    def _load_and_chunk(self) -> None:
        if not os.path.exists(self.file_path):
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # Teile an '## §' Abschnitten
        sections = re.split(r"(?m)(?=^## §)", raw_text)
        self.chunks = []
        for sec in sections:
            sec = sec.strip()
            if not sec or not sec.startswith("##"):
                continue

            lines = sec.split("\n", 1)
            title_line = lines[0].replace("##", "").strip()
            body = lines[1].strip() if len(lines) > 1 else ""

            # Extrahiere z. B. "§ 4"
            match_id = re.search(r"(§\s*\d+)", title_line)
            sec_id = match_id.group(1) if match_id else ""

            self.chunks.append(AGBChunk(title=title_line, content=body, section_id=sec_id))

        if not self.chunks:
            return

        # N-Gram-Vokabular & Document Frequencies berechnen
        n_docs = len(self.chunks)
        self.df = Counter()
        total_len = 0
        for chunk in self.chunks:
            total_len += chunk.doc_len
            unique_ngrams = set(chunk.ngram_counts.keys())
            for ng in unique_ngrams:
                self.df[ng] += 1

        self.avg_doc_len = total_len / n_docs if n_docs > 0 else 1.0

        # BM25-IDF vorberechnen
        self.idf = {}
        for ng, freq in self.df.items():
            self.idf[ng] = math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Sucht die relevantesten AGB-Abschnitte für die Nutzeranfrage mittels N-Gram-BM25.
        """
        if not self.chunks or not query or not query.strip():
            return []

        query_ngrams = extract_ngrams(query)
        if not query_ngrams:
            return [{"title": self.chunks[0].title, "content": self.chunks[0].content, "section_id": self.chunks[0].section_id, "score": 1.0}]

        # Direktes Paragraphen-Matching als Boost (z.B. "§ 4" oder "Paragraph 5")
        sec_match = re.search(r"(?:§|paragraph|abschnitt)\s*(\d+)", query, re.IGNORECASE)
        target_sec_num = sec_match.group(1) if sec_match else None

        q_counter = Counter(query_ngrams)
        k1 = 1.2
        b = 0.75

        scored_chunks: List[Tuple[float, AGBChunk]] = []

        for chunk in self.chunks:
            score = 0.0

            # 1. BM25-Scoring über gemeinsame N-Gramme
            for ng, q_freq in q_counter.items():
                if ng not in chunk.ngram_counts:
                    continue

                tf = chunk.ngram_counts[ng]
                idf_val = self.idf.get(ng, 0.5)

                # Unterschiedliche N-Gram-Gewichtungen:
                # Wort-Bigramme & seltene Wort-Unigramme wiegen am stärksten, Zeichen-N-Gramme stützen Komposita
                weight = 1.0
                if ng.startswith("w2:"):
                    weight = 2.5
                elif ng.startswith("w1:"):
                    weight = 1.8
                elif ng.startswith("c4:"):
                    weight = 0.8
                elif ng.startswith("c3:"):
                    weight = 0.4

                # BM25-Termberechnung
                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (chunk.doc_len / self.avg_doc_len))
                score += idf_val * (numerator / denominator) * weight

            # 2. Direkter Treffer im Titel (N-Gramm-Überschneidung mit Titel)
            title_overlap = sum(1 for ng in query_ngrams if ng in chunk.title_ngrams)
            if title_overlap > 0:
                score += title_overlap * 1.5

            # 3. Explizite Paragraphen-Referenz-Boost
            if target_sec_num and f"§ {target_sec_num}" in chunk.section_id:
                score += 15.0

            scored_chunks.append((score, chunk))

        # Sortiere nach absteigendem Score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scored_chunks[:top_k]:
            results.append({
                "title": chunk.title,
                "content": chunk.content,
                "section_id": chunk.section_id,
                "score": round(float(score), 2),
            })
        return results


# Globales Singleton für schnellen Zugriff
_retriever_instance: Optional[AGBRetriever] = None


def get_agb_retriever() -> AGBRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = AGBRetriever()
    return _retriever_instance
