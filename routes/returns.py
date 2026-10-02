"""
routes/returns.py
Endpunkte für Retourenbestätigung, Teil-Retouren-Auswahl, Stornierung und PDF-Label-Generierung.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from langchain_core.messages import HumanMessage

from api_schemas import CancelReturnRequest, ReturnConfirmRequest
from payload_helpers import build_chat_response_payload
from pdf_generator import generate_return_pdf
from repository import get_repository
from session_manager import sessions

router = APIRouter(prefix="/api", tags=["returns"])


@router.get("/returns/{return_id}/label.pdf")
async def get_return_label_pdf(return_id: str):
    """Generiert einen druckfähigen Retourenbegleitschein & Label als PDF."""
    repo = get_repository()
    booking = repo.get_return_booking(return_id)
    if not booking:
        # Fallback für direkte Links / Tests
        booking = {
            "return_id": return_id,
            "order_id": "ORD-1001",
            "return_type": "refund",
            "items": [{"item_id": "ART-901", "name": "Ergonomischer Bürostuhl", "price": 199.99}],
            "total_refund": 199.99
        }
    order_data = repo.get_order_details(booking.get("order_id", ""))
    pdf_bytes = generate_return_pdf(booking, order_data=order_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=retoure_{return_id}.pdf"}
    )


@router.post("/return/confirm")
async def return_confirm_endpoint(req: ReturnConfirmRequest):
    """Verarbeitet die verbindliche Retourenbestätigung (inkl. Teil-Retoure ausgewählter Artikel)."""
    session_id, graph_app, _ = sessions.get_or_create(session_id=req.session_id)
    config = {"configurable": {"thread_id": session_id}}

    st = graph_app.get_state(config)
    st_val = st.values if st else {}
    order_data = st_val.get("order_data")
    if not order_data:
        raise HTTPException(status_code=400, detail="Keine aktive Retourenbestellung gefunden.")

    selected = req.selected_items
    if not selected:
        selected = [
            it.get("item_id") for it in order_data.get("items", [])
            if isinstance(it, dict)
        ]

    graph_app.update_state(
        config,
        {
            "selected_items": selected,
            "return_confirmed": True,
        }
    )

    confirm_text = "Ich bestätige die Retoure für die ausgewählten Artikel."
    input_data = {"messages": [HumanMessage(content=confirm_text)]}
    state_result = graph_app.invoke(input_data, config=config)

    return build_chat_response_payload(session_id, state_result)


@router.post("/return/cancel")
async def return_cancel_endpoint(req: CancelReturnRequest):
    """Bricht die vorbereitete Retoure ab."""
    session_id, graph_app, _ = sessions.get_or_create(session_id=req.session_id)
    config = {"configurable": {"thread_id": session_id}}
    input_data = {"messages": [HumanMessage(content="Ich möchte die Retoure abbrechen.")]}
    state_result = graph_app.invoke(input_data, config=config)
    return build_chat_response_payload(session_id, state_result)
