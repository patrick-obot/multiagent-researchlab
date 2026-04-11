"""Tests for pilab.shared.llm — JSON repair and LLM client."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pilab.shared.llm import (
    _strip_markdown_fences,
    _fix_trailing_commas,
    _extract_json_object,
    repair_json,
    call_llm,
    call_json,
)


# -------------------------------------------------------------------
# JSON repair helpers
# -------------------------------------------------------------------

class TestStripMarkdownFences:
    def test_no_fences(self):
        assert _strip_markdown_fences('{"a": 1}') == '{"a": 1}'

    def test_json_fences(self):
        assert _strip_markdown_fences('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_plain_fences(self):
        assert _strip_markdown_fences('```\n{"a": 1}\n```') == '{"a": 1}'


class TestFixTrailingCommas:
    def test_trailing_comma_object(self):
        assert _fix_trailing_commas('{"a": 1, }') == '{"a": 1}'

    def test_trailing_comma_array(self):
        assert _fix_trailing_commas('[1, 2, ]') == '[1, 2]'

    def test_no_trailing_comma(self):
        assert _fix_trailing_commas('{"a": 1}') == '{"a": 1}'


class TestExtractJsonObject:
    def test_extract_object(self):
        result = _extract_json_object('blah blah {"key": "value"} more stuff')
        assert result == '{"key": "value"}'

    def test_extract_array(self):
        result = _extract_json_object('prefix [1, 2, 3] suffix')
        assert result == '[1, 2, 3]'

    def test_nested(self):
        result = _extract_json_object('x {"a": {"b": 1}} y')
        assert result == '{"a": {"b": 1}}'

    def test_no_json(self):
        assert _extract_json_object('no json here') is None


class TestRepairJson:
    def test_valid_json(self):
        assert repair_json('{"a": 1}') == {"a": 1}

    def test_with_fences(self):
        assert repair_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_trailing_comma(self):
        assert repair_json('{"a": 1,}') == {"a": 1}

    def test_embedded_json(self):
        result = repair_json('Here is the result: {"score": 7} end')
        assert result == {"score": 7}

    def test_unparseable(self):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            repair_json("this is not json at all")

    def test_array(self):
        result = repair_json('[{"a": 1}, {"b": 2}]')
        assert len(result) == 2


# -------------------------------------------------------------------
# LLM client
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_llm_success():
    mock_response = {
        "choices": [{"message": {"content": "hello world"}}]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("pilab.shared.llm.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await call_llm(
            "http://localhost:8080",
            system="sys", user="usr",
        )
        assert result == "hello world"

        # Verify no model field in payload when model is None
        posted_payload = mock_client.post.call_args[1]["json"]
        assert "model" not in posted_payload


@pytest.mark.asyncio
async def test_call_llm_with_model():
    mock_response = {
        "choices": [{"message": {"content": "hello"}}]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("pilab.shared.llm.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await call_llm(
            "http://localhost:11434",
            model="phi3:mini",
            system="sys", user="usr",
        )
        assert result == "hello"

        # Verify model field is present in payload
        posted_payload = mock_client.post.call_args[1]["json"]
        assert posted_payload["model"] == "phi3:mini"


@pytest.mark.asyncio
async def test_call_json_parses_response():
    with patch("pilab.shared.llm.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"score": 7}'
        result = await call_json(
            "http://localhost:8080",
            system="sys", user="usr",
        )
        assert result == {"score": 7}


@pytest.mark.asyncio
async def test_call_json_repairs_fences():
    with patch("pilab.shared.llm.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '```json\n{"score": 7}\n```'
        result = await call_json(
            "http://localhost:8080",
            system="sys", user="usr",
        )
        assert result == {"score": 7}
