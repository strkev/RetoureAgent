"""
test_flows.py
Zusätzliche modulare Unit- und Integrationstests:
- Schrittweise Datenabfrage (Missing Data Handling)
- Tool-Sperre nach Eskalation
- Pydantic Validierung von HandoffPayload
"""

import unittest
from uuid import uuid4
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from graph import create_return_graph
from models import EscalationReason, HandoffPayload
from repository import MockOrderRepository


class TestCustomerServiceFlows(unittest.TestCase):

    def setUp(self):
        self.repo = MockOrderRepository()

    def test_incremental_data_collection(self):
        """Testet, dass fehlende Daten nacheinander erfragt werden."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-incremental-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: Kunde sagt nur "Ich möchte retournieren"
        r1 = app.invoke({"messages": [HumanMessage(content="Hallo, ich möchte einen Artikel zurückgeben.")]}, config=config)
        self.assertEqual(r1["next_step"], "wait_for_input")
        self.assertIn("Bestellnummer", r1["messages"][-1].content)
        self.assertIn("E-Mail-Adresse", r1["messages"][-1].content)

        # Turn 2: Kunde nennt nur Bestellnummer
        r2 = app.invoke({"messages": [HumanMessage(content="Meine Bestellnummer ist ORD-1001")]}, config=config)
        self.assertEqual(r2["next_step"], "wait_for_input")
        self.assertEqual(r2["order_id"], "ORD-1001")
        self.assertIn("E-Mail-Adresse", r2["messages"][-1].content)

        # Turn 3: Kunde liefert E-Mail nach -> Prüfung erfolgt, Zusammenfassung & Bestätigung wird angefordert
        r3 = app.invoke({"messages": [HumanMessage(content="Hier ist meine Mail: kunde1@example.com")]}, config=config)
        self.assertEqual(r3["auth_status"], True)
        self.assertEqual(r3["next_step"], "await_confirmation")
        self.assertIsNotNone(r3.get("pending_return_summary"))
        self.assertIn("ORD-1001", r3["messages"][-1].content)

        # Turn 4: Kunde bestätigt die Retoure
        r4 = app.invoke({"messages": [HumanMessage(content="Ja, ich bestätige die Retoure.")]}, config=config)
        self.assertEqual(r4["auth_status"], True)
        self.assertEqual(r4["return_booking"]["return_type"], "refund")
        self.assertEqual(r4["next_step"], "END")
        self.assertTrue(r4["return_completed"])

    def test_repository_rules(self):
        """Testet die Repository-Logik isoliert."""
        # Valid vs Invalid
        self.assertTrue(self.repo.verify_order("ORD-1001", "kunde1@example.com"))
        self.assertTrue(self.repo.verify_order("ord-1001 ", " KUNDE1@EXAMPLE.COM "))
        self.assertFalse(self.repo.verify_order("ORD-1001", "wrong@example.com"))
        self.assertFalse(self.repo.verify_order("ORD-9999", "kunde1@example.com"))

        # Details & Days
        d1 = self.repo.get_order_details("ORD-1001")
        self.assertIsNotNone(d1)
        self.assertLessEqual(d1["days_since_purchase"], 14)

        d2 = self.repo.get_order_details("ORD-1002")
        self.assertGreater(d2["days_since_purchase"], 14)
        self.assertLessEqual(d2["days_since_purchase"], 30)

        d3 = self.repo.get_order_details("ORD-1003")
        self.assertGreater(d3["days_since_purchase"], 30)

    def test_handoff_payload_schema(self):
        """Testet die strikte Pydantic-Validierung des Handoff-Payloads."""
        payload = HandoffPayload(
            order_id="ORD-1003",
            customer_email="kunde3@example.com",
            escalation_reason=EscalationReason.RETURN_DEADLINE_EXCEEDED,
            summary="Frist abgelaufen.",
            recommended_action="Kulanzgutschrift prüfen",
            chat_history=[{"role": "customer", "content": "Hilfe"}]
        )
        data = payload.model_dump()
        self.assertIn("case_id", data)
        self.assertEqual(data["escalation_reason"], "RETURN_DEADLINE_EXCEEDED")

    def test_multilingual_english_return(self):
        """Testet vollständigen englischsprachigen Dialogablauf mit Sprachspiegelung."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-en-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: English request with order and email -> prompts confirmation summary
        r = app.invoke({"messages": [HumanMessage(content="Hello, I want to return my order ORD-1001. My email is kunde1@example.com")]}, config=config)
        self.assertEqual(r["language"], "en")
        self.assertEqual(r["auth_status"], True)
        self.assertEqual(r["next_step"], "await_confirmation")

        # Turn 2: Customer confirms return
        r2 = app.invoke({"messages": [HumanMessage(content="Yes, please confirm the return for all items.")]}, config=config)
        self.assertEqual(r2["auth_status"], True)
        self.assertIsNotNone(r2["return_booking"])
        bot_response = r2["messages"][-1].content
        self.assertIn("Your return has been successfully registered", bot_response)
        self.assertIn("RET-", bot_response)

    def test_multilingual_english_offtopic(self):
        """Testet Abweisung themenfremder englischer Anfragen (Off-Topic)."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-en-off-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        r = app.invoke({"messages": [HumanMessage(content="Can you write a sorting algorithm in Python?")]}, config=config)
        bot_response = r["messages"][-1].content
        self.assertEqual(r["language"], "en")
        self.assertIsNone(r["order_id"])
        self.assertIn("digital customer support assistant", bot_response)
        self.assertIn("cannot answer unrelated questions", bot_response)

    def test_clean_chat_output_universal(self):
        """Testet die universelle, sprachunabhängige Bereinigung von LLM-Ausgaben."""
        from graph import clean_chat_output

        # Testfall Deutsch mit Betreff-Header
        de_raw = "Betreff: Ihre Retourenbestätigung\n\nHallo,\nIhre Retoure wurde erfasst."
        self.assertEqual(clean_chat_output(de_raw), "Hallo,\nIhre Retoure wurde erfasst.")

        # Testfall Englisch mit Subject-Header
        en_raw = "Subject: Return Confirmation #1234\n\nDear Customer,\nYour return is approved."
        self.assertEqual(clean_chat_output(en_raw), "Dear Customer,\nYour return is approved.")

        # Testfall Französisch mit Objet-Header
        fr_raw = "Objet: Confirmation de retour\n\nBonjour,\nVotre retour a été validé."
        self.assertEqual(clean_chat_output(fr_raw), "Bonjour,\nVotre retour a été validé.")

        # Testfall Markdown-Block
        md_raw = "```markdown\nIhre Retoure ist gebucht.\n```"
        self.assertEqual(clean_chat_output(md_raw), "Ihre Retoure ist gebucht.")

    def test_agb_rag_payment_inquiry(self):
        """Testet die Beantwortung von AGB-Fragen zu Zahlungsmethoden mittels RAG."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-agb-pay-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        r = app.invoke({"messages": [HumanMessage(content="Welche Zahlungsmethoden akzeptiert ihr laut AGB?")]}, config=config)
        self.assertEqual(r.get("current_intent"), "agb")
        self.assertEqual(r.get("last_active_node"), "node_agb_rag")
        self.assertIsNotNone(r.get("agb_context"))
        self.assertGreater(len(r["agb_context"]), 0)
        # Überprüfe, dass § 4 Zahlungsbedingungen gefunden wurde
        self.assertTrue(any("Zahlung" in c["title"] for c in r["agb_context"]))
        bot_response = r["messages"][-1].content
        self.assertTrue(any(method in bot_response for method in ["PayPal", "Kreditkarte", "Klarna"]))

    def test_agb_rag_warranty_inquiry_english(self):
        """Testet englische AGB-Frage zur Gewährleistung."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-agb-war-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        r = app.invoke({"messages": [HumanMessage(content="What is the warranty policy according to your terms?")]}, config=config)
        self.assertEqual(r.get("current_intent"), "agb")
        self.assertEqual(r.get("last_active_node"), "node_agb_rag")
        self.assertIsNotNone(r.get("agb_context"))
        bot_response = r["messages"][-1].content
        self.assertTrue("24 months" in bot_response or "warranty" in bot_response.lower())

    def test_user_data_update_intent(self):
        """Testet die Erkennung und Bestätigung des Intents 'nutzerdaten'."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-usr-data-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        r = app.invoke({"messages": [HumanMessage(content="Ich bin umgezogen und möchte meine Lieferadresse anpassen.")]}, config=config)
        self.assertEqual(r.get("current_intent"), "nutzerdaten")
        self.assertEqual(r.get("last_active_node"), "node_user_data")
        bot_response = r["messages"][-1].content
        self.assertTrue(any(w in bot_response.lower() for w in ["nutzerdaten", "adresse", "anpassen", "ändern"]))

    def test_dynamic_intent_switching_and_greeting(self):
        """Testet dynamischen Intent-Wechsel und neutrale Begrüßung ohne vorschnellen Retouren-Zwang."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-switch-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: Begrüßung ("Hallo") -> neutral, keine Order-ID gefordert
        r1 = app.invoke({"messages": [HumanMessage(content="Hallo")]}, config=config)
        self.assertEqual(r1.get("current_intent"), "greeting")
        self.assertEqual(r1.get("last_active_node"), "node_process_input")
        self.assertNotIn("ORD-1001", r1["messages"][-1].content)
        self.assertIn("Retoure", r1["messages"][-1].content)
        self.assertIn("AGB", r1["messages"][-1].content)
        self.assertIn("Nutzerdaten", r1["messages"][-1].content)

        # Turn 2: Wechsel zu Nutzerdaten
        r2 = app.invoke({"messages": [HumanMessage(content="Ich möchte meine Nutzerdaten ändern")]}, config=config)
        self.assertEqual(r2.get("current_intent"), "nutzerdaten")
        self.assertEqual(r2.get("last_active_node"), "node_user_data")

        # Turn 3: Wechsel zu AGB ("Lieber doch agbs")
        r3 = app.invoke({"messages": [HumanMessage(content="Lieber doch agbs")]}, config=config)
        self.assertEqual(r3.get("current_intent"), "agb")
        self.assertEqual(r3.get("last_active_node"), "node_agb_rag")

        # Turn 4: Konkrete AGB-Frage
        r4 = app.invoke({"messages": [HumanMessage(content="Welche AGBs gelten für meine bestellung?")]}, config=config)
        self.assertEqual(r4.get("current_intent"), "agb")
        self.assertEqual(r4.get("last_active_node"), "node_agb_rag")

        # Turn 5: Wechsel zu Retoure -> fordert Bestätigung an
        r5 = app.invoke({"messages": [HumanMessage(content="Ich möchte jetzt doch meine Bestellung ORD-1001 retournieren mit kunde1@example.com")]}, config=config)
        self.assertEqual(r5.get("current_intent"), "retoure")
        self.assertEqual(r5.get("auth_status"), True)
        self.assertEqual(r5.get("next_step"), "await_confirmation")

        # Turn 6: Bestätigung der Retoure
        r6 = app.invoke({"messages": [HumanMessage(content="Ja, bitte bestätigen.")]}, config=config)
        self.assertIsNotNone(r6.get("return_booking"))
        self.assertTrue(r6.get("return_completed"))

    def test_partial_return_specific_item(self):
        """Testet die Teil-Retoure: Kunde wählt gezielt nur ein Produkt (Bürostuhl) aus."""
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-partial-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: Kunde meldet Retoure an
        r1 = app.invoke({"messages": [HumanMessage(content="Retoure für ORD-1001, Mail kunde1@example.com")]}, config=config)
        self.assertEqual(r1["auth_status"], True)
        self.assertEqual(r1["next_step"], "await_confirmation")
        self.assertEqual(len(r1["pending_return_summary"]["items"]), 2)

        # Turn 2: Kunde möchte nur den Bürostuhl zurückgeben
        r2 = app.invoke({"messages": [HumanMessage(content="Ich möchte nur den Bürostuhl zurückgeben und die Retoure bestätigen.")]}, config=config)
        self.assertEqual(r2["auth_status"], True)
        self.assertTrue(r2["return_completed"])
        booking = r2["return_booking"]
        self.assertIsNotNone(booking)
        self.assertEqual(len(booking["items"]), 1)
        self.assertEqual(booking["items"][0]["item_id"], "ART-901")
        self.assertEqual(booking["total_refund"], 199.99)

    def test_contextual_follow_up_questions_retain_topic(self):
        """
        Testet, dass kurze Rückfragen wie 'Warengutschein?' oder 'Um den Warengutschein'
        den aktiven Kontext ('agb') beibehalten und NICHT fälschlicherweise zu 'greeting' zurückfallen.
        """
        checkpointer = MemorySaver()
        app = create_return_graph(checkpointer=checkpointer)
        thread_id = f"test-ctx-{uuid4().hex[:6]}"
        config = {"configurable": {"thread_id": thread_id}}

        # Turn 1: Begrüßung ("Hallo")
        r1 = app.invoke({"messages": [HumanMessage(content="Hallo")]}, config=config)
        self.assertEqual(r1.get("current_intent"), "greeting")

        # Turn 2: Frage nach AGB bzgl. Retoure
        r2 = app.invoke({"messages": [HumanMessage(content="Welche AGBs gelten für meine Retoure?")]}, config=config)
        self.assertEqual(r2.get("current_intent"), "agb")
        self.assertEqual(r2.get("last_active_node"), "node_agb_rag")
        self.assertIn("Warengutschein", r2["messages"][-1].content)

        # Turn 3: Kurze Rückfrage "Warengutschein?" (DARF NICHT zu greeting werden!)
        r3 = app.invoke({"messages": [HumanMessage(content="Warengutschein?")]}, config=config)
        self.assertEqual(r3.get("current_intent"), "agb")
        self.assertEqual(r3.get("last_active_node"), "node_agb_rag")
        # Darf KEINE generische Begrüßung enthalten
        self.assertNotIn("Guten Tag! Wie kann ich Ihnen heute behilflich sein?", r3["messages"][-1].content)
        # Soll den Warengutschein aus den AGB erklären
        self.assertTrue(any(w in r3["messages"][-1].content.lower() for w in ["warengutschein", "store credit", "gutschein"]))

        # Turn 4: Nachfrage "Um den Warengutschein"
        r4 = app.invoke({"messages": [HumanMessage(content="Um den Warengutschein")]}, config=config)
        self.assertEqual(r4.get("current_intent"), "agb")
        self.assertEqual(r4.get("last_active_node"), "node_agb_rag")
        self.assertNotIn("Guten Tag! Wie kann ich Ihnen heute behilflich sein?", r4["messages"][-1].content)


if __name__ == "__main__":
    unittest.main()


