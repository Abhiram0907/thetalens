"""Intent returns is_clear=False when underlying cannot be resolved."""

import pytest

from app.core.security import INTENT_UNRECOGNIZED
from app.services.intent import evaluate_intent


@pytest.mark.asyncio
async def test_unrecognized_thesis_not_clear():
    result = await evaluate_intent("tell me something interesting")
    assert result.is_clear is False
    assert result.captured.underlying is None
    assert result.summary == INTENT_UNRECOGNIZED
    assert "underlying" in result.missing
