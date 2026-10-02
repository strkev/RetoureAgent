"""
i18n.py
Zentrales Lokalisierungs- und Template-Modul (Internationalisierung).
Trennt Formulierung/Copy vollständig von Steuerungs- und Graphenlogik.
Unterstützt standardmäßig Deutsch ('de') und Englisch ('en'),
erweiterbar um beliebige weitere Sprachen.
"""

from typing import Any, Dict, Optional

# Standard-Fallback-Sprache
DEFAULT_LANGUAGE = "de"

# ---------------------------------------------------------------------------
# Strukturierter Text-Katalog für UI- & Agenten-Nachrichten
# ---------------------------------------------------------------------------
MESSAGES: Dict[str, Dict[str, str]] = {
    "de": {
        # Begrüßung
        "welcome_initial": "Guten Tag! Wie kann ich Ihnen mit Ihrer Bestellung oder Retoure weiterhelfen?",
        "greeting_response": (
            "Guten Tag! Wie kann ich Ihnen heute behilflich sein?\n\n"
            "Ich unterstütze Sie gerne bei:\n"
            "- **Retoure & Rückgabe**: Wenn Sie einen Artikel zurückgeben oder erstatten möchten\n"
            "- **AGB & Richtlinien**: Fragen zu Zahlungsarten, Versandkosten, Lieferzeiten oder Garantie\n"
            "- **Nutzerdaten anpassen**: Aktualisierung von Liefer-/Rechnungsadresse oder Kontaktdaten\n\n"
            "Worum geht es in Ihrem Fall?"
        ),
        
        # Nutzerdaten anpassen
        "user_data_notice": (
            "Gerne helfe ich Ihnen bei der Aktualisierung Ihrer Nutzerdaten (z. B. Name, Lieferadresse oder Kontaktdaten). "
            "Welche Angaben möchten Sie anpassen? Bitte teilen Sie mir die gewünschten Änderungen mit."
        ),
        "user_data_login_prompt": (
            "Um Ihre Kundendaten einsehen und anpassen zu können, melden Sie sich bitte in Ihrem Kundenkonto an."
        ),
        "user_data_authenticated": (
            "Sie sind als **{name} {nachname}** ({account_id}) angemeldet. Sie können Ihre Lieferadresse, Telefonnummer und Namen anpassen. "
            "Anmeldedaten (E-Mail und Passwort) sind aus Sicherheitsgründen geschützt."
        ),
        
        # Datenerfassung (Retoure)
        "request_both": "Um Ihre Retoure bearbeiten zu können, benötige ich bitte Ihre Bestellnummer (z. B. ORD-1001) und Ihre E-Mail-Adresse.",
        "request_order": "Um Ihre Retoure bearbeiten zu können, benötige ich bitte Ihre Bestellnummer (z. B. ORD-1001).",
        "request_email": "Um Ihre Retoure bearbeiten zu können, benötige ich bitte Ihre E-Mail-Adresse.",
        
        # Off-Topic / Prompt-Injection Abweisung
        "off_topic_decline": (
            "Ich bin Ihr digitaler Kundenservice-Assistent für Bestellungen und Retouren. "
            "Themenfremde Anfragen, Rechen- oder Programmieraufgaben kann ich leider nicht bearbeiten.\n\n"
            "Gerne helfe ich Ihnen bei Ihrer Rücksendung weiter! {extra_info}"
        ),
        "off_topic_ask_both": "Bitte nennen Sie mir dazu Ihre Bestellnummer (z. B. ORD-1001) und Ihre E-Mail-Adresse.",
        "off_topic_ask_order": "Bitte nennen Sie mir dazu noch Ihre Bestellnummer (z. B. ORD-1001).",
        "off_topic_ask_email": "Bitte nennen Sie mir dazu noch Ihre E-Mail-Adresse.",
        "off_topic_ask_continue": "Möchten Sie mit Ihrer Retoure fortfahren?",
        
        # Authentifizierung
        "auth_retry": (
            "Die angegebenen Daten stimmen leider nicht mit unseren Unterlagen überein. "
            "Bitte prüfen Sie Ihre Bestellnummer und E-Mail-Adresse erneut und geben Sie diese noch einmal ein. "
            "(Versuch {attempt} von {max_attempts})"
        ),
        
        # Erfolgsmeldungen
        "success_refund": (
            "Ihre Retoure wurde erfolgreich erfasst. Da Ihre Bestellung innerhalb der 14-tägigen Frist liegt, "
            "erstatten wir den vollen Kaufbetrag auf Ihre ursprüngliche Zahlungsmethode.\n"
            "Ihr frankiertes Retourenlabel können Sie hier herunterladen: {label_url}\n"
            "Vielen Dank für Ihre Bestellung bei uns!"
        ),
        "success_credit": (
            "Ihre Retoure wurde erfolgreich gebucht. Da Ihr Kauf zwischen 15 und 30 Tagen zurückliegt (Kulanzfrist), "
            "erhalten Sie den Betrag in voller Höhe als Store-Guthaben gutgeschrieben.\n"
            "Ihr kostenloses Retourenlabel finden Sie hier: {label_url}\n"
            "Sobald die Rücksendung bei uns eingetroffen ist, wird Ihr Gutschein aktiviert."
        ),
        "return_completed_thanks": (
            "Sehr gerne! Ihre Retoure ist bereits vollständig verbucht und das Label steht bereit. "
            "Kann ich Ihnen noch bei weiteren Fragen (z. B. zu unseren AGBs oder Ihren Nutzerdaten) helfen?"
        ),
        "return_completed_already": (
            "Ihre Retoure für diese Bestellung wurde bereits erfolgreich gebucht. "
            "Möchten Sie Fragen zu unseren AGBs klären oder Ihre Kundendaten im Profil anpassen?"
        ),
        
        # Eskalation & Human-in-the-Loop
        "escalate_auth_failed": (
            "Wir konnten Ihre Bestelldaten nach {max_attempts} Versuchen leider nicht automatisch verifizieren. "
            "Zu Ihrer eigenen Sicherheit haben wir Ihr Anliegen an einen menschlichen Kundenservice-Mitarbeiter übergeben. "
            "Ein Kollege wird sich in Kürze per E-Mail bei Ihnen melden, um die Angaben manuell abzugleichen."
        ),
        "escalate_deadline_exceeded": (
            "Da die reguläre 30-tägige Rückgabefrist für diese Bestellung bereits überschritten ist, "
            "habe ich Ihr Anliegen direkt an unser Support-Team übergeben. "
            "Ein Mitarbeiter prüft nun eine Kulanzregelung für Sie und wird sich in Kürze per E-Mail melden."
        ),
        "escalate_system_error": (
            "Bei der Bearbeitung Ihres Anliegens ist ein unerwarteter Systemfehler aufgetreten. "
            "Ihr Vorgang wurde automatisch an unser Support-Team übergeben. "
            "Ein Mitarbeiter wird sich schnellstmöglich bei Ihnen melden."
        ),
        "escalate_emotional": (
            "Ich verstehe Ihren Unmut vollkommen und bedaure die entstandenen Unannehmlichkeiten sehr. "
            "Damit Ihr Anliegen schnell, persönlich und mit höchster Priorität gelöst werden kann, habe ich Ihren Vorgang "
            "direkt an unser Support-Team übergeben. Ein Kollege wird sich zeitnah persönlich bei Ihnen melden."
        ),
        
        # Zusammenfassung für internes Ticket
        "summary_auth_failed": (
            "Kunde konnte nach mehrfachen Fehlversuchen nicht authentifiziert werden. "
            "Fall wird zur manuellen Identitätsprüfung an das Support-Team übergeben."
        ),
        "summary_deadline_exceeded": (
            "Rückgabefrist überschritten: Das Kaufdatum der Bestellung liegt mehr als 30 Tage zurück. "
            "Übergabe an Support zur Prüfung einer individuellen Kulanzlösung."
        ),
        "summary_system_error": (
            "Kundenanliegen konnte nicht automatisiert gelöst werden und wurde an das Support-Team übergeben."
        ),
        "summary_emotional": (
            "Wiederholte Kundenfrustration: Der Kunde hat mehrfach deutlichen Unmut geäußert. "
            "Übergabe an den menschlichen Support zur Deeskalation und persönlichen Klärung."
        ),
        "recommended_action_auth": "Manuelle Identitätsprüfung durchführen ({attempts} Fehlversuche bei Authentifizierung).",
        "recommended_action_deadline": "Kulanzgutschrift prüfen (Kauf vor {days} Tagen, reguläre Frist 30 Tage überschritten).",
        "recommended_action_error": "Technischen Fehler analysieren und Kunden manuell kontaktieren.",
        "recommended_action_emotional": "Empathische Deeskalation und priorisierte Fallbearbeitung durch Senior Support Agent.",
    },

    "en": {
        # Welcome
        "welcome_initial": "Hello! How can I assist you with your order or return today?",
        "greeting_response": (
            "Hello! How can I assist you today?\n\n"
            "I would be glad to help you with:\n"
            "- **Returns & Refunds**: Return items or check return eligibility\n"
            "- **Terms & Policies (AGB)**: Inquiries about payments, shipping, delivery times, or warranty\n"
            "- **Update User Data**: Change your shipping address, billing address, or contact details\n\n"
            "How can I help you?"
        ),
        
        # User Data Update
        "user_data_notice": (
            "I would be glad to help you update your account details (such as name, shipping address, or contact details). "
            "Which information would you like to update? Please let me know the details."
        ),
        "user_data_login_prompt": (
            "To view and update your account details, please sign in to your customer account."
        ),
        "user_data_authenticated": (
            "You are signed in as **{name} {nachname}** ({account_id}). You can update your shipping address, phone number, and name. "
            "Login credentials (email and password) are protected for security reasons."
        ),
        
        # Data Request (Returns)
        "request_both": "In order to process your return, please provide your order number (e.g. ORD-1001) and your email address.",
        "request_order": "In order to process your return, please provide your order number (e.g. ORD-1001).",
        "request_email": "In order to process your return, please provide your email address.",
        
        # Off-Topic / Prompt-Injection Decline
        "off_topic_decline": (
            "I am your digital customer support assistant for orders and returns. "
            "I cannot answer unrelated questions, math problems, or programming tasks.\n\n"
            "I would be glad to help you with your return! {extra_info}"
        ),
        "off_topic_ask_both": "Please provide your order number (e.g. ORD-1001) and your email address.",
        "off_topic_ask_order": "Please provide your order number (e.g. ORD-1001).",
        "off_topic_ask_email": "Please provide your email address.",
        "off_topic_ask_continue": "Would you like to proceed with your return?",
        
        # Authentication
        "auth_retry": (
            "The details provided do not match our records. "
            "Please check your order number and email address and try again. "
            "(Attempt {attempt} of {max_attempts})"
        ),
        
        # Success Messages
        "success_refund": (
            "Your return has been successfully registered. Since your order is within the 14-day return window, "
            "a full refund will be issued to your original payment method.\n"
            "You can download your prepaid shipping label here: {label_url}\n"
            "Thank you for shopping with us!"
        ),
        "success_credit": (
            "Your return has been successfully booked. Since your order was placed between 15 and 30 days ago (grace period), "
            "the full amount will be credited to your account as store credit.\n"
            "You can find your return shipping label here: {label_url}\n"
            "Once your package arrives, your store credit will be activated."
        ),
        "return_completed_thanks": (
            "You're very welcome! Your return has already been successfully booked. "
            "Can I help you with anything else (such as our terms or your account details)?"
        ),
        "return_completed_already": (
            "Your return for this order has already been successfully booked. "
            "Would you like to ask about our terms or update your account details?"
        ),
        
        # Escalation & Human-in-the-Loop
        "escalate_auth_failed": (
            "We were unable to verify your order details after {max_attempts} attempts. "
            "For your security, your case has been handed over to a human customer support agent. "
            "A team member will reach out to you via email shortly to assist you personally."
        ),
        "escalate_deadline_exceeded": (
            "Since the regular 30-day return window for this order has expired, "
            "I have forwarded your request directly to our customer support team. "
            "An agent is reviewing a goodwill solution and will contact you via email shortly."
        ),
        "escalate_system_error": (
            "An unexpected system error occurred while processing your request. "
            "Your case has been automatically escalated to our support team. "
            "An agent will get back to you as soon as possible."
        ),
        "escalate_emotional": (
            "I completely understand your frustration and sincerely apologize for the inconvenience. "
            "To ensure your concern is resolved promptly and with personal care, I have escalated "
            "your case directly to our support team. A representative will contact you personally shortly."
        ),
        
        # Summary for internal ticket
        "summary_auth_failed": (
            "Customer could not be authenticated after multiple attempts. "
            "Case transferred to support team for manual identity verification."
        ),
        "summary_deadline_exceeded": (
            "Return deadline exceeded: Purchase date was more than 30 days ago. "
            "Handed over to support to assess goodwill store credit."
        ),
        "summary_system_error": (
            "Customer request could not be resolved automatically and was handed over to support."
        ),
        "summary_emotional": (
            "Repeated customer frustration: Customer expressed significant discontent across multiple turns. "
            "Escalated to human support for de-escalation and personal resolution."
        ),
        "recommended_action_auth": "Perform manual identity verification ({attempts} failed authentication attempts).",
        "recommended_action_deadline": "Review goodwill credit (purchased {days} days ago, standard 30-day window exceeded).",
        "recommended_action_error": "Analyze technical error and contact customer directly.",
        "recommended_action_emotional": "Empathetic de-escalation and prioritized handling by a senior support representative.",
    }
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen für Lokalisierung
# ---------------------------------------------------------------------------

def normalize_language(lang_code: Optional[str]) -> str:
    """Normalisiert einen Sprachcode (z. B. 'de-DE' -> 'de', 'EN' -> 'en')."""
    if not lang_code:
        return DEFAULT_LANGUAGE
    code = lang_code.strip().lower()[:2]
    return code if code in MESSAGES else DEFAULT_LANGUAGE


def detect_language_simple(text: str) -> str:
    """
    Erkennt die Sprache modellbasiert mittels Laya (sub-millisecond analyse)
    ohne hardcodierte Signalwort-Listen.
    Fällt bei unentschiedenem Text auf die Default-Sprache ('de') zurück.
    """
    if not text:
        return DEFAULT_LANGUAGE

    try:
        from laya.lang import analyse
        res = analyse(text)
        detected = res.get("language")
        if detected and not res.get("language_undecided"):
            return normalize_language(detected)
    except Exception:
        pass

    return DEFAULT_LANGUAGE


def get_text(key: str, lang: Optional[str] = None, **kwargs: Any) -> str:
    """
    Gibt den lokalisierten Textbaustein für den Schlüssel zurück.
    Fällt bei fehlendem Text auf die Default-Sprache ('de') zurück.
    Unterstützt Python-Format-Strings (z. B. {label_url}, {attempt}).
    """
    language = normalize_language(lang)
    catalog = MESSAGES.get(language, MESSAGES[DEFAULT_LANGUAGE])
    
    # Fallback auf Standard-Katalog, falls Schlüssel in Sprache nicht existiert
    template = catalog.get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LANGUAGE].get(key, f"[{key}]")

    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template
