"""
Asyncio scheduler: per-target intervals with jitter, global concurrency limit.
Publish ping results to async queue; UI consumes via timer/signals.
Ping workers never touch UI.
"""
import asyncio
import logging
import random
from dataclasses import dataclass, field
from queue import Queue
from typing import Optional

from core.config import TargetConfig
from core.ping import PingResult, run_ping
from core.state import OutageState, State
from core import notify

logger = logging.getLogger("pingu.monitor")


@dataclass
class MonitorUpdate:
    """One update for the UI: alias and display line + status."""
    alias: str
    host: str
    line: str  # "<ALIAS> - OK <DETAIL>" or "<ALIAS> - DOWN <DETAIL>"
    success: bool
    detail: str  # e.g. "23ms" or "TIMEOUT"
    display_mode: str  # "latency" | "codes"


def detail_for_display(success: bool, detail: str, display_mode: str) -> str:
    """Format DETAIL for display: latency -> '23ms' or 'TIMEOUT'; codes -> 200, 408, 503."""
    if display_mode == "codes":
        if success:
            return "200"
        if "TIMEOUT" in detail.upper():
            return "408"
        return "503"
    return detail


@dataclass
class MonitorState:
    targets: list[TargetConfig] = field(default_factory=list)
    concurrency: int = 5
    jitter_ms: tuple[int, int] = (0, 300)
    display_mode: str = "latency"
    notifications_enabled: bool = True
    sound_on_down: bool = True
    outage_states: dict[str, OutageState] = field(default_factory=dict)
    _sem: Optional[asyncio.Semaphore] = None
    _queue: Optional[asyncio.Queue] = None
    thread_safe_queue: Optional[Queue] = None  # GUI drains this on timer

    def ensure_structures(self) -> None:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.concurrency)
        if self._queue is None:
            self._queue = asyncio.Queue()
        for t in self.targets:
            if t.alias not in self.outage_states:
                self.outage_states[t.alias] = OutageState()

    @property
    def queue(self) -> asyncio.Queue:
        self.ensure_structures()
        return self._queue

    @property
    def sem(self) -> asyncio.Semaphore:
        self.ensure_structures()
        return self._sem


async def run_one_target(
    target: TargetConfig,
    state: MonitorState,
) -> None:
    """Run ping for one target, update state machine, push to queue, maybe notify."""
    async with state.sem:
        result = await run_ping(target.host, target.timeout)
        ost = state.outage_states.get(target.alias)
        if not ost:
            ost = OutageState()
            state.outage_states[target.alias] = ost

        if result.success:
            prev, notify_reachable = await ost.record_success()
            if notify_reachable and state.notifications_enabled:
                notify.notify("Pingu", f"{target.alias} is reachable again.", play_sound=False)
            detail = f"{result.latency_ms or 0:.0f}ms" if result.latency_ms is not None else "0"
            display_detail = detail_for_display(True, detail, state.display_mode)
            line = f"{target.alias} - OK {display_detail}"
        else:
            prev, first_failure = await ost.record_failure()
            if state.notifications_enabled:
                if first_failure and state.sound_on_down:
                    notify.notify("Pingu", f"{target.alias} is DOWN: {result.reason}.", play_sound=True)
                else:
                    notify.notify("Pingu", f"{target.alias} is DOWN: {result.reason}.", play_sound=False)
            display_detail = detail_for_display(False, result.reason, state.display_mode)
            line = f"{target.alias} - DOWN {display_detail}"

        # Log every ping result (as required by spec)
        if result.success:
            logger.info(
                "Ping %s (%s): OK %s",
                target.alias,
                target.host,
                f"{result.latency_ms or 0:.0f}ms" if result.latency_ms is not None else "0ms",
            )
        else:
            logger.info(
                "Ping %s (%s): DOWN %s",
                target.alias,
                target.host,
                result.reason,
            )

        if prev == State.UP and not result.success:
            logger.info("UP->DOWN %s: %s", target.alias, result.reason)
        elif prev == State.DOWN and result.success:
            logger.info("DOWN->UP %s", target.alias)

        update = MonitorUpdate(
            alias=target.alias,
            host=target.host,
            line=line,
            success=result.success,
            detail=display_detail,
            display_mode=state.display_mode,
        )
        try:
            state.queue.put_nowait(update)
        except asyncio.QueueFull:
            pass
        if state.thread_safe_queue is not None:
            try:
                state.thread_safe_queue.put(update, block=False)
            except Exception:
                pass


async def schedule_target(target: TargetConfig, state: MonitorState) -> None:
    """Loop: initial jitter, then ping; then wait interval + jitter, repeat while enabled."""
    jitter = random.randint(state.jitter_ms[0], state.jitter_ms[1]) / 1000.0
    await asyncio.sleep(jitter)
    while True:
        current = next((t for t in state.targets if t.alias == target.alias), None)
        if not current or not current.enabled:
            return
        await run_one_target(current, state)
        jitter = random.randint(state.jitter_ms[0], state.jitter_ms[1]) / 1000.0
        await asyncio.sleep(current.interval + jitter)


async def run_monitor(state: MonitorState) -> None:
    """Start a task per enabled target; run until cancelled."""
    state.ensure_structures()
    tasks: list[asyncio.Task] = []
    for t in state.targets:
        if not t.enabled:
            continue
        tasks.append(asyncio.create_task(schedule_target(t, state)))
    if not tasks:
        logger.info("Monitor started with no enabled targets")
        return
    logger.info("Monitor started with %d targets", len(tasks))
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Monitor stopped")
