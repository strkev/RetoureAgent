"""
main.py
Haupteinstiegspunkt für den Kundenservice-Agenten.
Startet standardmäßig das Web-Frontend (FastAPI + Uvicorn) auf http://127.0.0.1:8000.
Optional kann weiterhin die automatisierte Testsuite (--test) aufgerufen werden.
"""

import argparse
import socket
import threading
import time
import webbrowser
from typing import List
from uuid import uuid4
import uvicorn
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from graph import create_return_graph
from models import EscalationReason


def run_scenario(title: str, user_inputs: List[str], thread_id: str) -> dict:
    """
    Führt ein einzelnes Szenario mit einem oder mehreren Benutzerzügen (Turns) aus.
    Verwendet MemorySaver für echten Multi-Turn State.
    """
    print("\n" + "#" * 80)
    print(f"  START TESTFALL: {title}")
    print(f"  Thread-ID: {thread_id}")
    print("#" * 80)

    checkpointer = MemorySaver()
    app = create_return_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": thread_id}}

    final_state = {}

    for turn_idx, user_input in enumerate(user_inputs, start=1):
        print(f"\n>>> [KUNDE - TURN {turn_idx}]: \"{user_input}\"")

        initial_input = {"messages": [HumanMessage(content=user_input)]}
        result = app.invoke(initial_input, config=config)
        final_state = result

        last_message = result["messages"][-1]
        print(f"<<< [BOT ANTWORT]:\n{last_message.content}\n")

    return final_state


def run_test_suite() -> None:
    """
    Führt die 4 geforderten Testfälle automatisiert in der Konsole aus und validiert sie.
    """
    print("=" * 80)
    print(" START DER AUTOMATISIERTEN TESTSUITE (4 SZENARIEN)")
    print("=" * 80)

    # FALL 1: Happy Path (<= 14 Tage)
    state_1 = run_scenario(
        title="Fall 1: Happy Path (<= 14 Tage) -> Volle Rückerstattung (refund)",
        user_inputs=[
            "Hallo, ich möchte meine Bestellung ORD-1001 zurückgeben. Meine E-Mail ist kunde1@example.com.",
            "Ich bestätige die Retoure für die ausgewählten Artikel."
        ],
        thread_id=f"thread-test-1-{uuid4().hex[:6]}"
    )
    assert state_1.get("auth_status") is True, "Fall 1: Auth muss erfolgreich sein."
    assert state_1.get("return_booking", {}).get("return_type") == "refund", "Fall 1: Return Type muss 'refund' sein."
    print("  [TEST-ASSERTION] Fall 1 ERFOLGREICH: Retoure als 'refund' mit Label gebucht.")

    # FALL 2: Kulanzfrist (15-30 Tage)
    state_2 = run_scenario(
        title="Fall 2: Kulanzfrist (15-30 Tage) -> Warengutschein (store_credit)",
        user_inputs=[
            "Guten Tag, ich möchte Artikel aus ORD-1002 zurücksenden. Mail: kunde2@example.com",
            "Ja, ich bestätige die Retoure."
        ],
        thread_id=f"thread-test-2-{uuid4().hex[:6]}"
    )
    assert state_2.get("auth_status") is True, "Fall 2: Auth muss erfolgreich sein."
    assert state_2.get("return_booking", {}).get("return_type") == "store_credit", "Fall 2: Return Type muss 'store_credit' sein."
    print("  [TEST-ASSERTION] Fall 2 ERFOLGREICH: Retoure als 'store_credit' gebucht.")

    # FALL 3: Frist abgelaufen (> 30 Tage)
    state_3 = run_scenario(
        title="Fall 3: Frist abgelaufen (> 30 Tage) -> Eskalation (RETURN_DEADLINE_EXCEEDED)",
        user_inputs=[
            "Ich möchte die Bestellung ORD-1003 reklamieren und zurückgeben. Meine E-Mail lautet kunde3@example.com."
        ],
        thread_id=f"thread-test-3-{uuid4().hex[:6]}"
    )
    assert state_3.get("auth_status") is True, "Fall 3: Auth war erfolgreich."
    assert state_3.get("tools_locked") is True, "Fall 3: Tools müssen nach Eskalation gesperrt sein."
    assert state_3.get("handoff_payload") is not None, "Fall 3: Handoff-Payload muss existieren."
    assert state_3["handoff_payload"]["escalation_reason"] == EscalationReason.RETURN_DEADLINE_EXCEEDED.value
    print("  [TEST-ASSERTION] Fall 3 ERFOLGREICH: HandoffPayload mit RETURN_DEADLINE_EXCEEDED generiert und Tools gesperrt.")

    # FALL 4: Auth-Fehlschlag (3 Fehlversuche -> Eskalation beim dritten Mal)
    state_4 = run_scenario(
        title="Fall 4: Auth-Fehlschlag (3 Fehlversuche) -> Eskalation (AUTH_FAILED_MAX_ATTEMPTS)",
        user_inputs=[
            "Hallo, ich will retournieren: ORD-9999 mit falschemail@example.com",
            "Oh Verzeihung, ich meinte ORD-8888 und nochmalkorrupt@example.com",
            "Letzter Versuch: ORD-7777 mit drittversuchfalsch@example.com"
        ],
        thread_id=f"thread-test-4-{uuid4().hex[:6]}"
    )
    assert state_4.get("auth_status") is False, "Fall 4: Auth muss False sein."
    assert state_4.get("auth_attempts") == 3, "Fall 4: Auth-Versuche müssen 3 sein."
    assert state_4.get("tools_locked") is True, "Fall 4: Tools müssen gesperrt sein."
    assert state_4.get("handoff_payload") is not None, "Fall 4: Handoff-Payload muss existieren."
    assert state_4["handoff_payload"]["escalation_reason"] == EscalationReason.AUTH_FAILED_MAX_ATTEMPTS.value
    print("  [TEST-ASSERTION] Fall 4 ERFOLGREICH: HandoffPayload mit AUTH_FAILED_MAX_ATTEMPTS generiert nach 3 Fehlversuchen.")

    print("\n" + "=" * 80)
    print(" ALLE 4 TESTFÄLLE WURDEN ERFOLGREICH DURCHLAUFEN UND BESTÄTIGT!")
    print("=" * 80)


def wait_and_open_browser(host: str, port: int, url: str) -> None:
    """Wartet im Hintergrund, bis der Server aktiv lauscht, bevor der Browser geöffnet wird."""
    start_time = time.time()
    while time.time() - start_time < 8.0:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                time.sleep(0.1)
                webbrowser.open(url)
                return
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def run_server(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True) -> None:
    """Startet den FastAPI Webserver mit dem Frontend."""
    url = f"http://{host}:{port}"
    print("=" * 80)
    print(" START DES RETOUREN-AGENT WEB-FRONTENDS")
    print(f" URL: {url}")
    print(" Drücken Sie STRG+C zum Beenden.")
    print("=" * 80)

    if open_browser:
        threading.Thread(target=wait_and_open_browser, args=(host, port, url), daemon=True).start()

    uvicorn.run("server:app", host=host, port=port, reload=False, log_level="info")


def main():
    parser = argparse.ArgumentParser(description="Kundenservice-Agent für Retourenabwicklung (LangGraph & LangChain)")
    parser.add_argument("--test", action="store_true", help="Führt die 4 automatisierten Testfälle in der Konsole aus")
    parser.add_argument("--host", default="127.0.0.1", help="Host für den Webserver (Standard: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port für den Webserver (Standard: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Browser nicht automatisch öffnen")
    args = parser.parse_args()

    if args.test:
        run_test_suite()
    else:
        run_server(host=args.host, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
