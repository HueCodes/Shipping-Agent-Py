"""Chat and WebSocket streaming endpoints."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_optional_customer
from src.api.errors import create_error_response, ErrorCode
from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatHistoryResponse,
)
from src.db.database import get_db_session
from src.db.repository import ConversationRepository, CustomerRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

# Store agent instances per customer (in-memory cache)
agents: dict[str, "ShippingAgent"] = {}


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    customer=Depends(get_optional_customer),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Send a message to the shipping agent."""
    from src.agent import ShippingAgent
    from src.agent.context import CustomerContext

    if not request.message.strip():
        raise create_error_response(
            status_code=400,
            error="Message cannot be empty",
            code=ErrorCode.VALIDATION_ERROR,
            endpoint="/api/chat",
        )

    customer_id_str = str(customer.id) if customer else None

    try:
        cache_key = str(customer.id) if customer else request.session_id

        if cache_key not in agents:
            if customer:
                context = CustomerContext.from_customer(customer)
                agents[cache_key] = ShippingAgent(context=context, db=db)
            else:
                agents[cache_key] = ShippingAgent()

        agent = agents[cache_key]
        response = agent.chat(request.message)
        return ChatResponse(response=response, session_id=cache_key)
    except TimeoutError as e:
        raise create_error_response(
            status_code=504,
            error="The AI assistant is taking too long to respond. Please try again.",
            code=ErrorCode.CLAUDE_TIMEOUT,
            customer_id=customer_id_str,
            endpoint="/api/chat",
            exc=e,
        )
    except Exception as e:
        error_str = str(e).lower()
        if "anthropic" in error_str or "claude" in error_str or "api" in error_str:
            raise create_error_response(
                status_code=502,
                error="Unable to connect to the AI assistant. Please try again later.",
                code=ErrorCode.CLAUDE_API_ERROR,
                customer_id=customer_id_str,
                endpoint="/api/chat",
                exc=e,
            )
        raise create_error_response(
            status_code=500,
            error="An error occurred while processing your message. Please try again.",
            code=ErrorCode.INTERNAL_ERROR,
            customer_id=customer_id_str,
            endpoint="/api/chat",
            exc=e,
        )


@router.post("/reset")
async def reset(
    session_id: str = "default",
    customer=Depends(get_optional_customer),
) -> dict:
    """Reset conversation history for a session."""
    cache_key = str(customer.id) if customer else session_id
    if cache_key in agents:
        agents[cache_key].reset()
    return {"status": "ok", "session_id": cache_key}


@router.get("/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str = "default",
    limit: int = 50,
    customer=Depends(get_optional_customer),
    db: Session = Depends(get_db),
) -> ChatHistoryResponse:
    """Get conversation history for a session."""
    cache_key = str(customer.id) if customer else session_id

    if cache_key in agents:
        agent = agents[cache_key]
        messages = agent.messages[-limit:] if limit else agent.messages
    else:
        if customer:
            conversation_repo = ConversationRepository(db)
            conversation = conversation_repo.get_or_create(customer.id)
            messages = conversation_repo.get_messages(conversation.id, limit=limit)
        else:
            messages = []

    chat_messages = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        text_parts.append(f"[Tool result: {block.get('content', '')}]")
            content = "\n".join(text_parts)

        chat_messages.append(ChatMessage(
            role=msg.get("role", "unknown"),
            content=content,
            timestamp=msg.get("timestamp"),
        ))

    return ChatHistoryResponse(
        session_id=cache_key,
        messages=chat_messages,
        total=len(chat_messages),
    )


@router.websocket("/chat/stream")
async def chat_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming chat responses."""
    from src.agent import ShippingAgent
    from src.agent.context import CustomerContext

    await websocket.accept()

    session_id = None
    customer = None

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            user_message = message_data.get("message", "")
            session_id = message_data.get("session_id", "default")
            customer_id = message_data.get("customer_id")

            if not user_message.strip():
                await websocket.send_json({
                    "type": "error",
                    "message": "Message cannot be empty",
                })
                continue

            with get_db_session() as db:
                cache_key = customer_id or session_id

                if customer_id:
                    try:
                        cid = UUID(customer_id)
                        customer_repo = CustomerRepository(db)
                        customer = customer_repo.get_by_id(cid)
                    except (ValueError, Exception):
                        customer = None

                if cache_key not in agents:
                    if customer:
                        context = CustomerContext.from_customer(customer)
                        agents[cache_key] = ShippingAgent(context=context, db=db)
                    else:
                        agents[cache_key] = ShippingAgent()

                agent = agents[cache_key]

                await websocket.send_json({
                    "type": "status",
                    "status": "thinking",
                    "message": "Processing your request...",
                })

                if agent.mock_mode:
                    await asyncio.sleep(0.3)

                    lower_msg = user_message.lower()
                    if any(term in lower_msg for term in ["rate", "ship", "track", "valid"]):
                        tool_name = "get_shipping_rates"
                        if "valid" in lower_msg:
                            tool_name = "validate_address"
                        elif "ship" in lower_msg:
                            tool_name = "create_shipment"
                        elif "track" in lower_msg:
                            tool_name = "get_tracking_status"

                        await websocket.send_json({
                            "type": "tool_start",
                            "tool": tool_name,
                            "message": f"Executing {tool_name}...",
                        })
                        await asyncio.sleep(0.2)
                        await websocket.send_json({
                            "type": "tool_complete",
                            "tool": tool_name,
                            "message": f"{tool_name} completed",
                        })

                    response = agent.chat(user_message)

                    await websocket.send_json({
                        "type": "status",
                        "status": "responding",
                        "message": "Generating response...",
                    })

                    chunk_size = 20
                    for i in range(0, len(response), chunk_size):
                        chunk = response[i:i + chunk_size]
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                        })
                        await asyncio.sleep(0.02)

                    await websocket.send_json({
                        "type": "complete",
                        "session_id": cache_key,
                    })
                else:
                    await websocket.send_json({
                        "type": "status",
                        "status": "responding",
                        "message": "Generating response...",
                    })

                    async for event in agent.chat_stream(user_message):
                        event_type = event.get("type")

                        if event_type == "text":
                            await websocket.send_json({
                                "type": "chunk",
                                "content": event.get("content", ""),
                            })
                        elif event_type == "tool_start":
                            await websocket.send_json({
                                "type": "tool_start",
                                "tool": event.get("tool", ""),
                                "message": f"Executing {event.get('tool', '')}...",
                            })
                        elif event_type == "tool_complete":
                            await websocket.send_json({
                                "type": "tool_complete",
                                "tool": event.get("tool", ""),
                                "message": f"{event.get('tool', '')} completed",
                            })
                        elif event_type == "error":
                            await websocket.send_json({
                                "type": "error",
                                "message": event.get("content", "Unknown error"),
                            })
                        elif event_type == "complete":
                            await websocket.send_json({
                                "type": "complete",
                                "session_id": cache_key,
                            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session: %s", session_id)
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "code": ErrorCode.VALIDATION_ERROR,
            "message": "Invalid JSON format",
        })
    except Exception as e:
        logger.exception("WebSocket error for session %s: %s", session_id, e)
        try:
            await websocket.send_json({
                "type": "error",
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "An error occurred while processing your request. Please try again.",
            })
        except Exception:
            pass
