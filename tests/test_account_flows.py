"""
test_account_flows.py
Testet:
1. Anforderung des Login-Widgets bei unauthentifizierter Nutzerdatenanfrage (Zero-LLM-Leakage).
2. Sichere Authentifizierung über den REST-Endpunkt /api/auth/login.
3. Aktualisierung veränderlicher Stammdaten (Adresse, Land, Telefon, Name).
4. Striktes Verbot der Änderung von Anmeldedaten (E-Mail, Account-ID, Passwort).
5. Vermeidung der Retouren-Schleife (Post-Return Non-Stickiness): Folgefragen nach einer Retoure lösen keine Doppelbuchungen oder wiederkehrende Label-Cards aus.
"""

import json
import unittest
import uuid
from fastapi.testclient import TestClient
from server import app
from repository import get_repository


class TestAccountFlows(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.repo = get_repository()

    def test_auth_widget_requested_when_unauthenticated(self):
        """Prüft, ob bei Kundendatenanfrage ohne Login das interaktive Widget angefordert wird."""
        session_id = "test-auth-req"
        res = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Ich möchte meine Nutzerdaten anpassen."
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        
        # State prüfen
        state = data["state"]
        self.assertEqual(state["current_intent"], "nutzerdaten")
        self.assertTrue(state["auth_widget_requested"])
        self.assertFalse(state["account_authenticated"])
        
        # Prüfen, ob eine Login-Action-Card am Ende anhängt
        last_msg = data["messages"][-1]
        self.assertIsNotNone(last_msg.get("action_card"))
        self.assertEqual(last_msg["action_card"]["type"], "account_login")

    def test_auth_login_endpoint_success_and_failure(self):
        """Prüft Login-Erfolg und -Misserfolg direkt am Auth-Endpunkt."""
        session_id = "test-login-flow"
        # Initial-Chat anstoßen
        self.client.post("/api/chat", json={"session_id": session_id, "message": "Hallo"})

        # Fehlgeschlagener Login
        fail_res = self.client.post("/api/auth/login", json={
            "session_id": session_id,
            "login": "ACC-101",
            "password": "wrongpassword"
        })
        self.assertEqual(fail_res.status_code, 200)
        self.assertFalse(fail_res.json()["success"])

        # Erfolgreicher Login
        success_res = self.client.post("/api/auth/login", json={
            "session_id": session_id,
            "login": "ACC-101",
            "password": "secret123"
        })
        self.assertEqual(success_res.status_code, 200)
        data = success_res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["account"]["account_id"], "ACC-101")
        self.assertEqual(data["state"]["account_authenticated"], True)

        # Letzte Nachricht muss eine account_profile Action-Card besitzen
        last_msg = data["messages"][-1]
        self.assertIsNotNone(last_msg.get("action_card"))
        self.assertEqual(last_msg["action_card"]["type"], "account_profile")

    def test_account_update_profile_and_credential_protection(self):
        """Prüft Aktualisierung von Adressdaten und die strikte Unveränderlichkeit von Anmeldedaten."""
        session_id = "test-update-flow"
        # Einloggen
        self.client.post("/api/chat", json={"session_id": session_id, "message": "Kundendaten"})
        self.client.post("/api/auth/login", json={
            "session_id": session_id,
            "login": "kunde1@example.com",
            "password": "secret123"
        })

        # 1. Erlaubtes Profil-Update (Adresse & Telefonnummer)
        up_res = self.client.post("/api/account/update", json={
            "session_id": session_id,
            "updates": {
                "adresse": "Neuer Wall 99, 20354 Hamburg",
                "telefonnummer": "+49 40 987654"
            }
        })
        self.assertEqual(up_res.status_code, 200)
        data = up_res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["account"]["adresse"], "Neuer Wall 99, 20354 Hamburg")
        self.assertEqual(data["account"]["telefonnummer"], "+49 40 987654")
        # Automatisch eingeklappt: Bestätigungsnachricht darf keine Action-Card mehr tragen
        self.assertIsNone(data["messages"][-1].get("action_card"))

        # 2. Versuch, Anmeldedaten (E-Mail oder Passwort) zu manipulieren -> MUSS abgewiesen werden!
        hack_res = self.client.post("/api/account/update", json={
            "session_id": session_id,
            "updates": {
                "email": "hacked@example.com",
                "password": "newpassword123"
            }
        })
        self.assertEqual(hack_res.status_code, 200)
        hack_data = hack_res.json()
        self.assertFalse(hack_data["success"])
        self.assertIn("Sicherheitsgründen", hack_data["message"])

        # E-Mail in DB muss unverändert sein
        acc_db = self.repo.get_account("ACC-101")
        self.assertEqual(acc_db["email"], "kunde1@example.com")

    def test_post_return_non_stickiness_and_no_loop(self):
        """
        Garantiert, dass nach Abschluss einer Retoure Folgefragen keine erneute Buchung
        auslösen und das Retourenlabel nicht an spätere Nachrichten angehängt wird.
        """
        session_id = "test-post-return"
        
        # 1. Retoure für ORD-1001 anfragen -> fordert Bestätigung an
        r0 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Ich möchte ORD-1001 mit kunde1@example.com zurückgeben."
        })
        self.assertEqual(r0.status_code, 200)
        d0 = r0.json()
        self.assertEqual(d0["state"]["next_step"], "await_confirmation")
        self.assertEqual(d0["messages"][-1]["action_card"]["type"], "return_selection_confirm")

        # 1b. Verbindliche Bestätigung über den REST-Endpunkt
        r1 = self.client.post("/api/return/confirm", json={
            "session_id": session_id,
            "order_id": "ORD-1001",
            "selected_items": ["ART-901", "ART-902"]
        })
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertTrue(d1["state"]["return_completed"])
        # Erste Buchungsantwort muss die PDF-Card haben
        self.assertIsNotNone(d1["messages"][-1]["action_card"])
        self.assertEqual(d1["messages"][-1]["action_card"]["type"], "return_booking_refund")
        orig_return_id = d1["state"]["return_booking"]["return_id"]

        # 2. Folgefrage: Höflicher Dank
        r2 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Super, vielen Dank!"
        })
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        # Darf KEINE erneute Action Card haben
        self.assertIsNone(d2["messages"][-1]["action_card"])
        # Return-ID darf sich nicht verändert haben
        self.assertEqual(d2["state"]["return_booking"]["return_id"], orig_return_id)

        # 3. Folgefrage zu den AGBs: "Was steht in den AGBs über den Warengutschein?"
        r3 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Was steht in den AGBs über den Warengutschein?"
        })
        self.assertEqual(r3.status_code, 200)
        d3 = r3.json()
        self.assertEqual(d3["state"]["current_intent"], "agb")
        # Darf KEINE Return-Action-Card haben
        self.assertIsNone(d3["messages"][-1]["action_card"])
        # Return-ID muss noch dieselbe sein (keine Neubuchung)
        self.assertEqual(d3["state"]["return_booking"]["return_id"], orig_return_id)

    def test_welcome_message_single_and_not_duplicated(self):
        """Prüft, dass die Begrüßungsnachricht genau einmal existiert und synchronisiert ist."""
        session_id = "test-single-welcome"
        res = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Nutzerdaten verändern"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        messages = data["messages"]

        # Genau 1 Willkommensnachricht ganz zu Beginn
        welcome_msgs = [m for m in messages if m.get("id") == "msg-welcome"]
        self.assertEqual(len(welcome_msgs), 1)
        self.assertEqual(
            welcome_msgs[0]["content"],
            "Guten Tag! Wie kann ich Ihnen mit Ihrer Bestellung oder Retoure weiterhelfen?"
        )
        self.assertEqual(messages[0]["id"], "msg-welcome")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "Nutzerdaten verändern")

        # Session Reset Endpunkt prüfen
        reset_res = self.client.post("/api/reset", json={"session_id": session_id})
        self.assertEqual(reset_res.status_code, 200)
        reset_data = reset_res.json()
        self.assertEqual(
            reset_data["welcome_message"]["content"],
            "Guten Tag! Wie kann ich Ihnen mit Ihrer Bestellung oder Retoure weiterhelfen?"
        )
        self.assertEqual(reset_data["welcome_message"]["id"], "msg-welcome")

    def test_laya_intent_and_streaming_endpoint(self):
        """Prüft Laya-Intent-Erkennung, Konfidenzwert und SSE-Streaming über /api/chat/stream."""
        session_id = f"test-laya-stream-{uuid.uuid4().hex[:6]}"
        stream_res = self.client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "message": "Ich möchte meine Kundendaten ändern"
            }
        )
        self.assertEqual(stream_res.status_code, 200)
        lines = stream_res.text.split("\n")
        events = [l for l in lines if l.startswith("data: ")]
        self.assertGreater(len(events), 0)

        # Prüfe finalen 'done' Event mit Intent und Konfidenz
        done_events = [e for e in events if '"type": "done"' in e]
        self.assertEqual(len(done_events), 1)
        done_payload = json.loads(done_events[0].replace("data: ", ""))
        state = done_payload["payload"]["state"]
        self.assertEqual(state["current_intent"], "nutzerdaten")
        self.assertIsNotNone(state.get("intent_confidence"))
        self.assertGreater(state["intent_confidence"], 0.5)

    def test_auth_widget_not_sticky_on_subsequent_different_topic_messages(self):
        """
        Garantiert, dass das Login-Widget NICHT an nachfolgende Nachrichten angehängt wird,
        wenn der Nutzer nach einer Nutzerdatenanfrage zu einem anderen Thema wechselt.
        """
        session_id = f"test-auth-nostick-{uuid.uuid4().hex[:6]}"

        # Turn 1: Nutzer fragt nach Nutzerdaten -> Login-Widget wird angefordert
        r1 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Ich möchte meine Nutzerdaten anpassen."
        })
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertEqual(d1["state"]["current_intent"], "nutzerdaten")
        self.assertIsNotNone(d1["messages"][-1].get("action_card"))
        self.assertEqual(d1["messages"][-1]["action_card"]["type"], "account_login")

        # Turn 2: Nutzer stellt eine AGB-Frage -> Login-Widget darf HIER NICHT erscheinen!
        r2 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Welche Zahlungsarten akzeptiert ihr laut AGB?"
        })
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertEqual(d2["state"]["current_intent"], "agb")
        self.assertIsNone(d2["messages"][-1].get("action_card"))
        self.assertFalse(d2["state"]["auth_widget_requested"])

        # Turn 3: Nutzer leitet Retoure ein -> Login-Widget darf HIER NICHT erscheinen!
        r3 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Ich möchte ORD-1001 retournieren mit kunde1@example.com"
        })
        self.assertEqual(r3.status_code, 200)
        d3 = r3.json()
        self.assertEqual(d3["state"]["current_intent"], "retoure")
        # Retouren-Auswahlcard ja, aber KEINE Login-Card
        self.assertEqual(d3["messages"][-1]["action_card"]["type"], "return_selection_confirm")

    def test_pdf_label_generation_endpoint(self):
        """Prüft, dass der PDF-Endpunkt /api/returns/{return_id}/label.pdf ein gültiges PDF generiert."""
        session_id = f"test-pdf-{uuid.uuid4().hex[:6]}"
        # Retoure anfragen und bestätigen
        self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "ORD-1001 mit kunde1@example.com retournieren"
        })
        conf_res = self.client.post("/api/return/confirm", json={
            "session_id": session_id,
            "order_id": "ORD-1001",
            "selected_items": ["ART-901"]
        })
        self.assertEqual(conf_res.status_code, 200)
        data = conf_res.json()
        return_id = data["state"]["return_booking"]["return_id"]

        # PDF abrufen
        pdf_res = self.client.get(f"/api/returns/{return_id}/label.pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.headers["content-type"], "application/pdf")
        self.assertTrue(pdf_res.content.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", pdf_res.content)
        self.assertGreater(len(pdf_res.content), 500)

    def test_auth_widget_cancel_endpoint_dismisses_widget(self):
        """
        Prüft, dass das Schließen des Widgets über den 'x'-Button (/api/auth/cancel)
        das auth_widget_requested-Flag im State sofort auf False setzt.
        """
        session_id = f"test-auth-cancel-{uuid.uuid4().hex[:6]}"

        # Turn 1: Nutzer fragt nach Nutzerdaten
        r1 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Lieferadresse anpassen"
        })
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertTrue(d1["state"]["auth_widget_requested"])
        self.assertEqual(d1["messages"][-1]["action_card"]["type"], "account_login")

        # Turn 2: Nutzer klickt auf 'x' (cancel)
        cancel_res = self.client.post("/api/auth/cancel", json={"session_id": session_id})
        self.assertEqual(cancel_res.status_code, 200)
        self.assertTrue(cancel_res.json()["success"])

        # Turn 3: Beliebige Folgenachricht (z.B. "Hallo") -> Kein Login-Widget mehr!
        r3 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Hallo nochmal"
        })
        self.assertEqual(r3.status_code, 200)
        d3 = r3.json()
        self.assertIsNone(d3["messages"][-1].get("action_card"))
        self.assertFalse(d3["state"]["auth_widget_requested"])

    def test_emotional_escalation_after_three_frustrated_messages(self):
        """
        Garantiert, dass der Agent nach der 3. emotional/frustriert geladenen Nachricht
        automatisch an den menschlichen Support eskaliert (EMOTIONAL_ESCALATION).
        """
        session_id = f"test-emotion-escl-{uuid.uuid4().hex[:6]}"

        # Turn 1: 1. emotionale Nachricht
        r1 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Das ist doch eine absolute Frechheit hier!"
        })
        self.assertEqual(r1.status_code, 200)
        d1 = r1.json()
        self.assertEqual(d1["state"]["emotional_messages_count"], 1)
        self.assertTrue(d1["state"]["is_frustrated"])
        self.assertIsNone(d1["state"]["handoff_payload"])

        # Turn 2: 2. emotionale Nachricht
        r2 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Ich bin stinksauer, ihr seid total unfähig!"
        })
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertEqual(d2["state"]["emotional_messages_count"], 2)
        self.assertTrue(d2["state"]["is_frustrated"])
        self.assertIsNone(d2["state"]["handoff_payload"])

        # Turn 3: 3. emotionale Nachricht -> Eskalationsschwelle erreicht!
        r3 = self.client.post("/api/chat", json={
            "session_id": session_id,
            "message": "Ihr Saftladen, ich schalte jetzt einen Anwalt ein wegen dieser Abzocke!"
        })
        self.assertEqual(r3.status_code, 200)
        d3 = r3.json()
        self.assertEqual(d3["state"]["emotional_messages_count"], 3)
        self.assertEqual(d3["state"]["last_active_node"], "node_escalate")
        self.assertTrue(d3["state"]["tools_locked"])

        # Handoff-Payload prüfen
        handoff = d3["state"]["handoff_payload"]
        self.assertIsNotNone(handoff)
        self.assertEqual(handoff["escalation_reason"], "EMOTIONAL_ESCALATION")
        self.assertIn("Deeskalation", handoff["recommended_action"])

        # Action-Card an Support übergeben
        last_card = d3["messages"][-1]["action_card"]
        self.assertIsNotNone(last_card)
        self.assertEqual(last_card["type"], "handoff_escalation")
        self.assertEqual(last_card["badge"], "An Support übergeben")


if __name__ == "__main__":
    unittest.main()
