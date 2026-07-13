import argparse
import asyncio
from datetime import datetime
from uuid import UUID

from app.db.session import dispose_engine
from app.domain.credits import CreditSourceKind
from app.services.credits import get_credit_service


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Grant SodAI credits to one user")
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--amount", required=True, type=int)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument(
        "--source-kind",
        choices=[kind.value for kind in CreditSourceKind],
        default=CreditSourceKind.ADMIN.value,
    )
    parser.add_argument("--expires-at", type=datetime.fromisoformat)
    return parser.parse_args()


async def _run() -> None:
    arguments = _arguments()
    try:
        grant = await get_credit_service().grant(
            arguments.user_id,
            arguments.amount,
            idempotency_key=arguments.idempotency_key,
            source_kind=CreditSourceKind(arguments.source_kind),
            expires_at=arguments.expires_at,
        )
        print(
            f"transaction={grant.transaction_id} lot={grant.lot_id} "
            f"amount={grant.amount} replayed={str(grant.replayed).lower()}"
        )
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_run())
