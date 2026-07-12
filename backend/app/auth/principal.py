from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import authentication_required, bearer_scheme, get_token_verifier
from app.auth.verifier import TokenVerificationError, TokenVerifier
from app.domain.accounts import AccountStatus
from app.domain.conversations import ConversationPrincipal, PrincipalKind
from app.services.account import AccountService, get_account_service
from app.services.guest_sessions import GUEST_COOKIE_NAME, guest_session_service


async def get_conversation_principal(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    verifier: TokenVerifier = Depends(get_token_verifier),
    account_service: AccountService = Depends(get_account_service),
) -> ConversationPrincipal:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        try:
            identity = await verifier.verify(credentials.credentials)
        except TokenVerificationError:
            # An explicitly supplied invalid credential must never fall back to a guest.
            raise authentication_required()
        account = await account_service.resolve_authenticated_account(identity)
        if account.status is not AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
            )
        return ConversationPrincipal(PrincipalKind.USER, account.id)

    return await guest_session_service.resolve(request.cookies.get(GUEST_COOKIE_NAME), response)
