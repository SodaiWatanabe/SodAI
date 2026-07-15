import argparse
import asyncio
from uuid import UUID

from app.db.session import dispose_engine
from app.services.human import get_human_service


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set one user's Human rank")
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--rank", required=True, type=int, choices=range(1, 101))
    return parser.parse_args()


async def _run() -> None:
    arguments = _arguments()
    try:
        state = await get_human_service().set_rank(arguments.user_id, arguments.rank)
        print(f"user={arguments.user_id} rank={state.rank_level}")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_run())
