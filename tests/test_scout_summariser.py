"""Tests for pilab.scout.summariser."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from pilab.scout.summariser import summarise


pytestmark = pytest.mark.asyncio


async def test_summarise_calls_llm():
    with patch("pilab.scout.summariser.call_llm", new_callable=AsyncMock) as mock:
        mock.return_value = "This is a 3 sentence summary."
        result = await summarise("Test Title", "Some raw content here")
        assert result == "This is a 3 sentence summary."
        mock.assert_called_once()
        # Verify it passes title and content in user prompt
        call_kwargs = mock.call_args
        assert "Test Title" in call_kwargs.kwargs["user"]
        assert "Some raw content here" in call_kwargs.kwargs["user"]


async def test_summarise_truncates_content():
    with patch("pilab.scout.summariser.call_llm", new_callable=AsyncMock) as mock:
        mock.return_value = "Summary."
        long_content = "x" * 5000
        await summarise("Title", long_content)
        user_prompt = mock.call_args.kwargs["user"]
        # Content truncated to 2000 chars, plus title line
        assert len(user_prompt) < 2100
