from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_authenticated_identity
from app.domain.accounts import Account, ExternalIdentity
from app.schemas.account import AccountProfileUpdate, AccountResponse
from app.services.account import AccountService, InactiveAccountError, get_account_service

router = APIRouter(prefix="/account", tags=["account"])


async def get_current_account(
    identity: ExternalIdentity = Depends(get_authenticated_identity),
    service: AccountService = Depends(get_account_service),
) -> Account:
    return await service.resolve_authenticated_account(identity)


@router.get("/me", response_model=AccountResponse)
async def read_current_account(
    account: Account = Depends(get_current_account),
) -> AccountResponse:
    return AccountResponse.model_validate(account)


@router.patch("/me", response_model=AccountResponse)
async def update_current_account(
    profile: AccountProfileUpdate,
    identity: ExternalIdentity = Depends(get_authenticated_identity),
    service: AccountService = Depends(get_account_service),
) -> AccountResponse:
    try:
        account = await service.set_display_name(identity, profile.display_name)
    except InactiveAccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        ) from exc
    return AccountResponse.model_validate(account)
