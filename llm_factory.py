"""
llm_factory.py
Stellt das Sprachmodell bereit: Verwendet ChatOpenAI bei verfügbarem API-Key
(entweder via Environment oder dynamisch über Frontend-Sidebar übergeben)
oder ein deterministisches MockCustomerServiceLLM für testsichere und API-key-freie Ausführungen.
"""

import os
import re
from typing import Any, Optional, Type
from langchain_core.messages import AIMessage, HumanMessage
from models import ExtractedReturnInfo
import i18n


class MockStructuredExtractor:
    """Simuliert LLM with_structured_output für Intent-, Sprach- und Entitätsextraktion."""

    def __init__(self, output_schema: Type[ExtractedReturnInfo]):
        self.output_schema = output_schema

    def invoke(self, input_val: Any) -> ExtractedReturnInfo:
        human_messages = []
        active_topic = None
        if isinstance(input_val, list):
            for m in input_val:
                if isinstance(m, HumanMessage):
                    human_messages.append(str(m.content))
                elif isinstance(m, dict) and m.get("role") in ["user", "human"]:
                    human_messages.append(str(m.get("content", "")))
                elif hasattr(m, "content"):
                    c = str(m.content)
                    match_topic = re.search(r"Active topic:\s*([a-z_]+)", c, re.IGNORECASE)
                    if match_topic:
                        active_topic = match_topic.group(1).lower()
            if not human_messages:
                for m in input_val:
                    if hasattr(m, "content"):
                        human_messages.append(str(m.content))
        elif hasattr(input_val, "content"):
            human_messages.append(str(input_val.content))
        else:
            human_messages.append(str(input_val))

        full_human_text = "\n".join(human_messages)
        latest_text = human_messages[-1] if human_messages else full_human_text
        latest_lower = latest_text.lower().strip()

        # Sprache aus neuester Nachricht erkennen (bevorzugt Laya)
        lang = i18n.detect_language_simple(latest_text or full_human_text)

        # Regex für Order-ID & E-Mail (dürfen aus Gesprächsverlauf stammen)
        order_matches = re.findall(r"\b(ORD-\d+)\b", full_human_text, re.IGNORECASE)
        order_id = order_matches[-1].upper() if order_matches else None

        email_matches = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", full_human_text)
        email = email_matches[-1].lower() if email_matches else None

        # Semantische Intent-Klassifikation STRIKT basierend auf der AKTUELLEN Nutzernachricht (Turn)
        is_off_topic = False
        if not (order_id and email):
            off_topic_heuristic = r"(\b\d+\s*[\+\-\*\/]\s*\d+\b|\b(?:sort|code|program|python|javascript|prompt|weather|wetter|recipe|rezept|joke|witz)\b)"
            if re.search(off_topic_heuristic, latest_lower, re.IGNORECASE):
                is_off_topic = True

        agb_pattern = r"\b(agb|agbs|richtlinien|zahlung|zahlungsart|zahlungsarten|bezahlen|bezahlung|versand|versandkosten|lieferung|lieferzeit|porto|dauer|garantie|gewährleistung|gutschein|warengutschein|store\s*credit|voucher|rabatt|coupon|terms|condition|conditions|payment|shipping|warranty)\b"
        userdata_pattern = r"\b(adresse|lieferadresse|rechnungsadresse|umzug|umgezogen|nutzerdaten|daten\s+anpassen|adresse\s+ändern|daten\s+ändern|profil|profil\s+anpassen|update\s+address|change\s+address|email\s+ändern|e-mail\s+ändern)\b"
        greeting_pattern = r"^(?:hallo|guten\s+tag|guten\s+morgen|guten\s+abend|hi|hello|hey|moin|servus|grüße)\b"
        return_pattern = r"\b(retoure|retouren|retournier\w*|rücksend\w*|zurück\w*|widerruf\w*|erstatten|erstattung|umtausch\w*|reklam\w*|return\w*|refund\w*|exchange)\b"

        if is_off_topic and not (order_id and email):
            intent = "off_topic"
        elif re.search(agb_pattern, latest_lower, re.IGNORECASE):
            intent = "agb"
        elif re.search(userdata_pattern, latest_lower, re.IGNORECASE) or latest_lower in ["email", "e-mail", "adresse", "name"]:
            intent = "nutzerdaten"
        elif re.search(return_pattern, latest_lower, re.IGNORECASE):
            intent = "retoure"
        elif re.search(greeting_pattern, latest_lower, re.IGNORECASE):
            intent = "greeting"
        elif "ord-" in latest_lower or (order_id and ("@" in latest_lower or "ord-" in latest_lower)):
            intent = "retoure"
        elif active_topic in ["agb", "nutzerdaten", "retoure"]:
            # Kontextuelle Beibehaltung bei Folgefragen (z. B. "Warengutschein?", "Wie lange?")
            intent = active_topic
        else:
            intent = "greeting"

        return self.output_schema(intent=intent, language=lang, order_id=order_id, email=email)


class MockCustomerServiceLLM:
    """
    Mock-LLM, das für alle Phasen (Extraktion, AGB-RAG, Erfolgsnachricht, Eskalationszusammenfassung)
    lokalisierte und sprachangepasste Antworten über i18n erzeugt.
    """

    def with_structured_output(self, schema: Type[Any]):
        if schema == ExtractedReturnInfo:
            return MockStructuredExtractor(schema)
        return MockStructuredExtractor(ExtractedReturnInfo)

    def invoke(self, messages: Any) -> AIMessage:
        prompt_text = ""
        if isinstance(messages, list):
            for m in messages:
                if hasattr(m, "content"):
                    prompt_text += f"\n{m.content}"
                elif isinstance(m, dict):
                    prompt_text += f"\n{m.get('content', '')}"
        elif hasattr(messages, "content"):
            prompt_text = str(messages.content)
        else:
            prompt_text = str(messages)

        prompt_lower = prompt_text.lower()
        lang_req = re.search(r"customer's language\s*\(?([a-z]{2})\)?", prompt_text, re.IGNORECASE)
        if lang_req:
            lang = lang_req.group(1).lower()
        else:
            lang = i18n.detect_language_simple(prompt_text)

        # Ermittle die konkrete Kundenfrage
        user_question = ""
        if isinstance(messages, list):
            for m in reversed(messages):
                if isinstance(m, HumanMessage):
                    user_question = str(m.content).lower()
                    break
        query_target = user_question or prompt_lower

        # Fall 0: AGB-RAG Beantwortung
        if any(w in prompt_lower for w in ["terms & conditions", "agb context", "agb-kontext", "agb"]):
            if any(w in query_target for w in ["zahlung", "bezahl", "payment"]):
                if lang == "en":
                    return AIMessage(content="According to § 4 of our Terms & Conditions, we offer the following payment methods:\n- Credit Card (Visa, MasterCard, American Express)\n- PayPal\n- Klarna (Invoice with 30-day payment term, instant bank transfer)\n- Apple Pay & Google Pay\n- Prepayment via bank transfer")
                return AIMessage(content="Gemäß § 4 unserer AGB bieten wir folgende Zahlungsmethoden an:\n- Kreditkarte (Visa, MasterCard, American Express)\n- PayPal (inkl. PayPal Express & Später Bezahlen)\n- Klarna (Rechnungskauf mit 30 Tagen Zahlungsziel, Sofortüberweisung)\n- Apple Pay & Google Pay\n- Vorkasse per Banküberweisung")
            elif any(w in query_target for w in ["garantie", "gewährleistung", "warranty"]):
                if lang == "en":
                    return AIMessage(content="According to § 6 of our Terms & Conditions, a statutory warranty of 24 months applies to all new products.")
                return AIMessage(content="Gemäß § 6 unserer AGB gilt für alle Neuwaren die gesetzliche Gewährleistungsfrist von 24 Monaten ab Übergabe der Ware.")
            elif any(w in query_target for w in ["versand", "liefer", "shipping", "delivery", "porto"]):
                if lang == "en":
                    return AIMessage(content="According to § 3 of our Terms & Conditions, shipping within Germany is free for orders over €50.00 (€4.95 for lower values). Standard delivery takes 2 to 4 business days.")
                return AIMessage(content="Gemäß § 3 unserer AGB ist der Standardversand innerhalb Deutschlands ab 50,00 € versandkostenfrei (darunter 4,95 € Pauschale). Die Lieferzeit beträgt 2 bis 4 Werktage.")
            elif any(w in query_target for w in ["gutschein", "warengutschein", "voucher", "store credit"]):
                if lang == "en":
                    return AIMessage(content="According to § 5 (2) of our Terms & Conditions, returns during the goodwill grace period (15 to 30 days after delivery) are issued as a store credit voucher for the full purchase value, redeemable for future orders.")
                return AIMessage(content="Gemäß § 5 Abs. 2 unserer AGB erhalten Sie bei einer Rückgabe im Kulanzzeitraum (15 bis 30 Tage nach Zustellung) einen Warengutschein (Store Credit) in voller Höhe des Kaufpreises für Ihre Retoure. Dieser kann für zukünftige Einkäufe in unserem Shop eingelöst werden.")
            elif any(w in query_target for w in ["adresse", "nutzerdaten", "daten"]):
                if lang == "en":
                    return AIMessage(content="According to § 7 of our Terms & Conditions, customers can update their shipping, billing address and account details at any time in the portal or via customer support.")
                return AIMessage(content="Gemäß § 7 unserer AGB können Sie Ihre Liefer- und Rechnungsadresse sowie Profildaten jederzeit in Ihrem Kundenkonto oder über unseren Kundenservice aktualisieren lassen.")
            else:
                if lang == "en":
                    return AIMessage(content="According to our Terms & Conditions (§ 5), you have a 14-day statutory return period for a full refund, and an extended 15-30 day grace period for store credit.")
                return AIMessage(content="Gemäß § 5 unserer AGB haben Sie ein 14-tägiges gesetzliches Widerrufsrecht (volle Rückerstattung) sowie eine Kulanzfrist von 15 bis 30 Tagen gegen Warengutschein.")

        # Fall 1: Eskalations-Zusammenfassung für Support-Ticket
        if any(w in prompt_lower for w in ["zusammenfassung", "summary", "support-ticket", "ticket"]):
            if "auth_failed" in prompt_lower:
                return AIMessage(content=i18n.get_text("summary_auth_failed", lang=lang))
            if "return_deadline_exceeded" in prompt_lower or "deadline" in prompt_lower or "frist" in prompt_lower:
                return AIMessage(content=i18n.get_text("summary_deadline_exceeded", lang=lang))
            if "emotional_escalation" in prompt_lower or "emotional" in prompt_lower or "frustrat" in prompt_lower:
                return AIMessage(content=i18n.get_text("summary_emotional", lang=lang))
            return AIMessage(content=i18n.get_text("summary_system_error", lang=lang))

        # Fall 2: Eskalationsmitteilung an Kunden
        if any(w in prompt_lower for w in ["übergeben", "handed over", "escalat", "inform"]):
            if "auth_failed" in prompt_lower:
                return AIMessage(content=i18n.get_text("escalate_auth_failed", lang=lang, max_attempts=3))
            elif "return_deadline_exceeded" in prompt_lower or "deadline" in prompt_lower or "frist" in prompt_lower:
                return AIMessage(content=i18n.get_text("escalate_deadline_exceeded", lang=lang))
            elif "emotional_escalation" in prompt_lower or "emotional" in prompt_lower or "frustrat" in prompt_lower:
                return AIMessage(content=i18n.get_text("escalate_emotional", lang=lang))
            else:
                return AIMessage(content=i18n.get_text("escalate_system_error", lang=lang))

        # Fall 3: Erfolgsmeldung Retoure
        if any(w in prompt_lower for w in ["retoure", "return", "refund", "verbucht", "erfolgreich", "booked"]):
            if "return-type: store_credit" in prompt_lower or ("store_credit" in prompt_lower and "return-type: refund" not in prompt_lower):
                return AIMessage(content=i18n.get_text("success_credit", lang=lang, label_url="{label_url}"))
            else:
                return AIMessage(content=i18n.get_text("success_refund", lang=lang, label_url="{label_url}"))

        # Standard-Antwort
        return AIMessage(content=i18n.get_text("greeting_response", lang=lang))


def get_llm(
    force_mock: bool = False,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_name: Optional[str] = None
):
    effective_key = (api_key or "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    effective_base_url = (base_url or "").strip() or os.getenv("OPENAI_BASE_URL", "").strip() or os.getenv("OPENAI_API_BASE", "").strip()
    effective_model = (model_name or "").strip() or os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if effective_key and not force_mock:
        try:
            from langchain_openai import ChatOpenAI
            kwargs = {
                "model": effective_model,
                "temperature": 0,
                "api_key": effective_key,
            }
            if effective_base_url:
                kwargs["base_url"] = effective_base_url
            return ChatOpenAI(**kwargs)
        except (ImportError, ValueError) as e:
            # ImportError: langchain_openai not installed
            # ValueError: numpy/transformers version check failure (Anaconda env conflict)
            print(f"[WARN] ChatOpenAI nicht verfügbar ({type(e).__name__}: {e}). Verwende Mock-LLM.")
            print("[HINT] Starte den Server mit: .venv/bin/python main.py")
            return MockCustomerServiceLLM()
        except Exception as e:
            print(f"[WARN] ChatOpenAI konnte nicht initialisiert werden ({e}). Verwende Mock-LLM.")
            return MockCustomerServiceLLM()

    return MockCustomerServiceLLM()
