import base64
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.services.human_answers import HumanAnswerHistoryService


def test_human_answer_cursor_requires_an_aware_timestamp_and_uuid() -> None:
    with pytest.raises(ValueError, match="invalid Human answer cursor"):
        HumanAnswerHistoryService._parse_cursor("not-a-cursor")

    timestamp = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    execution_id = uuid4()
    raw = f"{timestamp.isoformat()}|{execution_id}".encode()
    cursor = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    assert HumanAnswerHistoryService._parse_cursor(cursor) == (
        timestamp,
        execution_id,
    )
