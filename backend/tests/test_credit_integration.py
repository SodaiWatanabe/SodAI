import asyncio
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sodai_contracts.inference import FinishReason, GenerationEvent, GenerationEventType
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import dispose_engine, get_session_factory
from app.domain.answerers import AnswererId, get_answerer
from app.domain.credits import (
    CREDIT_ASSET_CODE,
    CREDIT_SCALE,
    ISSUANCE_ACCOUNT_ID,
    RESERVE_ACCOUNT_ID,
    REVENUE_ACCOUNT_ID,
    CreditBalance,
    CreditIdempotencyConflictError,
    CreditReservationStatus,
    CreditSourceKind,
    InferenceTariff,
    InsufficientCreditsError,
)
from app.domain.principals import Principal, PrincipalKind
from app.models.account import UserModel
from app.models.credits import (
    CreditAccountModel,
    CreditLotConsumptionModel,
    CreditLotModel,
    CreditPostingModel,
    CreditReservationAllocationModel,
    CreditTransactionModel,
    InferenceBillingIntentModel,
    InferenceCreditReservationModel,
    InferenceUsageRecordModel,
)
from app.models.platform import ExecutionModel, SpaceModel
from app.repositories.credits import CreditLedgerRepository
from app.repositories.threads import SqlAlchemyThreadRepository
from app.services.credits import CreditService
from app.services.inference.billing import InferenceBillingService
from app.services.inference.deployment import ModelDeploymentRegistry
from app.services.thread import ThreadService

pytestmark = pytest.mark.skipif(
    os.getenv("SODAI_INTEGRATION_TESTS") != "1",
    reason="set SODAI_INTEGRATION_TESTS=1 to run PostgreSQL integration tests",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def isolated_database_engine():
    yield
    await dispose_engine()


async def create_user() -> Principal:
    principal = Principal(PrincipalKind.USER, uuid4())
    async with get_session_factory()() as session:
        session.add(UserModel(id=principal.id, display_name="Credit integration"))
        await session.commit()
    return principal


async def create_execution(principal: Principal, content: str):
    factory = get_session_factory()
    async with factory() as session:
        repository = SqlAlchemyThreadRepository(session)
        context = await repository.ensure_personal_context(principal)
        creation = await repository.create_thread_response(
            principal,
            context,
            content,
            get_answerer(AnswererId.ASUKA_1),
            execution_target="pseudo:asuka-1",
            artifact_id="pseudo-v1",
            deadline_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        await session.commit()
        return creation


def add_paid_billing_intent(
    session: AsyncSession,
    principal: Principal,
    execution_id: UUID,
    maximum_charge: int,
    *,
    fixed_charge: int = 0,
) -> None:
    session.add(
        InferenceBillingIntentModel(
            execution_reference_id=execution_id,
            user_id=principal.id,
            asset_code=CREDIT_ASSET_CODE,
            tariff_revision=f"integration-ledger-{maximum_charge}-v1",
            fixed_charge=fixed_charge,
            input_token_rate=0,
            output_token_rate=0,
            maximum_charge=maximum_charge,
            unmetered_charge=maximum_charge,
        )
    )


@pytest.mark.anyio
async def test_credit_grant_is_balanced_idempotent_and_immutable() -> None:
    principal = await create_user()
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        grant = await repository.grant(
            principal.id,
            5 * CREDIT_SCALE,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="integration-grant",
        )
        await session.commit()
    async with factory() as session:
        replay = await CreditLedgerRepository(session).grant(
            principal.id,
            5 * CREDIT_SCALE,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="integration-grant",
        )
        await session.commit()
        assert replay.transaction_id == grant.transaction_id
        assert replay.lot_id == grant.lot_id
        assert replay.replayed

    async with factory() as session:
        repository = CreditLedgerRepository(session)
        assert await repository.balance(principal.id) == CreditBalance(
            CREDIT_ASSET_CODE,
            CREDIT_SCALE,
            5 * CREDIT_SCALE,
            0,
        )
        page = await repository.transaction_page(principal.id, limit=10)
        assert len(page.items) == 1
        assert page.items[0].available_delta == 5 * CREDIT_SCALE
        assert page.items[0].source_kind is CreditSourceKind.ADMIN

        posting = await session.scalar(
            select(CreditPostingModel).where(
                CreditPostingModel.transaction_id == grant.transaction_id,
                CreditPostingModel.amount > 0,
            )
        )
        assert posting is not None
        with pytest.raises(DBAPIError, match="credit ledger records are immutable"):
            await session.execute(
                update(CreditPostingModel)
                .where(CreditPostingModel.id == posting.id)
                .values(amount=1)
            )


@pytest.mark.anyio
async def test_concurrent_identical_grants_converge_to_one_transaction() -> None:
    principal = await create_user()
    factory = get_session_factory()

    async def grant_once():
        async with factory() as session:
            grant = await CreditLedgerRepository(session).grant(
                principal.id,
                40,
                source_kind=CreditSourceKind.ADMIN,
                idempotency_key="concurrent-grant",
            )
            await session.commit()
            return grant

    first, second = await asyncio.wait_for(
        asyncio.gather(grant_once(), grant_once()),
        timeout=5,
    )
    assert first.transaction_id == second.transaction_id
    assert first.lot_id == second.lot_id
    assert {first.replayed, second.replayed} == {False, True}
    async with factory() as session:
        assert (await CreditLedgerRepository(session).balance(principal.id)).available == 40


@pytest.mark.anyio
async def test_concurrent_cross_user_idempotency_conflict_is_a_domain_error() -> None:
    first_user = await create_user()
    second_user = await create_user()
    factory = get_session_factory()

    async def grant_once(principal: Principal) -> str:
        async with factory() as session:
            try:
                await CreditLedgerRepository(session).grant(
                    principal.id,
                    40,
                    source_kind=CreditSourceKind.ADMIN,
                    idempotency_key="cross-user-grant",
                )
                await session.commit()
                return "granted"
            except CreditIdempotencyConflictError:
                await session.rollback()
                return "conflict"

    results = await asyncio.wait_for(
        asyncio.gather(grant_once(first_user), grant_once(second_user)),
        timeout=5,
    )
    assert sorted(results) == ["conflict", "granted"]


@pytest.mark.anyio
async def test_database_rejects_an_unbalanced_credit_transaction() -> None:
    factory = get_session_factory()
    async with factory() as session:
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="grant",
                idempotency_key_hash="f" * 64,
                reference_type="integration_test",
            )
        )
        session.add(
            CreditPostingModel(
                transaction_id=transaction_id,
                account_id=ISSUANCE_ACCOUNT_ID,
                amount=-1,
            )
        )
        with pytest.raises(DBAPIError, match="is not balanced"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_a_grant_that_does_not_match_its_lot() -> None:
    principal = await create_user()
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            1,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="wallet-bootstrap",
        )
        await session.commit()

    async with factory() as session:
        account = await session.scalar(
            select(CreditAccountModel).where(
                CreditAccountModel.owner_user_id == principal.id
            )
        )
        assert account is not None
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="grant",
                idempotency_key_hash="a" * 64,
                reference_type="user_credit_grant",
                reference_id=account.id,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=ISSUANCE_ACCOUNT_ID,
                    amount=-100,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=account.id,
                    amount=100,
                ),
            )
        )
        await session.flush()
        session.add(
            CreditLotModel(
                owner_account_id=account.id,
                issuance_transaction_id=transaction_id,
                source_kind=CreditSourceKind.ADMIN.value,
                original_amount=50,
                issued_at=datetime.now(timezone.utc),
            )
        )
        with pytest.raises(DBAPIError, match="does not match its lot"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_a_grant_lot_owned_by_a_system_account() -> None:
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="grant",
                idempotency_key_hash="i" * 64,
                reference_type="user_credit_grant",
                reference_id=RESERVE_ACCOUNT_ID,
                effective_at=now,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=ISSUANCE_ACCOUNT_ID,
                    amount=-5,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=5,
                ),
            )
        )
        await session.flush()
        session.add(
            CreditLotModel(
                owner_account_id=RESERVE_ACCOUNT_ID,
                issuance_transaction_id=transaction_id,
                source_kind=CreditSourceKind.ADMIN.value,
                original_amount=5,
                issued_at=now,
            )
        )
        with pytest.raises(DBAPIError, match="does not match its lot"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_a_lot_created_from_a_non_grant_transaction() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "lot transaction kind")
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="lot-kind-funds",
        )
        add_paid_billing_intent(
            session,
            principal,
            creation.response.execution.id,
            5,
        )
        reservation = await repository.reserve_inference(
            principal.id,
            creation.response.execution.id,
            5,
        )
        assert reservation is not None
        await session.commit()

    async with factory() as session:
        reservation = await session.get(InferenceCreditReservationModel, reservation.id)
        assert reservation is not None
        session.add(
            CreditLotModel(
                owner_account_id=reservation.owner_account_id,
                issuance_transaction_id=reservation.reserve_transaction_id,
                source_kind=CreditSourceKind.ADMIN.value,
                original_amount=1,
                issued_at=reservation.created_at,
            )
        )
        with pytest.raises(DBAPIError, match="require a grant transaction"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_lot_consumption_attached_to_a_grant() -> None:
    principal = await create_user()
    factory = get_session_factory()
    async with factory() as session:
        grant = await CreditLedgerRepository(session).grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="consumption-parent",
        )
        await session.commit()

    async with factory() as session:
        session.add(
            CreditLotConsumptionModel(
                lot_id=grant.lot_id,
                transaction_id=grant.transaction_id,
                kind="settle",
                amount=1,
            )
        )
        with pytest.raises(DBAPIError, match="require an expiration or settlement"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_an_orphan_reserve_transaction() -> None:
    principal = await create_user()
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="orphan-reserve-funds",
        )
        await session.commit()

    async with factory() as session:
        account = await session.scalar(
            select(CreditAccountModel).where(
                CreditAccountModel.owner_user_id == principal.id
            )
        )
        assert account is not None
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="reserve",
                idempotency_key_hash="d" * 64,
                reference_type="inference_execution",
                reference_id=uuid4(),
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=account.id,
                    amount=-1,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=1,
                ),
            )
        )
        with pytest.raises(DBAPIError, match="allocations do not match"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_an_orphan_settlement_transaction() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "orphan settlement")
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="orphan-settlement-funds",
        )
        add_paid_billing_intent(
            session,
            principal,
            creation.response.execution.id,
            5,
        )
        await repository.reserve_inference(
            principal.id,
            creation.response.execution.id,
            5,
        )
        await session.commit()

    async with factory() as session:
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="settle",
                idempotency_key_hash="e" * 64,
                reference_type="inference_execution",
                reference_id=creation.response.execution.id,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=-1,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=REVENUE_ACCOUNT_ID,
                    amount=1,
                ),
            )
        )
        with pytest.raises(DBAPIError, match="finalization is inconsistent"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_billing_reserved_from_another_user_wallet() -> None:
    billed_user = await create_user()
    wallet_user = await create_user()
    creation = await create_execution(billed_user, "billing owner")
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            wallet_user.id,
            10,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="wrong-billing-owner-funds",
        )
        add_paid_billing_intent(
            session,
            billed_user,
            creation.response.execution.id,
            5,
        )
        await repository.reserve_inference(
            wallet_user.id,
            creation.response.execution.id,
            5,
        )
        with pytest.raises(DBAPIError, match="billing registration .* is inconsistent"):
            await session.commit()


@pytest.mark.anyio
async def test_concurrent_reservations_cannot_overdraw_one_wallet() -> None:
    principal = await create_user()
    first = await create_execution(principal, "first")
    second = await create_execution(principal, "second")
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            100,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="concurrent-funds",
        )
        await session.commit()

    async def reserve(execution_id: UUID) -> str:
        async with factory() as session:
            try:
                add_paid_billing_intent(session, principal, execution_id, 80)
                await CreditLedgerRepository(session).reserve_inference(
                    principal.id,
                    execution_id,
                    80,
                )
                await session.commit()
                return "reserved"
            except InsufficientCreditsError:
                await session.rollback()
                return "insufficient"

    results = await asyncio.wait_for(
        asyncio.gather(
            reserve(first.response.execution.id),
            reserve(second.response.execution.id),
        ),
        timeout=5,
    )
    assert sorted(results) == ["insufficient", "reserved"]
    async with factory() as session:
        balance = await CreditLedgerRepository(session).balance(principal.id)
        assert balance.available == 20
        assert balance.reserved == 80


@pytest.mark.anyio
async def test_effective_time_follows_wallet_lock_serialization() -> None:
    principal = await create_user()
    slow_execution = await create_execution(principal, "serialized second")
    fast_execution = await create_execution(principal, "serialized first")
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        expiring = await repository.grant(
            principal.id,
            50,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="serialized-expiring",
            expires_at=now + timedelta(hours=1),
            now=now,
        )
        stable = await repository.grant(
            principal.id,
            50,
            source_kind=CreditSourceKind.PURCHASED,
            idempotency_key="serialized-stable",
            now=now,
        )
        await session.commit()

    slow_reached_lock = asyncio.Event()
    release_slow = asyncio.Event()

    async def reserve_slow() -> UUID:
        async with factory() as session:
            repository = CreditLedgerRepository(session)
            original_lock = repository._locked_user_account

            async def delayed_lock(user_id: UUID):
                slow_reached_lock.set()
                await release_slow.wait()
                return await original_lock(user_id)

            repository._locked_user_account = delayed_lock
            add_paid_billing_intent(
                session,
                principal,
                slow_execution.response.execution.id,
                50,
            )
            reservation = await repository.reserve_inference(
                principal.id,
                slow_execution.response.execution.id,
                50,
            )
            assert reservation is not None
            await session.commit()
            return reservation.id

    async def reserve_fast() -> UUID:
        await slow_reached_lock.wait()
        try:
            async with factory() as session:
                repository = CreditLedgerRepository(session)
                add_paid_billing_intent(
                    session,
                    principal,
                    fast_execution.response.execution.id,
                    50,
                )
                reservation = await repository.reserve_inference(
                    principal.id,
                    fast_execution.response.execution.id,
                    50,
                )
                assert reservation is not None
                await session.commit()
                return reservation.id
        finally:
            release_slow.set()

    slow_reservation_id, fast_reservation_id = await asyncio.wait_for(
        asyncio.gather(reserve_slow(), reserve_fast()),
        timeout=5,
    )

    async with factory() as session:
        allocations = (
            await session.scalars(
                select(CreditReservationAllocationModel).where(
                    CreditReservationAllocationModel.reservation_id.in_(
                        (slow_reservation_id, fast_reservation_id)
                    )
                )
            )
        ).all()
        by_reservation = {item.reservation_id: item.lot_id for item in allocations}
        assert by_reservation == {
            fast_reservation_id: expiring.lot_id,
            slow_reservation_id: stable.lot_id,
        }


@pytest.mark.anyio
async def test_database_rejects_a_reservation_that_is_not_fully_allocated() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "allocation invariant")
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            principal.id,
            50,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="allocation-first-lot",
        )
        second = await repository.grant(
            principal.id,
            50,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="allocation-second-lot",
        )
        add_paid_billing_intent(
            session,
            principal,
            creation.response.execution.id,
            40,
        )
        reservation = await repository.reserve_inference(
            principal.id,
            creation.response.execution.id,
            40,
        )
        assert reservation is not None
        reservation_id = reservation.id
        await session.commit()

    async with factory() as session:
        second_lot = await session.get(CreditLotModel, second.lot_id)
        assert second_lot is not None
        session.add(
            CreditReservationAllocationModel(
                reservation_id=reservation_id,
                lot_id=second_lot.id,
                amount=1,
            )
        )
        with pytest.raises(DBAPIError, match="allocations do not match"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_a_reservation_allocated_from_another_wallet() -> None:
    owner = await create_user()
    other = await create_user()
    creation = await create_execution(owner, "foreign allocation")
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            owner.id,
            30,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="allocation-owner",
        )
        foreign_lot = await repository.grant(
            other.id,
            30,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="allocation-foreign",
        )
        await session.commit()

    async with factory() as session:
        owner_account = await session.scalar(
            select(CreditAccountModel).where(CreditAccountModel.owner_user_id == owner.id)
        )
        assert owner_account is not None
        transaction_id = uuid4()
        reservation_id = uuid4()
        add_paid_billing_intent(
            session,
            owner,
            creation.response.execution.id,
            20,
        )
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="reserve",
                idempotency_key_hash="b" * 64,
                reference_type="inference_execution",
                reference_id=creation.response.execution.id,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=owner_account.id,
                    amount=-20,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=20,
                ),
                InferenceCreditReservationModel(
                    id=reservation_id,
                    execution_reference_id=creation.response.execution.id,
                    owner_account_id=owner_account.id,
                    status=CreditReservationStatus.HELD.value,
                    reserved_amount=20,
                    settled_amount=0,
                    reserve_transaction_id=transaction_id,
                ),
            )
        )
        await session.flush()
        session.add(
            CreditReservationAllocationModel(
                reservation_id=reservation_id,
                lot_id=foreign_lot.lot_id,
                amount=20,
            )
        )
        with pytest.raises(DBAPIError, match="allocations do not match"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_reserving_a_lot_after_its_expiration() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "expired allocation")
    execution_id = creation.response.execution.id
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        grant = await CreditLedgerRepository(session).grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="expired-allocation-funds",
            expires_at=now + timedelta(minutes=1),
            now=now,
        )
        await session.commit()

    reserved_at = now + timedelta(minutes=2)
    async with factory() as session:
        account = await session.scalar(
            select(CreditAccountModel).where(
                CreditAccountModel.owner_user_id == principal.id
            )
        )
        assert account is not None
        transaction_id = uuid4()
        reservation_id = uuid4()
        add_paid_billing_intent(session, principal, execution_id, 5)
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="reserve",
                idempotency_key_hash="j" * 64,
                reference_type="inference_execution",
                reference_id=execution_id,
                effective_at=reserved_at,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=account.id,
                    amount=-5,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=5,
                ),
                InferenceCreditReservationModel(
                    id=reservation_id,
                    execution_reference_id=execution_id,
                    owner_account_id=account.id,
                    status=CreditReservationStatus.HELD.value,
                    reserved_amount=5,
                    settled_amount=0,
                    reserve_transaction_id=transaction_id,
                    created_at=reserved_at,
                ),
            )
        )
        await session.flush()
        session.add(
            CreditReservationAllocationModel(
                reservation_id=reservation_id,
                lot_id=grant.lot_id,
                amount=5,
            )
        )
        with pytest.raises(DBAPIError, match="allocations do not match"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_reservation_allocations_out_of_fefo_order() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "invalid reservation FEFO")
    execution_id = creation.response.execution.id
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="reservation-fefo-first",
            expires_at=now + timedelta(minutes=5),
            now=now,
        )
        stable = await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.PURCHASED,
            idempotency_key="reservation-fefo-second",
            now=now,
        )
        await session.commit()

    async with factory() as session:
        account = await session.scalar(
            select(CreditAccountModel).where(
                CreditAccountModel.owner_user_id == principal.id
            )
        )
        assert account is not None
        transaction_id = uuid4()
        reservation_id = uuid4()
        add_paid_billing_intent(session, principal, execution_id, 5)
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="reserve",
                idempotency_key_hash="k" * 64,
                reference_type="inference_execution",
                reference_id=execution_id,
                effective_at=now,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=account.id,
                    amount=-5,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=5,
                ),
                InferenceCreditReservationModel(
                    id=reservation_id,
                    execution_reference_id=execution_id,
                    owner_account_id=account.id,
                    status=CreditReservationStatus.HELD.value,
                    reserved_amount=5,
                    settled_amount=0,
                    reserve_transaction_id=transaction_id,
                    created_at=now,
                ),
            )
        )
        await session.flush()
        session.add(
            CreditReservationAllocationModel(
                reservation_id=reservation_id,
                lot_id=stable.lot_id,
                amount=5,
            )
        )
        with pytest.raises(DBAPIError, match="allocations do not match"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_settlement_consuming_an_unallocated_lot() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "foreign consumption")
    execution_id = creation.response.execution.id
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        lots = [
            await repository.grant(
                principal.id,
                20,
                source_kind=CreditSourceKind.ADMIN,
                idempotency_key=f"consumption-lot-{index}",
            )
            for index in range(2)
        ]
        add_paid_billing_intent(session, principal, execution_id, 10)
        reservation = await repository.reserve_inference(
            principal.id,
            execution_id,
            10,
        )
        assert reservation is not None
        reservation_id = reservation.id
        await session.commit()

    async with factory() as session:
        allocation = await session.scalar(
            select(CreditReservationAllocationModel).where(
                CreditReservationAllocationModel.reservation_id == reservation_id
            )
        )
        assert allocation is not None
        unallocated_lot_id = next(
            lot.lot_id for lot in lots if lot.lot_id != allocation.lot_id
        )
        reservation = await session.get(InferenceCreditReservationModel, reservation_id)
        assert reservation is not None
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="settle",
                idempotency_key_hash="c" * 64,
                reference_type="inference_execution",
                reference_id=execution_id,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=-10,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=REVENUE_ACCOUNT_ID,
                    amount=10,
                ),
            )
        )
        await session.flush()
        session.add(
            CreditLotConsumptionModel(
                lot_id=unallocated_lot_id,
                transaction_id=transaction_id,
                kind="settle",
                amount=10,
            )
        )
        reservation.status = CreditReservationStatus.SETTLED.value
        reservation.settled_amount = 10
        reservation.final_transaction_id = transaction_id
        reservation.finalized_at = datetime.now(timezone.utc)
        with pytest.raises(DBAPIError, match="finalization is inconsistent"):
            await session.commit()


@pytest.mark.anyio
async def test_settlement_consumes_fefo_and_expires_released_credit() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "FEFO")
    execution_id = creation.response.execution.id
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        expiring = await repository.grant(
            principal.id,
            50,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="expiring",
            expires_at=now + timedelta(minutes=1),
            now=now,
        )
        stable = await repository.grant(
            principal.id,
            50,
            source_kind=CreditSourceKind.PURCHASED,
            idempotency_key="stable",
            now=now,
        )
        add_paid_billing_intent(session, principal, execution_id, 70)
        await repository.reserve_inference(principal.id, execution_id, 70, now=now)
        await session.commit()

    async with factory() as session:
        repository = CreditLedgerRepository(session)
        reservation = await repository.finalize_inference(
            execution_id,
            30,
            now=now + timedelta(minutes=2),
        )
        await session.commit()
        assert reservation is not None
        assert reservation.status == CreditReservationStatus.SETTLED.value
        assert reservation.settled_amount == 30

    async with factory() as session:
        repository = CreditLedgerRepository(session)
        balance = await repository.balance(
            principal.id,
            now=now + timedelta(minutes=2),
        )
        assert balance.available == 50
        assert balance.reserved == 0
        allocations = (
            await session.scalars(
                select(CreditReservationAllocationModel).where(
                    CreditReservationAllocationModel.reservation_id == reservation.id
                )
            )
        ).all()
        assert [(item.lot_id, item.amount) for item in allocations] == [
            (expiring.lot_id, 50),
            (stable.lot_id, 20),
        ]
        consumptions = (
            await session.scalars(
                select(CreditLotConsumptionModel).where(
                    CreditLotConsumptionModel.lot_id == expiring.lot_id
                )
            )
        ).all()
        assert sorted((item.kind, item.amount) for item in consumptions) == [
            ("expire", 20),
            ("settle", 30),
        ]


@pytest.mark.anyio
async def test_database_rejects_returning_an_expired_reserved_lot() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "expired return")
    execution_id = creation.response.execution.id
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="expired-return-funds",
            expires_at=now + timedelta(minutes=1),
            now=now,
        )
        add_paid_billing_intent(session, principal, execution_id, 10)
        reservation = await repository.reserve_inference(
            principal.id,
            execution_id,
            10,
            now=now,
        )
        assert reservation is not None
        reservation_id = reservation.id
        await session.commit()

    finalized_at = now + timedelta(minutes=2)
    async with factory() as session:
        reservation = await session.get(InferenceCreditReservationModel, reservation_id)
        assert reservation is not None
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="release",
                idempotency_key_hash="g" * 64,
                reference_type="inference_execution",
                reference_id=execution_id,
                effective_at=finalized_at,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=-10,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=reservation.owner_account_id,
                    amount=10,
                ),
            )
        )
        reservation.status = CreditReservationStatus.RELEASED.value
        reservation.settled_amount = 0
        reservation.final_transaction_id = transaction_id
        reservation.finalized_at = finalized_at
        with pytest.raises(DBAPIError, match="finalization is inconsistent"):
            await session.commit()


@pytest.mark.anyio
async def test_database_rejects_settling_reserved_lots_out_of_fefo_order() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "invalid FEFO")
    execution_id = creation.response.execution.id
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="fefo-first",
            expires_at=now + timedelta(minutes=5),
            now=now,
        )
        stable = await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.PURCHASED,
            idempotency_key="fefo-second",
            now=now,
        )
        add_paid_billing_intent(session, principal, execution_id, 20)
        reservation = await repository.reserve_inference(
            principal.id,
            execution_id,
            20,
            now=now,
        )
        assert reservation is not None
        reservation_id = reservation.id
        await session.commit()

    finalized_at = now + timedelta(minutes=1)
    async with factory() as session:
        reservation = await session.get(InferenceCreditReservationModel, reservation_id)
        assert reservation is not None
        transaction_id = uuid4()
        session.add(
            CreditTransactionModel(
                id=transaction_id,
                kind="settle",
                idempotency_key_hash="h" * 64,
                reference_type="inference_execution",
                reference_id=execution_id,
                effective_at=finalized_at,
            )
        )
        session.add_all(
            (
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=RESERVE_ACCOUNT_ID,
                    amount=-20,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=REVENUE_ACCOUNT_ID,
                    amount=10,
                ),
                CreditPostingModel(
                    transaction_id=transaction_id,
                    account_id=reservation.owner_account_id,
                    amount=10,
                ),
            )
        )
        await session.flush()
        session.add(
            CreditLotConsumptionModel(
                lot_id=stable.lot_id,
                transaction_id=transaction_id,
                kind="settle",
                amount=10,
            )
        )
        reservation.status = CreditReservationStatus.SETTLED.value
        reservation.settled_amount = 10
        reservation.final_transaction_id = transaction_id
        reservation.finalized_at = finalized_at
        with pytest.raises(DBAPIError, match="finalization is inconsistent"):
            await session.commit()


@pytest.mark.anyio
async def test_due_lot_expiration_is_idempotent() -> None:
    principal = await create_user()
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            25,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="expires",
            expires_at=now + timedelta(seconds=1),
            now=now,
        )
        await CreditLedgerRepository(session).grant(
            principal.id,
            30,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="expires-later",
            expires_at=now + timedelta(seconds=2),
            now=now,
        )
        await session.commit()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        expired = await repository.expire_due(
            now + timedelta(seconds=1, milliseconds=500),
            limit=1,
        )
        assert expired == 1
        await session.commit()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        assert await repository.expire_due(now + timedelta(seconds=3), limit=1) == 1
        await session.commit()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        assert await repository.expire_due(now + timedelta(seconds=4), limit=1) == 0
        await session.commit()
        assert (
            await repository.balance(
                principal.id,
                now=now + timedelta(seconds=4),
            )
        ).available == 0


@pytest.mark.anyio
async def test_balance_excludes_expired_credit_before_the_expiration_sweep() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "unswept expiration")
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.PROMOTIONAL,
            idempotency_key="unswept-expiration",
            expires_at=now + timedelta(minutes=1),
            now=now,
        )
        await session.commit()

    after_expiration = now + timedelta(minutes=2)
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        balance = await repository.balance(principal.id, now=after_expiration)
        assert balance.available == 0
        assert balance.reserved == 0
        add_paid_billing_intent(
            session,
            principal,
            creation.response.execution.id,
            1,
        )
        with pytest.raises(InsufficientCreditsError):
            await repository.reserve_inference(
                principal.id,
                creation.response.execution.id,
                1,
                now=after_expiration,
            )


@pytest.mark.anyio
async def test_transaction_history_cursor_has_no_duplicates_or_gaps() -> None:
    principal = await create_user()
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        for index in range(3):
            await repository.grant(
                principal.id,
                index + 1,
                source_kind=CreditSourceKind.ADMIN,
                idempotency_key=f"page-{index}",
            )
        await session.commit()

    service = CreditService(factory)
    first = await service.transactions(principal.id, limit=2)
    assert len(first.items) == 2
    assert first.next_cursor is not None
    second = await service.transactions(
        principal.id,
        limit=2,
        cursor=first.next_cursor,
    )
    ids = [item.id for item in (*first.items, *second.items)]
    assert len(second.items) == 1
    assert second.next_cursor is None
    assert len(ids) == len(set(ids)) == 3


@pytest.mark.anyio
async def test_user_deletion_pseudonymizes_but_preserves_the_ledger() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "retained financial record")
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        grant = await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="pseudonymized-ledger",
        )
        add_paid_billing_intent(
            session,
            principal,
            creation.response.execution.id,
            5,
            fixed_charge=3,
        )
        reservation = await repository.reserve_inference(
            principal.id,
            creation.response.execution.id,
            5,
        )
        assert reservation is not None
        reservation_id = reservation.id
        await session.commit()
    started = GenerationEvent.create(
        GenerationEventType.STARTED,
        execution_id=creation.response.execution.id,
        attempt_id=creation.response.execution.attempt_id,
        sequence=0,
        thread_id=creation.thread.id,
        resolved_model="asuka-1@pseudo-v1",
        input_tokens=0,
    )
    completed = GenerationEvent.create(
        GenerationEventType.COMPLETED,
        execution_id=creation.response.execution.id,
        attempt_id=creation.response.execution.attempt_id,
        sequence=1,
        thread_id=creation.thread.id,
        content="retained",
        output_tokens=0,
        finish_reason=FinishReason.STOP,
    )
    async with factory() as session:
        await SqlAlchemyThreadRepository(session).project_generation_event(started)
        await session.commit()
    async with factory() as session:
        await SqlAlchemyThreadRepository(session).project_generation_event(completed)
        await InferenceBillingService(session).finalize(creation.response.execution.id)
        await session.commit()
    async with factory() as session:
        user = await session.get(UserModel, principal.id)
        assert user is not None
        await session.delete(user)
        await session.commit()
    async with factory() as session:
        account = await session.scalar(
            select(CreditAccountModel)
            .join(
                CreditPostingModel,
                CreditPostingModel.account_id == CreditAccountModel.id,
            )
            .where(CreditPostingModel.transaction_id == grant.transaction_id)
        )
        assert account is not None
        assert account.owner_user_id is None
        assert await session.get(CreditTransactionModel, grant.transaction_id) is not None
        retained = await session.get(InferenceCreditReservationModel, reservation_id)
        assert retained is not None
        assert retained.execution_reference_id == creation.response.execution.id
        assert retained.status == CreditReservationStatus.SETTLED.value


@pytest.mark.anyio
async def test_user_deletion_waits_for_held_reservations_to_finish() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "active financial record")
    factory = get_session_factory()
    async with factory() as session:
        repository = CreditLedgerRepository(session)
        await repository.grant(
            principal.id,
            10,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="active-ledger",
        )
        add_paid_billing_intent(
            session,
            principal,
            creation.response.execution.id,
            5,
        )
        await repository.reserve_inference(
            principal.id,
            creation.response.execution.id,
            5,
        )
        await session.commit()

    async with factory() as session:
        user = await session.get(UserModel, principal.id)
        assert user is not None
        await session.delete(user)
        with pytest.raises(DBAPIError, match="held credit reservations"):
            await session.commit()

    failed = GenerationEvent.create(
        GenerationEventType.FAILED,
        execution_id=creation.response.execution.id,
        attempt_id=creation.response.execution.attempt_id,
        sequence=0,
        thread_id=creation.thread.id,
        error_code="account_deleted",
    )
    async with factory() as session:
        await SqlAlchemyThreadRepository(session).project_generation_event(failed)
        await InferenceBillingService(session).finalize(creation.response.execution.id)
        await session.commit()
    async with factory() as session:
        user = await session.get(UserModel, principal.id)
        assert user is not None
        await session.delete(user)
        await session.commit()


@pytest.mark.anyio
async def test_inference_billing_records_usage_and_is_terminally_idempotent() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "billing")
    execution = creation.response.execution
    tariff = InferenceTariff(
        revision="integration-metered-v1",
        fixed_charge=2,
        input_token_rate=1,
        output_token_rate=2,
        maximum_charge=100,
        unmetered_charge=100,
    )
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            200,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="billing-funds",
        )
        await InferenceBillingService(session).register(principal, execution, tariff)
        await session.commit()

    started = GenerationEvent.create(
        GenerationEventType.STARTED,
        execution_id=execution.id,
        attempt_id=execution.attempt_id,
        sequence=0,
        thread_id=creation.thread.id,
        resolved_model="asuka-1@pseudo-v1",
        input_tokens=10,
    )
    completed = GenerationEvent.create(
        GenerationEventType.COMPLETED,
        execution_id=execution.id,
        attempt_id=execution.attempt_id,
        sequence=1,
        thread_id=creation.thread.id,
        content="recorded",
        output_tokens=5,
        finish_reason=FinishReason.STOP,
    )
    async with factory() as session:
        await SqlAlchemyThreadRepository(session).project_generation_event(started)
        await session.commit()
    async with factory() as session:
        result = await SqlAlchemyThreadRepository(session).project_generation_event(completed)
        assert result.projection is not None
        await session.commit()

    async def finalize_once() -> UUID:
        async with factory() as session:
            usage = await InferenceBillingService(session).finalize(execution.id)
            await session.commit()
            return usage.execution_reference_id

    finalized = await asyncio.wait_for(
        asyncio.gather(finalize_once(), finalize_once()),
        timeout=5,
    )
    assert finalized == [execution.id, execution.id]

    async with factory() as session:
        usage = await session.get(InferenceUsageRecordModel, execution.id)
        reservation = await session.scalar(
            select(InferenceCreditReservationModel).where(
                InferenceCreditReservationModel.execution_reference_id == execution.id
            )
        )
        assert usage is not None
        assert usage.input_tokens == 10
        assert usage.output_tokens == 5
        assert usage.charged_amount == 22
        assert usage.billing_reason == "completed"
        assert reservation is not None
        assert reservation.settled_amount == 22
        balance = await CreditLedgerRepository(session).balance(principal.id)
        assert balance.available == 178
        assert balance.reserved == 0

    async with factory() as session:
        user = await session.get(UserModel, principal.id)
        assert user is not None
        await session.delete(user)
        await session.commit()
    async with factory() as session:
        intent = await session.get(InferenceBillingIntentModel, execution.id)
        usage = await session.get(InferenceUsageRecordModel, execution.id)
        assert intent is not None
        assert intent.user_id is None
        assert intent.tariff_revision == "integration-metered-v1"
        assert usage is not None
        assert usage.user_id is None
        assert usage.charged_amount == 22
        with pytest.raises(DBAPIError, match="credit billing records are immutable"):
            await session.execute(
                update(InferenceUsageRecordModel)
                .where(
                    InferenceUsageRecordModel.execution_reference_id == execution.id
                )
                .values(charged_amount=23)
            )


@pytest.mark.anyio
async def test_failed_inference_releases_the_full_reservation_once() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "failure")
    execution = creation.response.execution
    tariff = InferenceTariff(
        revision="integration-failure-v1",
        fixed_charge=5,
        maximum_charge=80,
        unmetered_charge=80,
    )
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            100,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="failure-funds",
        )
        await InferenceBillingService(session).register(principal, execution, tariff)
        await session.commit()

    async with factory() as session:
        active = await session.get(ExecutionModel, execution.id)
        assert active is not None
        await session.delete(active)
        with pytest.raises(DBAPIError, match="billable executions must be finalized"):
            await session.commit()

    failed = GenerationEvent.create(
        GenerationEventType.FAILED,
        execution_id=execution.id,
        attempt_id=execution.attempt_id,
        sequence=0,
        thread_id=creation.thread.id,
        error_code="integration_failure",
    )
    async with factory() as session:
        result = await SqlAlchemyThreadRepository(session).project_generation_event(failed)
        assert result.projection is not None
        first = await InferenceBillingService(session).finalize(execution.id)
        replay = await InferenceBillingService(session).finalize(execution.id)
        await session.commit()
        assert replay is first

    async with factory() as session:
        usage = await session.get(InferenceUsageRecordModel, execution.id)
        reservation = await session.scalar(
            select(InferenceCreditReservationModel).where(
                InferenceCreditReservationModel.execution_reference_id == execution.id
            )
        )
        assert usage is not None
        assert usage.outcome == "failed"
        assert usage.billing_reason == "failed"
        assert usage.charged_amount == 0
        assert reservation is not None
        assert reservation.status == CreditReservationStatus.RELEASED.value
        balance = await CreditLedgerRepository(session).balance(principal.id)
        assert balance.available == 100
        assert balance.reserved == 0


@pytest.mark.anyio
async def test_timed_out_inference_releases_its_reservation() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "timeout")
    execution = creation.response.execution
    tariff = InferenceTariff(
        revision="integration-timeout-v1",
        maximum_charge=60,
        unmetered_charge=60,
    )
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            100,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="timeout-funds",
        )
        await InferenceBillingService(session).register(principal, execution, tariff)
        await session.commit()

    async with factory() as session:
        projections = await SqlAlchemyThreadRepository(session).expire_executions(
            datetime.now(timezone.utc) + timedelta(minutes=10)
        )
        assert execution.id in {
            projection.execution_id for projection in projections
        }
        await InferenceBillingService(session).finalize(execution.id)
        await session.commit()

    async with factory() as session:
        usage = await session.get(InferenceUsageRecordModel, execution.id)
        assert usage is not None
        assert usage.outcome == "failed"
        assert usage.billing_reason == "failed"
        balance = await CreditLedgerRepository(session).balance(principal.id)
        assert balance.available == 100
        assert balance.reserved == 0


@pytest.mark.anyio
async def test_paid_projection_and_settlement_roll_back_together() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "atomic billing")
    execution = creation.response.execution
    tariff = InferenceTariff(
        revision="integration-atomic-v1",
        maximum_charge=80,
        unmetered_charge=80,
    )
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            100,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="atomic-funds",
        )
        await InferenceBillingService(session).register(principal, execution, tariff)
        await session.commit()

    failed = GenerationEvent.create(
        GenerationEventType.FAILED,
        execution_id=execution.id,
        attempt_id=execution.attempt_id,
        sequence=0,
        thread_id=creation.thread.id,
        error_code="atomic_failure",
    )
    async with factory() as session:
        await SqlAlchemyThreadRepository(session).project_generation_event(failed)
        await InferenceBillingService(session).finalize(execution.id)
        await session.rollback()

    async with factory() as session:
        persisted_execution = await session.get(ExecutionModel, execution.id)
        reservation = await session.scalar(
            select(InferenceCreditReservationModel).where(
                InferenceCreditReservationModel.execution_reference_id == execution.id
            )
        )
        assert persisted_execution is not None
        assert persisted_execution.status == "queued"
        assert reservation is not None
        assert reservation.status == CreditReservationStatus.HELD.value
        assert await session.get(InferenceUsageRecordModel, execution.id) is None
        balance = await CreditLedgerRepository(session).balance(principal.id)
        assert balance.available == 20
        assert balance.reserved == 80

    async with factory() as session:
        await SqlAlchemyThreadRepository(session).project_generation_event(failed)
        await InferenceBillingService(session).finalize(execution.id)
        await session.commit()


@pytest.mark.anyio
async def test_unmetered_paid_completion_uses_the_explicit_fallback() -> None:
    principal = await create_user()
    creation = await create_execution(principal, "unmetered")
    execution = creation.response.execution
    tariff = InferenceTariff(
        revision="integration-unmetered-v1",
        input_token_rate=1,
        output_token_rate=2,
        maximum_charge=50,
        unmetered_charge=40,
    )
    factory = get_session_factory()
    async with factory() as session:
        await CreditLedgerRepository(session).grant(
            principal.id,
            100,
            source_kind=CreditSourceKind.ADMIN,
            idempotency_key="unmetered-funds",
        )
        await InferenceBillingService(session).register(principal, execution, tariff)
        await session.commit()

    events = (
        GenerationEvent.create(
            GenerationEventType.STARTED,
            execution_id=execution.id,
            attempt_id=execution.attempt_id,
            sequence=0,
            thread_id=creation.thread.id,
            resolved_model="asuka-1@pseudo-v1",
        ),
        GenerationEvent.create(
            GenerationEventType.COMPLETED,
            execution_id=execution.id,
            attempt_id=execution.attempt_id,
            sequence=1,
            thread_id=creation.thread.id,
            content="unmetered",
            finish_reason=FinishReason.STOP,
        ),
    )
    for event in events:
        async with factory() as session:
            await SqlAlchemyThreadRepository(session).project_generation_event(event)
            if event.type is GenerationEventType.COMPLETED:
                await InferenceBillingService(session).finalize(execution.id)
            await session.commit()

    async with factory() as session:
        usage = await session.get(InferenceUsageRecordModel, execution.id)
        assert usage is not None
        assert usage.billing_reason == "unmetered"
        assert usage.charged_amount == 40
        balance = await CreditLedgerRepository(session).balance(principal.id)
        assert balance.available == 60
        assert balance.reserved == 0


@pytest.mark.anyio
async def test_insufficient_credits_roll_back_the_entire_thread_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    principal = await create_user()
    answerer = get_answerer(AnswererId.ASUKA_1)
    assert answerer is not None
    paid_answerer = replace(
        answerer,
        tariff=InferenceTariff(
            revision="integration-insufficient-v1",
            maximum_charge=10,
            unmetered_charge=10,
        ),
    )
    monkeypatch.setattr(
        ThreadService,
        "select_answerer",
        staticmethod(lambda _principal, _requested: paid_answerer),
    )
    settings = get_settings()
    service = ThreadService(
        get_session_factory(),
        ModelDeploymentRegistry(settings.model_root),
        settings,
    )

    with pytest.raises(InsufficientCreditsError):
        await service.create(principal, "no funds", AnswererId.ASUKA_1)

    async with get_session_factory()() as session:
        space_count = await session.scalar(
            select(func.count())
            .select_from(SpaceModel)
            .where(SpaceModel.owner_user_id == principal.id)
        )
        intent_count = await session.scalar(
            select(func.count())
            .select_from(InferenceBillingIntentModel)
            .where(InferenceBillingIntentModel.user_id == principal.id)
        )
        account = await session.scalar(
            select(CreditAccountModel).where(
                CreditAccountModel.owner_user_id == principal.id
            )
        )
        assert space_count == 0
        assert intent_count == 0
        assert account is None
