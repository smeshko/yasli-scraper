from __future__ import annotations

import httpx
import pytest
import respx

from yasli_scraper.http import USER_AGENT, ContentLengthMismatch, FetchError, fetch


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip backoff sleeps so the suite runs fast."""
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("yasli_scraper.http.asyncio.sleep", _instant)


@respx.mock
async def test_fetch_returns_body_on_200() -> None:
    route = respx.get("https://example.test/x").mock(
        return_value=httpx.Response(200, content=b"hello")
    )
    async with httpx.AsyncClient() as client:
        body = await fetch(client, "GET", "https://example.test/x")
    assert body == b"hello"
    assert route.call_count == 1


@respx.mock
async def test_fetch_sends_user_agent_header() -> None:
    route = respx.get("https://example.test/ua").mock(
        return_value=httpx.Response(200, content=b"ok")
    )
    async with httpx.AsyncClient() as client:
        await fetch(client, "GET", "https://example.test/ua")
    sent = route.calls.last.request
    assert sent.headers["user-agent"] == USER_AGENT
    assert sent.headers["user-agent"]


@respx.mock
async def test_fetch_recovers_from_transient_500() -> None:
    route = respx.get("https://example.test/flaky").mock(
        side_effect=[
            httpx.Response(500, content=b""),
            httpx.Response(200, content=b"recovered"),
        ]
    )
    async with httpx.AsyncClient() as client:
        body = await fetch(
            client, "GET", "https://example.test/flaky", base_backoff=0
        )
    assert body == b"recovered"
    assert route.call_count == 2


@respx.mock
async def test_fetch_raises_after_persistent_failure() -> None:
    respx.get("https://example.test/dead").mock(
        return_value=httpx.Response(500, content=b"")
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError) as exc_info:
            await fetch(
                client, "GET", "https://example.test/dead", base_backoff=0
            )
    assert "https://example.test/dead" in str(exc_info.value)
    assert exc_info.value.__cause__ is not None


@respx.mock
async def test_fetch_raises_on_content_length_mismatch() -> None:
    respx.get("https://example.test/truncated").mock(
        return_value=httpx.Response(
            200, content=b"short", headers={"Content-Length": "999"}
        )
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(FetchError) as exc_info:
            await fetch(
                client, "GET", "https://example.test/truncated", base_backoff=0
            )
    assert isinstance(exc_info.value.__cause__, ContentLengthMismatch)


@respx.mock
async def test_fetch_passes_json_body_to_post() -> None:
    route = respx.post("https://example.test/api").mock(
        return_value=httpx.Response(200, content=b"{}")
    )
    async with httpx.AsyncClient() as client:
        await fetch(
            client,
            "POST",
            "https://example.test/api",
            json={"reception": "garden"},
        )
    sent = route.calls.last.request
    assert sent.content == b'{"reception":"garden"}'
