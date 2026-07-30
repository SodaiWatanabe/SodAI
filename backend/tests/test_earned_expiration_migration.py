import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.session import dispose_engine, get_session_factory
from app.domain.credits import CREDIT_ASSET_CODE, ISSUANCE_ACCOUNT_ID
from app.models.account import UserModel
from app.models.credits import (
    CreditAccountModel,
    CreditLotModel,
    CreditPostingModel,
    CreditTransactionModel,
)

MIGRATION_PHASE = os.getenv("SODAI_EARNED_EXPIRATION_MIGRATION_TEST")
SEED_USER_ID = UUID("00000000-0000-4000-8000-000000000110")
SEED_ACCOUNT_ID = UUID("00000000-0000-4000-9000-000000000110")
SEED_TRANSACTION_ID = UUID("00000000-0000-4000-a000-000000000110")
SEED_LOT_ID = UUID("00000000-0000-4000-b000-000000000110")
ISSUED_AT = datetime(2026, 7, 1, 12, 34, 56, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    MIGRATION_PHASE not in {"prepare", "verify"},
    reason="run around the earned expiration migration",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_existing_earned_lot_receives_the_90_day_expiration() -> None:
    try:
        if MIGRATION_PHASE == "prepare":
            await prepare_unbounded_earned_lot()
        else:
            await verify_expiration()
    finally:
        await dispose_engine()


async def prepare_unbounded_earned_lot() -> None:
    async with get_session_factory()() as session:
        session.add(UserModel(id=SEED_USER_ID, display_name="earned-migration-user"))
        await session.flush()
        session.add(
            CreditAccountModel(
                id=SEED_ACCOUNT_ID,
                kind="user",
                owner_user_id=SEED_USER_ID,
                asset_code=CREDIT_ASSET_CODE,
            )
        )
        await session.flush()
        session.add(
            CreditTransactionModel(
                id=SEED_TRANSACTION_ID,
                kind="grant",
                idempotency_key_hash="e" * 64,
                reference_type="user_credit_grant",
                reference_id=SEED_ACCOUNT_ID,
                effective_at=ISSUED_AT,
            )
        )
        await session.flush()
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=SEED_TRANSACTION_ID,
                    account_id=ISSUANCE_ACCOUNT_ID,
                    amount=-5,
                ),
                CreditPostingModel(
                    transaction_id=SEED_TRANSACTION_ID,
                    account_id=SEED_ACCOUNT_ID,
                    amount=5,
                ),
            )
        )
        session.add(
            CreditLotModel(
                id=SEED_LOT_ID,
                owner_account_id=SEED_ACCOUNT_ID,
                issuance_transaction_id=SEED_TRANSACTION_ID,
                source_kind="earned",
                original_amount=5,
                issued_at=ISSUED_AT,
                expires_at=None,
            )
        )
        await session.commit()


async def verify_expiration() -> None:
    async with get_session_factory()() as session:
        lot = await session.scalar(
            select(CreditLotModel).where(CreditLotModel.id == SEED_LOT_ID)
        )

        assert lot is not None
        assert lot.expires_at == ISSUED_AT + timedelta(days=90)
