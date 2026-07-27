from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.auth.principal import get_principal
from app.domain.credits import InsufficientCreditsError
from app.domain.principals import Principal
from app.repositories.threads import (
    ExecutionNotFoundError,
    ResponseNotRetryableError,
    ResponseRequestNotFoundError,
    ThreadBusyError,
    ThreadNotFoundError,
)
from app.schemas.thread import (
    AnswererListResponse,
    CreateResponseRequest,
    CreateThreadRequest,
    ExecutionResponse,
    ResponseCreationResponse,
    SpaceListResponse,
    ThreadListResponse,
    ThreadResponse,
    ThreadSearchRequest,
    ThreadSearchResponse,
    ThreadSummaryResponse,
    UpdateThreadRequest,
)
from app.services.thread import (
    AnswererAccessError,
    AnswererUnavailableError,
    GenerationCapacityError,
    ThreadService,
    get_thread_service,
)

router = APIRouter(tags=["collaboration"])


@router.get("/spaces", response_model=SpaceListResponse)
async def list_spaces(
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> SpaceListResponse:
    return SpaceListResponse(items=await service.list_spaces(principal))


@router.post(
    "/threads",
    response_model=ResponseCreationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_thread(
    payload: CreateThreadRequest,
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ResponseCreationResponse:
    try:
        creation = await service.create(principal, payload.input, payload.answerer)
    except AnswererAccessError as exc:
        raise HTTPException(status_code=403, detail="Answerer is not available") from exc
    except AnswererUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Answerer is temporarily unavailable") from exc
    except GenerationCapacityError as exc:
        raise HTTPException(status_code=429, detail="Generation capacity is exhausted") from exc
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail="Insufficient credits") from exc
    return ResponseCreationResponse.model_validate(creation, from_attributes=True)


@router.post(
    "/response-requests/{response_request_id}/executions",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_response_execution(
    response_request_id: UUID,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128),
    ],
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ExecutionResponse:
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        raise HTTPException(status_code=422, detail="Idempotency-Key cannot be blank")
    try:
        execution = await service.retry(principal, response_request_id, normalized_key)
    except ResponseRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Response request not found") from exc
    except ResponseNotRetryableError as exc:
        raise HTTPException(status_code=409, detail="Response request cannot be retried") from exc
    except AnswererUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Answerer is temporarily unavailable") from exc
    except GenerationCapacityError as exc:
        raise HTTPException(status_code=429, detail="Generation capacity is exhausted") from exc
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail="Insufficient credits") from exc
    return ExecutionResponse.model_validate(execution, from_attributes=True)


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ThreadResponse,
)
async def cancel_execution(
    execution_id: UUID,
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    try:
        thread = await service.cancel(principal, execution_id)
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Execution not found") from exc
    return ThreadResponse.model_validate(thread, from_attributes=True)


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadListResponse:
    return ThreadListResponse(items=await service.list(principal))


@router.post("/thread-searches", response_model=ThreadSearchResponse)
async def search_threads(
    payload: ThreadSearchRequest,
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadSearchResponse:
    page = await service.search(
        principal,
        payload.query,
        limit=payload.limit,
    )
    return ThreadSearchResponse.model_validate(page, from_attributes=True)


@router.get("/threads/{thread_id}", response_model=ThreadResponse)
async def read_thread(
    thread_id: UUID,
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadResponse:
    try:
        thread = await service.get(principal, thread_id)
    except ThreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc
    return ThreadResponse.model_validate(thread, from_attributes=True)


@router.patch("/threads/{thread_id}", response_model=ThreadSummaryResponse)
async def update_thread(
    thread_id: UUID,
    payload: UpdateThreadRequest,
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadSummaryResponse:
    try:
        thread = await service.update_title(principal, thread_id, payload.title)
    except ThreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Thread title cannot be blank") from exc
    return ThreadSummaryResponse.model_validate(thread, from_attributes=True)


@router.post("/threads/{thread_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_thread(
    thread_id: UUID,
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> None:
    try:
        await service.archive(principal, thread_id)
    except ThreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc


@router.post(
    "/response-requests",
    response_model=ResponseCreationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_response_request(
    payload: CreateResponseRequest,
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> ResponseCreationResponse:
    try:
        creation = await service.append(
            principal, payload.thread_id, payload.input, payload.answerer
        )
    except ThreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Thread not found") from exc
    except ThreadBusyError as exc:
        raise HTTPException(
            status_code=409, detail="A response is already being generated"
        ) from exc
    except AnswererAccessError as exc:
        raise HTTPException(status_code=403, detail="Answerer is not available") from exc
    except AnswererUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Answerer is temporarily unavailable") from exc
    except GenerationCapacityError as exc:
        raise HTTPException(status_code=429, detail="Generation capacity is exhausted") from exc
    except InsufficientCreditsError as exc:
        raise HTTPException(status_code=402, detail="Insufficient credits") from exc
    return ResponseCreationResponse.model_validate(creation, from_attributes=True)


@router.get("/answerers", response_model=AnswererListResponse)
async def list_answerers(
    principal: Principal = Depends(get_principal),
    service: ThreadService = Depends(get_thread_service),
) -> AnswererListResponse:
    return AnswererListResponse(items=service.available_answerers(principal))
