import asyncio

from app.db.session import dispose_engine
from app.services.credits import get_credit_service


async def _run() -> None:
    try:
        count = await get_credit_service().expire_due()
        print(f"expired_lots={count}")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_run())
