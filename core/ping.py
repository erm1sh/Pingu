"""
ICMP ping via subprocess (1 packet). Windows: ping -n 1 -w <timeout_ms> <host>.
Linux/macOS: ping -c 1 -W <timeout_s> <host>.
Capture return code and elapsed time; parse output only if needed for reason.
"""
import asyncio
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class PingResult:
    success: bool
    latency_ms: Optional[float]  # None if failed or unparseable
    reason: str  # "OK", "TIMEOUT", "UNREACHABLE", "ERROR:<code>"


def _timeout_seconds(timeout_ms: int) -> int:
    return max(1, (timeout_ms + 999) // 1000)


async def run_ping(host: str, timeout_ms: int) -> PingResult:
    """
    Run one ping. Returns PingResult with success, latency_ms (if success), and reason string.
    """
    if sys.platform == "win32":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
        timeout_s = (timeout_ms / 1000.0) + 2.0
    else:
        timeout_s = _timeout_seconds(timeout_ms)
        cmd = ["ping", "-c", "1", "-W", str(timeout_s), host]
        timeout_s = timeout_s + 2.0

    start = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_s
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return _interpret(proc.returncode or 0, stdout.decode("utf-8", errors="replace"), elapsed_ms, timeout_ms)
    except asyncio.TimeoutError:
        return PingResult(success=False, latency_ms=None, reason="TIMEOUT")
    except Exception as e:
        return PingResult(success=False, latency_ms=None, reason=f"ERROR:{getattr(e, 'returncode', type(e).__name__)}")


def _interpret(returncode: int, output: str, elapsed_ms: float, timeout_ms: int) -> PingResult:
    """Interpret ping return code and optional output for latency/reason."""
    if returncode == 0:
        lat = _parse_latency(output)
        return PingResult(success=True, latency_ms=lat if lat is not None else round(elapsed_ms, 1), reason="OK")
    # Failure
    output_lower = output.lower()
    if "timed out" in output_lower or "timeout" in output_lower or "request timed out" in output_lower:
        reason = "TIMEOUT"
    elif "unreachable" in output_lower:
        reason = "UNREACHABLE"
    else:
        reason = f"ERROR:{returncode}"
    return PingResult(success=False, latency_ms=None, reason=reason)


def _parse_latency(output: str) -> Optional[float]:
    """Extract latency in ms from ping output. Windows: time=12ms, Linux: time=12.3 ms."""
    # Windows: "Reply from ...: time=23ms TTL=..."
    # Linux: "rtt ... = 12.3/12.3/12.3 ms" or "time=12.3 ms"
    m = re.search(r"time[=:]?\s*([\d.]+)\s*ms", output, re.I)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    m = re.search(r"([\d.]+)\s*ms", output)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None
