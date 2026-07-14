from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.domain.accounts import Account, AccountStatus
from app.routers.account import get_current_account
from app.schemas.credits import CreditBalanceResponse, CreditTransactionListResponse
from app.services.credits import CreditService, get_credit_service

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("", response_model=CreditBalanceResponse)
async def read_credit_balance(
    response: Response,
    account: Account = Depends(get_current_account),
    service: CreditService = Depends(get_credit_service),
) -> CreditBalanceResponse:
    if account.status is not AccountStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    response.headers["Cache-Control"] = "private, no-store"
    return CreditBalanceResponse.model_validate(await service.balance(account.id))


@router.get("/transactions", response_model=CreditTransactionListResponse)
async def list_credit_transactions(
    response: Response,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    account: Account = Depends(get_current_account),
    service: CreditService = Depends(get_credit_service),
) -> CreditTransactionListResponse:
    if account.status is not AccountStatus.ACTIVE:
        raise HTTPException(status_code=403, detail="Account is not active")
    response.headers["Cache-Control"] = "private, no-store"
    try:
        page = await service.transactions(account.id, limit=limit, cursor=cursor)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return CreditTransactionListResponse(
        items=list(page.items),
        next_cursor=page.next_cursor,
    )
