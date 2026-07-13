import asyncio

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from app.auth.principal import get_principal
from app.domain.principals import Principal
from app.schemas.thread import RealtimeTicketResponse
from app.services.realtime import RealtimeEvent, realtime_hub, realtime_tickets

router = APIRouter(tags=["realtime"])
REALTIME_HEARTBEAT_INTERVAL = 20.0


async def next_realtime_message(
    queue: asyncio.Queue[RealtimeEvent],
    *,
    timeout: float = REALTIME_HEARTBEAT_INTERVAL,
) -> dict[str, object]:
    try:
        event = await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"type": "ping"}
    return event.as_dict()


@router.post("/realtime/tickets", response_model=RealtimeTicketResponse)
async def create_realtime_ticket(
    principal: Principal = Depends(get_principal),
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
        await websocket.send_json({"type": "ready", "cursor": after})
        for event in replay:
            await websocket.send_json(event.as_dict())
        while True:
            await websocket.send_json(await next_realtime_message(queue))
    except WebSocketDisconnect:
        pass
    finally:
        realtime_hub.unsubscribe(principal, queue)
