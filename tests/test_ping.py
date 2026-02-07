"""Unit tests for ping result parsing (core.ping); mock subprocess."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from core.ping import run_ping, _interpret, _parse_latency, PingResult


def test_parse_latency_windows():
    out = "Reply from 8.8.8.8: bytes=32 time=23ms TTL=54"
    assert _parse_latency(out) == 23.0


def test_parse_latency_linux():
    out = "64 bytes from 8.8.8.8: icmp_seq=1 ttl=54 time=12.3 ms"
    assert _parse_latency(out) == 12.3


def test_parse_latency_fallback():
    out = "something 42.5 ms"
    assert _parse_latency(out) == 42.5


def test_parse_latency_none():
    assert _parse_latency("no time here") is None


def test_interpret_success_with_latency():
    r = _interpret(0, "time=15ms", 14.0, 1000)
    assert r.success is True
    assert r.reason == "OK"
    assert r.latency_ms == 15.0


def test_interpret_success_fallback_elapsed():
    r = _interpret(0, "reply", 22.5, 1000)
    assert r.success is True
    assert r.latency_ms == 22.5


def test_interpret_timeout():
    r = _interpret(1, "Request timed out.", 0, 1000)
    assert r.success is False
    assert r.reason == "TIMEOUT"
    assert r.latency_ms is None


def test_interpret_unreachable():
    r = _interpret(1, "Destination Host Unreachable", 0, 1000)
    assert r.success is False
    assert r.reason == "UNREACHABLE"


def test_interpret_error_code():
    r = _interpret(2, "unknown", 0, 1000)
    assert r.success is False
    assert r.reason == "ERROR:2"


@pytest.mark.asyncio
async def test_run_ping_mock_success():
    with patch("core.ping.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"time=10ms", b""))
        mock_exec.return_value = proc
        result = await run_ping("127.0.0.1", 1000)
        assert result.success is True
        assert result.reason == "OK"
        assert result.latency_ms is not None


@pytest.mark.asyncio
async def test_run_ping_mock_timeout():
    import asyncio
    with patch("core.ping.asyncio.create_subprocess_exec", new_callable=AsyncMock), \
         patch("core.ping.asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
        mock_wait.side_effect = asyncio.TimeoutError()
        result = await run_ping("192.168.255.254", 500)
        assert result.success is False
        assert result.reason == "TIMEOUT"
        assert result.latency_ms is None
