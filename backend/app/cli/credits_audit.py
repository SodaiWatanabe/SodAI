import asyncio

from app.db.session import dispose_engine, get_session_factory
from app.services.credit_audit import CreditAuditService


async def _run() -> None:
    try:
        report = await CreditAuditService(get_session_factory()).audit()
        print(f"earned_lots={report.scanned_earned_lots}")
        print(f"human_reservations={report.scanned_human_reservations}")
        if report.issues:
            for issue in report.issues:
                print(f"ERROR {issue}")
            raise SystemExit(1)
        print("status=ok")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_run())
