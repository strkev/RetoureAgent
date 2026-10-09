"""
routes/chat.py
Endpunkte für synchrone und gestreamte Chat-Interaktionen mit dem LangGraph-Agenten.
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from api_schemas import ChatRequest
from payload_helpers import build_chat_response_payload
from session_manager import sessions

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """Synchroner Chat-Endpunkt: Führt den Graph-Turn aus und gibt den aktualisierten State zurück."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Nachricht darf nicht leer sein.")

    session_id, graph_app, _ = sessions.get_or_create(
        session_id=req.session_id,
        api_key=req.api_key,
        api_url=req.api_url,
        model=req.model
    )
    config = {"configurable": {"thread_id": session_id}}

    input_data = {"messages": [HumanMessage(content=req.message.strip())]}
    state_result = graph_app.invoke(input_data, config=config)

    return build_chat_response_payload(session_id, state_result)


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """Server-Sent-Events (SSE) Streaming-Endpunkt mit nativem LangGraph astream."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Nachricht darf nicht leer sein.")

    session_id, graph_app, _ = sessions.get_or_create(
        session_id=req.session_id,
        api_key=req.api_key,
        api_url=req.api_url,
        model=req.model
    )
    config = {"configurable": {"thread_id": session_id}}
    input_data = {"messages": [HumanMessage(content=req.message.strip())]}

    async def stream_generator():
        async for msg, meta in graph_app.astream(input_data, config=config, stream_mode="messages"):
            tags = meta.get("tags") or []
            if "internal_task" in tags:
                continue

            if isinstance(msg, AIMessageChunk) and msg.content:
                yield f"data: {json.dumps({'type': 'token', 'token': msg.content}, ensure_ascii=False)}\n\n"
            # Vollständige Nachricht bei synchronen / deterministischen Knoten oder Mock-LLM
            elif isinstance(msg, AIMessage) and not isinstance(msg, AIMessageChunk) and msg.content:
                yield f"data: {json.dumps({'type': 'token', 'token': msg.content}, ensure_ascii=False)}\n\n"

        state_snapshot = graph_app.get_state(config)
        final_state = state_snapshot.values if state_snapshot else {}
        payload = build_chat_response_payload(session_id, final_state)

        # Finales Event mit vollständigem State-Payload für Action Cards & State Inspector
        yield f"data: {json.dumps({'type': 'done', 'payload': payload}, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
