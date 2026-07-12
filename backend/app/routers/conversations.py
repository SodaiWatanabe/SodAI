import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.auth.principal import get_conversation_principal
from app.domain.conversations import ConversationPrincipal
from app.repositories.conversations import ConversationBusyError, ConversationNotFoundError
from app.schemas.conversation import (
    ConversationCreationResponse,
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    CreateTurnRequest,
    ModelListResponse,
    RealtimeTicketResponse,
)
from app.services.conversation import (
    ConversationService,
    ModelAccessError,
    get_conversation_service,
)
from app.services.realtime import realtime_hub, realtime_tickets

router = APIRouter(tags=["conversations"])


@router.post(
    "/conversations",
    response_model=ConversationCreationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: CreateConversationRequest,
    principal: ConversationPrincipal = Depends(get_conversation_principal),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationCreationResponse:
    try:
        creation = await service.create(principal, payload.input, payload.model)
    except ModelAccessError as exc:
        raise HTTPException(status_code=403, detail="Model is not available") from exc
    return ConversationCreationResponse.model_validate(creation, from_attributes=True)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    principal: ConversationPrincipal = Depends(get_conversation_principal),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationListResponse:
    items = await service.list(principal)
    return ConversationListResponse.model_validate({"items": items}, from_attributes=True)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def read_conversation(
    conversation_id: UUID,
    principal: ConversationPrincipal = Depends(get_conversation_principal),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationResponse:
    try:
        conversation = await service.get(principal, conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    return ConversationResponse.model_validate(conversation, from_attributes=True)


@router.post(
    "/conversations/{conversation_id}/turns",
    response_model=ConversationCreationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_turn(
    conversation_id: UUID,
    payload: CreateTurnRequest,
    principal: ConversationPrincipal = Depends(get_conversation_principal),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationCreationResponse:
    try:
        creation = await service.add_turn(principal, conversation_id, payload.input, payload.model)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    except ConversationBusyError as exc:
        raise HTTPException(
            status_code=409, detail="A response is already being generated"
        ) from exc
    except ModelAccessError as exc:
        raise HTTPException(status_code=403, detail="Model is not available") from exc
    return ConversationCreationResponse.model_validate(creation, from_attributes=True)


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    principal: ConversationPrincipal = Depends(get_conversation_principal),
    service: ConversationService = Depends(get_conversation_service),
) -> ModelListResponse:
    return ModelListResponse(items=service.available_models(principal))


@router.post("/realtime/tickets", response_model=RealtimeTicketResponse)
async def create_realtime_ticket(
    principal: ConversationPrincipal = Depends(get_conversation_principal),
) -> RealtimeTicketResponse:
    return RealtimeTicketResponse(
        ticket=realtime_tickets.issue(principal), cursor=realtime_hub.cursor
    )


@router.websocket("/realtime")
async def realtime(
    websocket: WebSocket,
    ticket: str = Query(),
    after: int = Query(default=0, ge=0),
) -> None:
    principal = realtime_tickets.consume(ticket)
    if principal is None:
        await websocket.close(code=4401, reason="Invalid or expired ticket")
        return
    await websocket.accept()
    queue, replay = realtime_hub.subscribe(principal, after)
    try:
        # A client may disconnect halfway through replay. Acknowledging only the
        # requested cursor keeps the remaining replay eligible on reconnect.
        await websocket.send_json({"type": "ready", "cursor": after})
        for event in replay:
            await websocket.send_json(event.as_dict())
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=20)
                await websocket.send_json(event.as_dict())
            except TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    finally:
        realtime_hub.unsubscribe(principal, queue)
