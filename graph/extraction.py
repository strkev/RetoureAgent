"""
graph/extraction.py
Eingabeverarbeitung, strukturierte LLM-Intent- und Daten-Extraktion,
Halluzinations-Schutz und Off-Topic-Filterung.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from models import AgentState, ExtractedReturnInfo
import i18n
from .utils import log_action, log_node


# ---------------------------------------------------------------------------
# Vorkompilierte reguläre Ausdrücke (Performance & Wartbarkeit)
# ---------------------------------------------------------------------------
RE_ORDER_ID = re.compile(r"\b(ORD-\d+)\b", re.IGNORECASE)
RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RE_OFF_TOPIC = re.compile(
    r"(\b\d+\s*[\+\-\*\/]\s*\d+\b|\b(?:sort|code|program|python|javascript|prompt|weather|wetter|recipe|rezept|joke|witz)\b)",
    re.IGNORECASE
)
RE_AGB = re.compile(
    r"\b(agb|agbs|richtlinien|zahlung|zahlungsart|zahlungsarten|bezahlen|bezahlung|versand|versandkosten|lieferung|lieferzeit|porto|dauer|garantie|gewährleistung|gutschein|warengutschein|store\s*credit|voucher|rabatt|coupon|terms|condition|conditions|payment|shipping|warranty)\b",
    re.IGNORECASE
)
RE_USERDATA = re.compile(
    r"\b(adresse|lieferadresse|rechnungsadresse|umzug|umgezogen|nutzerdaten|kundendaten|kundenkonto|account|daten\s+anpassen|adresse\s+ändern|daten\s+ändern|kundendaten\s+ändern|kundendaten\s+anpassen|kundenkonto\s+bearbeiten|kundenkonto\s+anpassen|profil|profil\s+anpassen|profil\s+bearbeiten|meine\s+daten|update\s+address|change\s+address|update\s+data|change\s+data|user\s+data|email\s+ändern|e-mail\s+ändern)\b",
    re.IGNORECASE
)
RE_GREETING = re.compile(
    r"^(?:hallo|guten\s+tag|guten\s+morgen|guten\s+abend|hi|hello|hey|moin|servus|grüße)\b",
    re.IGNORECASE
)
RE_RETURN = re.compile(
    r"\b(retoure|retouren|retournier\w*|rücksend\w*|zurück\w*|widerruf\w*|erstatten|erstattung|umtausch\w*|reklam\w*|return\w*|refund\w*|exchange)\b",
    re.IGNORECASE
)
RE_NEW_RETURN = re.compile(
    r"\b(weitere|andere|neue|noch\s+eine|another|new)\s+(?:retoure|rücksendung|return)\b",
    re.IGNORECASE
)
RE_THANKS = re.compile(
    r"\b(danke|vielen\s+dank|klasse|super|perfekt|dankeschön|thanks|thank\s+you)\b",
    re.IGNORECASE
)
RE_EMOTIONAL = re.compile(
    r"\b(wütend|sauer|stinksauer|verärgert|frechheit|unverschämt|saftladen|katastrophe|unfähig|scheiß\w*|mist|drecks\w*|verarschen|verarsche|abzocke|betrug|beschwerde|beschweren|anwalt|drohen|unhöflich|inkompetent|schlechteste[rns]?\s+service|schrecklich|unzumutbar|ridiculous|furious|angry|pissed|unacceptable|scam|terrible|horrible|lawyer)\b",
    re.IGNORECASE
)



def extract_fallback_regex(messages: List[Any], previous_intent: Optional[str] = None) -> ExtractedReturnInfo:
    """
    Deterministischer Fallback zur Extraktion von Bestellnummer, E-Mail und Sprache
    AUSSCHLIESSLICH aus Nachrichten des Kunden (HumanMessage).
    """
    human_texts = []
    for m in messages:
        if isinstance(m, HumanMessage):
            human_texts.append(str(m.content))
        elif isinstance(m, dict) and m.get("role") in ["user", "human"]:
            human_texts.append(str(m.get("content", "")))

    full_text = "\n".join(human_texts)
    latest_text = human_texts[-1] if human_texts else full_text

    order_matches = RE_ORDER_ID.findall(full_text)
    order_id = order_matches[-1].upper() if order_matches else None

    email_matches = RE_EMAIL.findall(full_text)
    email = email_matches[-1].lower() if email_matches else None

    lang = i18n.detect_language_simple(full_text)

    is_off_topic = False
    if not (order_id and email):
        if RE_OFF_TOPIC.search(latest_text):
            is_off_topic = True

    latest_lower = latest_text.lower().strip()

    if is_off_topic and not (order_id and email):
        intent = "off_topic"
    elif RE_AGB.search(latest_lower):
        intent = "agb"
    elif RE_USERDATA.search(latest_lower) or latest_lower in ["email", "e-mail", "adresse", "name", "kundendaten", "kundenkonto", "account"]:
        intent = "nutzerdaten"
    elif RE_RETURN.search(latest_lower):
        intent = "retoure"
    elif RE_GREETING.search(latest_lower):
        intent = "greeting"
    elif "ord-" in latest_lower or (order_id and ("@" in latest_lower or "ord-" in latest_lower)):
        intent = "retoure"
    elif previous_intent in ["agb", "nutzerdaten", "retoure"]:
        intent = previous_intent
    else:
        intent = "greeting"

    is_frustrated = bool(RE_EMOTIONAL.search(latest_lower))
    return ExtractedReturnInfo(intent=intent, language=lang, order_id=order_id, email=email, is_frustrated=is_frustrated)


_laya_router = None


def get_laya_router():
    """Initialisiert und cached den Laya Router als Singleton."""
    global _laya_router
    if _laya_router is None:
        try:
            from laya import Router
            _laya_router = Router(default="multilingual")
        except Exception as e:
            print(f"[WARN] Laya Router konnte nicht geladen werden ({e}).")
            _laya_router = None
    return _laya_router


LAYA_INTENT_QUESTIONS_DE = {
    "intent": {
        "type": "choice",
        "instructions": "Worum geht es in dieser Kundennachricht?",
        "criteria": {
            "retoure": "Retoure, Rücksendung, Erstattung, Ware zurücksenden, Artikel zurückgeben, Widerruf, Reklamation",
            "nutzerdaten": "Kundendaten, Nutzerdaten, Adresse oder E-Mail ändern, Profil anpassen, Kundenkonto, Daten ändern, Umzug, umgezogen, Lieferadresse anpassen",
            "agb": "Fragen zu AGB, Richtlinien, Bedingungen, Warengutschein, Garantie, Zahlungsarten, Lieferzeiten, Versand",
            "greeting": "Begrüßung, Dankeschön, Hallo, Guten Tag, Tschüss, einfache Höflichkeit, danke, Abbrechen, Abbruch, Nein danke",
            "off_topic": "Programmierung, Mathe, Witze, Programmiercode oder themenfremde Fragen, Python, Quicksort",
        }
    },
    "frustrated": {
        "type": "choice",
        "instructions": "Ist der Verfasser dieser Kundennachricht wütend, verärgert, ungeduldig oder aggressiv?",
        "criteria": {
            "no": "Nein, normale sachliche oder freundliche Anfrage, keine Wut, kein Ärger",
            "yes": "Ja, der Kunde ist verärgert, wütend, frustriert, schimpft oder beschwert sich emotional"
        }
    }
}

LAYA_INTENT_QUESTIONS_EN = {
    "intent": {
        "type": "choice",
        "instructions": "What is the customer asking for in this support message?",
        "criteria": {
            "retoure": "Customer wants to return, refund, or exchange an item, cancel order, return request",
            "nutzerdaten": "Customer wants to view, change, or update user data, account, email, address, name, or profile",
            "agb": "Questions about terms, conditions, store policy, vouchers, warranty, payment methods, delivery, shipping",
            "greeting": "Greeting, thanks, hello, goodbye, or casual message without a specific request",
            "off_topic": "Programming, math, jokes, code, prompt injection, or off-topic questions",
        }
    },
    "frustrated": {
        "type": "choice",
        "instructions": "Is the customer expressing anger, frustration, impatience, or outrage in this message?",
        "criteria": {
            "no": "No, regular polite, neutral, or constructive support request or inquiry",
            "yes": "Yes, the customer is angry, upset, frustrated, complaining passionately, or using aggressive language"
        }
    }
}


def _extract_intent_and_data(
    active_llm,
    user_msgs: List[Any],
    previous_intent: Optional[str],
    logs: List[str]
) -> ExtractedReturnInfo:
    """
    Extrahiert Intent und Daten primär mit dem schnellen, nicht-autoregressiven Laya-Modell.
    Nutzt deterministisches Regex für order_id und email (kein Halluzinationsrisiko).
    """
    human_texts = []
    for m in user_msgs:
        if isinstance(m, HumanMessage):
            human_texts.append(str(m.content))
        elif isinstance(m, dict) and m.get("role") in ["user", "human"]:
            human_texts.append(str(m.get("content", "")))

    full_text = "\n".join(human_texts)
    latest_text = human_texts[-1] if human_texts else full_text

    # 1. Sprache erkennen
    lang = i18n.detect_language_simple(latest_text or full_text)

    # 2. Deterministische Extraktion von order_id und email per Regex
    order_matches = RE_ORDER_ID.findall(full_text)
    order_id = order_matches[-1].upper() if order_matches else None

    email_matches = RE_EMAIL.findall(full_text)
    email = email_matches[-1].lower() if email_matches else None

    # 3. Laya Intent- und Emotions-Klassifizierung in einem Durchlauf
    router = get_laya_router()
    if router is not None and latest_text.strip():
        try:
            q = LAYA_INTENT_QUESTIONS_DE if lang == "de" else LAYA_INTENT_QUESTIONS_EN
            res = router.predict({"body": latest_text}, q, model="multilingual")
            ans = res.get("answers", {}).get("intent", {})
            intent = ans.get("choice", "greeting")
            raw_conf = ans.get("answer_confidence") or ans.get("confidence") or 0.95
            confidence = float(raw_conf)

            # Laya Sprach-Routing berücksichtigen
            routing_info = res.get("routing") or {}
            detection_info = routing_info.get("detection") or {}
            laya_lang = detection_info.get("language")
            if laya_lang and laya_lang in ["de", "en"]:
                lang = laya_lang

            latest_lower = latest_text.lower().strip()

            # Frustration / Emotion aus Laya und Regex ermitteln
            ans_frust = res.get("answers", {}).get("frustrated", {})
            frustrated_choice = ans_frust.get("choice")
            is_frustrated = (frustrated_choice == "yes") or bool(RE_EMOTIONAL.search(latest_lower))

            log_action("LAYA_PREDICT", f"Laya Intent erkannt: '{intent}' (Konfidenz: {confidence:.2f}, Sprache: {lang}, Frust: {is_frustrated})")
            logs.append(f"[LOG][ACTION][LAYA_PREDICT] Laya Intent: '{intent}' (Konfidenz: {confidence:.2f}, Frust: {is_frustrated})")

            # Plausibilitätsprüfungen und Kontextkorrektur:
            # 1. Reine Bestelldaten für Retoure (z.B. "Meine Bestellnummer ist ORD-1001", "Hier meine Mail: ...")
            if (order_id or email or "ord-" in latest_lower or "@" in latest_lower) and not RE_USERDATA.search(latest_lower):
                if previous_intent == "retoure" or intent in ["greeting", "off_topic", "nutzerdaten"]:
                    intent = "retoure"

            # 2. Explizite Nutzerdaten-Anfrage (z.B. "Ich bin umgezogen und möchte meine Lieferadresse anpassen")
            elif RE_USERDATA.search(latest_lower) and not re.search(r"\b(ich\s+möchte|will|bitte)\s+.*(?:zurück|retournier)", latest_lower, re.IGNORECASE):
                if confidence < 0.85 or intent != "nutzerdaten":
                    intent = "nutzerdaten"
                    confidence = 0.95

            # 3. Fragen nach AGB / Richtlinien (z.B. "Welche AGBs gelten für meine Retoure?")
            elif RE_AGB.search(latest_lower) and not re.search(r"\b(ich\s+möchte|will|bitte)\s+.*(?:zurück|retournier)", latest_lower, re.IGNORECASE):
                if any(w in latest_lower for w in ["welche", "was", "wie", "gelten", "bedingungen", "richtlinie", "agb"]):
                    intent = "agb"
                    confidence = 0.95

            return ExtractedReturnInfo(
                intent=intent,
                language=lang,
                order_id=order_id,
                email=email,
                intent_confidence=confidence,
                is_frustrated=is_frustrated,
            )
        except Exception as e:
            warn_msg = f"Laya-Klassifikation fehlgeschlagen: {e}. Fallback auf LLM / Regex."
            log_action("LAYA_FALLBACK", warn_msg)
            logs.append(f"[LOG][ACTION][LAYA_FALLBACK] {warn_msg}")

    # Fallback auf LLM oder Regex
    if active_llm and hasattr(active_llm, "with_structured_output"):
        try:
            extractor = active_llm.with_structured_output(ExtractedReturnInfo)
            extraction_prompt = [
                SystemMessage(content=(
                    "You are an accurate multilingual data and intent extractor for an e-commerce customer support system.\n"
                    f"Active topic in conversation: {previous_intent or 'none'}.\n"
                    "Determine the customer's CURRENT intent based on their latest message.\n"
                    "1. order_id (Format: ORD-XXXX): Extract only if explicitly in text.\n"
                    "2. email: Extract only if valid email in text.\n"
                    "3. language: 'de' or 'en'.\n"
                    "4. intent: 'retoure', 'nutzerdaten', 'agb', 'greeting', or 'off_topic'.\n"
                    "5. intent_confidence: Float 0.0 to 1.0."
                ))
            ] + user_msgs
            return extractor.invoke(extraction_prompt)
        except Exception:
            pass

    return extract_fallback_regex(user_msgs, previous_intent=previous_intent)


def _resolve_language(
    state_language: Optional[str],
    extracted_lang: Optional[str],
    user_msgs: List[Any],
    user_text_corpus: str
) -> str:
    """Ermittelt und normalisiert die aktive Sprache unter Berücksichtigung von Kurzantworten."""
    latest_user_text = str(user_msgs[-1].content if hasattr(user_msgs[-1], "content") else user_msgs[-1].get("content", "")) if user_msgs else ""
    if len(latest_user_text.split()) <= 2 and state_language:
        return state_language
    if extracted_lang:
        return i18n.normalize_language(extracted_lang)
    if user_text_corpus:
        return i18n.detect_language_simple(user_text_corpus)
    return state_language or i18n.DEFAULT_LANGUAGE


def _sanitize_credentials(
    extracted: Optional[ExtractedReturnInfo],
    user_msgs: List[Any],
    user_text_corpus: str,
    current_order_id: Optional[str],
    current_email: Optional[str],
    logs: List[str]
) -> Tuple[Optional[str], Optional[str]]:
    """Validiert Bestelldaten gegen Halluzinationen und übernimmt Angaben aus vorherigen Turns."""
    order_id = current_order_id
    email = current_email

    if extracted:
        if extracted.order_id:
            cand_order = extracted.order_id.strip().upper()
            if re.search(re.escape(cand_order), user_text_corpus, re.IGNORECASE):
                order_id = cand_order
            else:
                log_action("HALLUCINATION_GUARD", f"Ignoriere unbestätigte order_id '{cand_order}', da nicht in Kundennachrichten.")
                logs.append(f"[LOG][ACTION][HALLUCINATION_GUARD] Ignoriere order_id '{cand_order}'.")

        if extracted.email:
            cand_email = extracted.email.strip().lower()
            if re.search(re.escape(cand_email), user_text_corpus, re.IGNORECASE):
                email = cand_email
            else:
                log_action("HALLUCINATION_GUARD", f"Ignoriere unbestätigte email '{cand_email}', da nicht in Kundennachrichten.")
                logs.append(f"[LOG][ACTION][HALLUCINATION_GUARD] Ignoriere email '{cand_email}'.")

    if not order_id:
        for m in reversed(user_msgs):
            txt = m.content if hasattr(m, "content") else str(m)
            om = RE_ORDER_ID.search(str(txt))
            if om:
                order_id = om.group(1).upper()
                log_action("HISTORY_LOOKUP", f"Bestellnummer {order_id} aus vorheriger Kundennachricht übernommen.")
                break

    if not email:
        for m in reversed(user_msgs):
            txt = m.content if hasattr(m, "content") else str(m)
            em = RE_EMAIL.search(str(txt))
            if em:
                email = em.group(0).lower()
                log_action("HISTORY_LOOKUP", f"E-Mail {email} aus vorheriger Kundennachricht übernommen.")
                break

    if order_id and not re.search(re.escape(order_id), user_text_corpus, re.IGNORECASE):
        order_id = None
    if email and not re.search(re.escape(email), user_text_corpus, re.IGNORECASE):
        email = None

    return order_id, email


def _resolve_effective_intent(
    extracted_intent: str,
    previous_intent: Optional[str],
    latest_user_text: str,
    logs: List[str]
) -> str:
    """Normalisiert den Intent und sichert Kontext-Retention bei kurzen Rückfragen."""
    current_intent = extracted_intent or "retoure"
    if current_intent == "return_request":
        current_intent = "retoure"

    latest_lower = latest_user_text.lower().strip()
    if re.search(r"\b(abbrechen|abbruch|doch\s+nicht|nicht\s+mehr|nein\s+danke|abbreche|stoppen|stop|zurück|cancel)\b", latest_lower):
        return "greeting"

    if current_intent == "greeting" and previous_intent in ["agb", "nutzerdaten", "retoure"]:
        if not RE_GREETING.search(latest_user_text.strip()):
            current_intent = previous_intent
            log_action("CONTEXT_RETENTION", f"Thema '{previous_intent}' für Rückfrage '{latest_user_text}' beibehalten.")
            logs.append(f"[LOG][ACTION][CONTEXT_RETENTION] Thema '{previous_intent}' beibehalten.")

    return current_intent


def _handle_completed_return(
    lang: str,
    order_id: Optional[str],
    email: Optional[str],
    state_order_id: Optional[str],
    latest_user_text: str,
    logs: List[str]
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Prüft, ob nach einer gebuchten Retoure eine Bestätigung oder Folge-Retoure vorliegt."""
    latest_lower = latest_user_text.lower().strip()
    new_ord_match = RE_ORDER_ID.search(latest_lower)
    is_new_return = bool(
        RE_NEW_RETURN.search(latest_lower)
        or (new_ord_match and new_ord_match.group(1).upper() != (state_order_id or ""))
    )

    if not is_new_return:
        is_thanks = bool(RE_THANKS.search(latest_lower))
        msg_key = "return_completed_thanks" if is_thanks else "return_completed_already"
        ack_text = i18n.get_text(msg_key, lang=lang)

        log_action("RETURN_ALREADY_COMPLETED", "Retoure war bereits gebucht. Keine Doppelbuchung.")
        logs.append("[LOG][ACTION][RETURN_ALREADY_COMPLETED] Retoure bereits abgeschlossen.")

        response_dict = {
            "language": lang,
            "order_id": order_id,
            "email": email,
            "current_intent": "greeting",
            "messages": [AIMessage(content=ack_text)],
            "next_step": "wait_for_input",
            "last_active_node": "node_process_input",
            "execution_logs": logs,
            "auth_widget_requested": False,
        }
        return True, response_dict

    log_action("NEW_RETURN_INITIATED", "Explizite Folge-Retoure wird eingeleitet.")
    logs.append("[LOG][ACTION][NEW_RETURN_INITIATED] Neue Retoure eingeleitet.")
    return False, None


def build_node_process_input(active_llm):
    """Erstellt den modularen Einstiegsknoten zur Analyse von Kundennachrichten."""
    def node_process_input(state: AgentState) -> Dict[str, Any]:
        log_node("node_process_input", "Analysiere Nutzereingabe...")
        logs = ["[LOG][NODE][node_process_input] Analysiere Nutzereingabe..."]

        messages = state.messages
        user_msgs = [
            m for m in messages
            if isinstance(m, HumanMessage) or (isinstance(m, dict) and m.get("role") in ["user", "human"])
        ]
        user_text_corpus = " ".join([
            str(m.content if hasattr(m, "content") else m.get("content", ""))
            for m in user_msgs
        ])
        latest_user_text = str(user_msgs[-1].content if hasattr(user_msgs[-1], "content") else user_msgs[-1].get("content", "")) if user_msgs else ""

        extracted = _extract_intent_and_data(active_llm, user_msgs, state.current_intent, logs)
        lang = _resolve_language(state.language, extracted.language if extracted else None, user_msgs, user_text_corpus)
        order_id, email = _sanitize_credentials(extracted, user_msgs, user_text_corpus, state.order_id, state.email, logs)
        current_intent = _resolve_effective_intent(extracted.intent if extracted else "retoure", state.current_intent, latest_user_text, logs)

        log_msg = f"Extrahierte Werte: Intent='{current_intent}', Sprache='{lang}', order_id='{order_id}', email='{email}'"
        log_action("EXTRACT_DATA", log_msg)
        logs.append(f"[LOG][ACTION][EXTRACT_DATA] {log_msg}")

        intent_confidence = getattr(extracted, "intent_confidence", None) if extracted else None

        # Frustrations- / Emotions-Tracking
        is_frustrated = bool(getattr(extracted, "is_frustrated", False))
        prev_emotional_count = state.emotional_messages_count or 0
        emotional_count = prev_emotional_count + 1 if is_frustrated else prev_emotional_count

        if is_frustrated:
            log_action("EMOTION_TRACKED", f"Emotionale Nachricht registriert (Zähler: {emotional_count}/3).")
            logs.append(f"[LOG][ACTION][EMOTION_TRACKED] Emotionalitäts-Zähler: {emotional_count}/3")

        # Eskalationsregel: Nach der 3. emotionalen Nachricht direkt an menschlichen Support übergeben!
        if emotional_count >= 3:
            log_action("EMOTIONAL_ESCALATION", f"Schwellenwert für emotionale Eskalation erreicht ({emotional_count}/3). Leite an Support weiter.")
            logs.append("[LOG][ACTION][EMOTIONAL_ESCALATION] 3 emotionale Nachrichten erreicht -> Übergabe an menschlichen Support.")
            return {
                "language": lang,
                "order_id": order_id,
                "email": email,
                "current_intent": "off_topic",
                "next_step": "escalate",
                "last_active_node": "node_process_input",
                "execution_logs": logs,
                "intent_confidence": intent_confidence,
                "auth_widget_requested": False,
                "emotional_messages_count": emotional_count,
                "is_frustrated": True,
            }

        # 1. Intent: AGB-Auskunft (RAG)
        if current_intent == "agb":
            log_action("INTENT_AGB", "Kundenanfrage als AGB- / Richtlinien-Thema klassifiziert.")
            logs.append("[LOG][ACTION][INTENT_AGB] Anfrage als AGB / Richtlinien klassifiziert.")
            return {
                "language": lang,
                "order_id": order_id,
                "email": email,
                "current_intent": "agb",
                "next_step": "agb_rag",
                "last_active_node": "node_process_input",
                "execution_logs": logs,
                "intent_confidence": intent_confidence,
                "auth_widget_requested": False,
                "emotional_messages_count": emotional_count,
                "is_frustrated": is_frustrated,
            }

        # 2. Intent: Nutzerdaten anpassen
        if current_intent == "nutzerdaten":
            log_action("INTENT_USER_DATA", "Kundenanfrage als Nutzerdatenanpassung klassifiziert.")
            logs.append("[LOG][ACTION][INTENT_USER_DATA] Anfrage als Nutzerdatenanpassung klassifiziert.")
            return {
                "language": lang,
                "order_id": order_id,
                "email": email,
                "current_intent": "nutzerdaten",
                "next_step": "user_data",
                "last_active_node": "node_process_input",
                "execution_logs": logs,
                "intent_confidence": intent_confidence,
                "emotional_messages_count": emotional_count,
                "is_frustrated": is_frustrated,
            }

        # 3. Intent: Off-Topic / Prompt-Injections
        if current_intent == "off_topic":
            if not order_id and not email:
                extra_info = i18n.get_text("off_topic_ask_both", lang=lang)
            elif not order_id:
                extra_info = i18n.get_text("off_topic_ask_order", lang=lang)
            elif not email:
                extra_info = i18n.get_text("off_topic_ask_email", lang=lang)
            else:
                extra_info = i18n.get_text("off_topic_ask_continue", lang=lang)

            content = i18n.get_text("off_topic_decline", lang=lang, extra_info=extra_info)
            log_action("OFF_TOPIC_REJECTED", f"Themenfremde Anfrage abgewiesen (Sprache: {lang}).")
            logs.append(f"[LOG][ACTION][OFF_TOPIC_REJECTED] Themenfremde Anfrage abgewiesen ({lang}).")
            return {
                "language": lang,
                "order_id": order_id,
                "email": email,
                "current_intent": "off_topic",
                "messages": [AIMessage(content=content)],
                "next_step": "wait_for_input",
                "last_active_node": "node_process_input",
                "execution_logs": logs,
                "intent_confidence": intent_confidence,
                "auth_widget_requested": False,
                "emotional_messages_count": emotional_count,
                "is_frustrated": is_frustrated,
            }

        # 4. Reine Begrüßung (ohne Retourendaten)
        if current_intent == "greeting" and not order_id and not email:
            greet_msg = AIMessage(content=i18n.get_text("greeting_response", lang=lang))
            log_action("GREETING_RESPONDED", f"Begrüßung erwidert (Sprache: {lang}).")
            logs.append(f"[LOG][ACTION][GREETING_RESPONDED] Begrüßung erwidert ({lang}).")
            return {
                "language": lang,
                "order_id": None,
                "email": None,
                "current_intent": "greeting",
                "messages": [greet_msg],
                "next_step": "wait_for_input",
                "last_active_node": "node_process_input",
                "execution_logs": logs,
                "intent_confidence": intent_confidence,
                "auth_widget_requested": False,
                "emotional_messages_count": emotional_count,
                "is_frustrated": is_frustrated,
            }

        # 5. Intent: Retoure
        # Prüfen, ob eine Bestätigung oder Teilauswahl für eine bereits authentifizierte Bestellung vorliegt
        if state.auth_status and state.order_data and not state.return_completed:
            order_items = state.order_data.get("items", [])
            latest_lower = latest_user_text.lower().strip()

            # Prüfen auf Abbruch
            if re.search(r"\b(abbrechen|abbruch|doch\s+nicht|nicht\s+mehr|nein\s+danke|cancel|stop)\b", latest_lower):
                cancel_text = (
                    "Die Retoure wurde abgebrochen. Wie kann ich Ihnen sonst weiterhelfen?"
                    if lang == "de" else
                    "The return process has been canceled. How else can I assist you?"
                )
                log_action("RETURN_CANCELED", "Nutzer hat die Retourenbestätigung abgebrochen.")
                logs.append("[LOG][ACTION][RETURN_CANCELED] Retoure abgebrochen.")
                return {
                    "language": lang,
                    "order_id": None,
                    "email": None,
                    "order_data": None,
                    "current_intent": "greeting",
                    "messages": [AIMessage(content=cancel_text)],
                    "next_step": "wait_for_input",
                    "last_active_node": "node_process_input",
                    "execution_logs": logs,
                }

            # Prüfen auf Bestätigung oder Artikelauswahl
            is_confirm = bool(re.search(r"\b(ja|bestätig\w*|abgeschloss\w*|abschließen|passt|in ordnung|einverstanden|confirm|yes|ok|alle\s+artikel|alle)\b", latest_lower))

            # Prüfen, ob bestimmte Artikel explizit genannt wurden (Teil-Retoure)
            matched_item_ids = []
            for it in order_items:
                if isinstance(it, dict):
                    name_words = [w.lower() for w in re.findall(r"\w+", it.get("name", ""))]
                    item_id = it.get("item_id", "").lower()
                    if item_id in latest_lower or any(len(w) >= 4 and w in latest_lower for w in name_words):
                        matched_item_ids.append(it.get("item_id"))

            if is_confirm or matched_item_ids:
                final_selected = matched_item_ids if matched_item_ids else (state.selected_items or [it.get("item_id") for it in order_items if isinstance(it, dict)])
                log_action("RETURN_CONFIRMED_VIA_CHAT", f"Retoure per Chat bestätigt für Artikel: {final_selected}")
                logs.append(f"[LOG][ACTION][RETURN_CONFIRMED_VIA_CHAT] Retoure bestätigt für: {final_selected}")
                return {
                    "language": lang,
                    "order_id": state.order_id,
                    "email": state.email,
                    "current_intent": "retoure",
                    "selected_items": final_selected,
                    "return_confirmed": True,
                    "next_step": "verify_auth",
                    "last_active_node": "node_process_input",
                    "execution_logs": logs,
                }

        if state.return_completed:
            handled, completed_res = _handle_completed_return(
                lang, order_id, email, state.order_id, latest_user_text, logs
            )
            if handled and completed_res:
                completed_res["emotional_messages_count"] = emotional_count
                completed_res["is_frustrated"] = is_frustrated
                return completed_res
            # Bei Folgeretoure mit neuer Bestellnummer diese aktualisieren:
            new_match = RE_ORDER_ID.search(latest_user_text)
            if new_match:
                order_id = new_match.group(1).upper()

        # Fehlende Pflichtangaben bei Retoure erfragen
        if not order_id and not email:
            prompt_missing = i18n.get_text("request_both", lang=lang)
        elif not order_id:
            prompt_missing = i18n.get_text("request_order", lang=lang)
        elif not email:
            prompt_missing = i18n.get_text("request_email", lang=lang)
        else:
            prompt_missing = None

        if prompt_missing:
            req_msg = f"Fehlende Angaben. Warte auf Kundeneingabe (Sprache: {lang})."
            log_action("REQUEST_INFO", req_msg)
            logs.append(f"[LOG][ACTION][REQUEST_INFO] {req_msg}")
            return {
                "language": lang,
                "order_id": order_id,
                "email": email,
                "current_intent": "retoure",
                "messages": [AIMessage(content=prompt_missing)],
                "next_step": "wait_for_input",
                "last_active_node": "node_process_input",
                "execution_logs": logs,
                "intent_confidence": intent_confidence,
                "auth_widget_requested": False,
                "emotional_messages_count": emotional_count,
                "is_frustrated": is_frustrated,
            }

        val_msg = f"Beide Angaben vorhanden: order_id={order_id}, email={email}, lang={lang}"
        log_action("VALIDATION_SUCCESS", val_msg)
        logs.append(f"[LOG][ACTION][VALIDATION_SUCCESS] {val_msg}")

        return {
            "language": lang,
            "order_id": order_id,
            "email": email,
            "current_intent": "retoure",
            "next_step": "verify_auth",
            "last_active_node": "node_process_input",
            "execution_logs": logs,
            "intent_confidence": intent_confidence,
            "auth_widget_requested": False,
            "emotional_messages_count": emotional_count,
            "is_frustrated": is_frustrated,
        }

    return node_process_input
