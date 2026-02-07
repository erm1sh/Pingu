"""
Outage state machine per target (race-free).
States: UP, DOWN.
Transitions: UP -> DOWN on first failure; DOWN -> UP on first success after outage.
Used to decide: first DOWN = notification WITH sound; subsequent DOWN = silent; DOWN -> UP = "reachable again" once.
"""
from enum import Enum
from typing import Optional
import asyncio


class State(Enum):
    UP = "up"
    DOWN = "down"


class OutageState:
    """Per-target state machine. All mutations from monitor loop only (single writer)."""

    def __init__(self) -> None:
        self._state = State.UP
        self._lock = asyncio.Lock()

    @property
    def state(self) -> State:
        return self._state

    async def record_success(self) -> tuple[State, bool]:
        """
        Record a successful ping. Returns (previous_state, should_notify_reachable_again).
        """
        async with self._lock:
            prev = self._state
            if prev == State.DOWN:
                self._state = State.UP
                return (State.DOWN, True)
            self._state = State.UP
            return (prev, False)

    async def record_failure(self) -> tuple[State, bool]:
        """
        Record a failed ping. Returns (previous_state, is_first_failure_of_outage).
        First failure: show notification WITH sound.
        """
        async with self._lock:
            prev = self._state
            if prev == State.UP:
                self._state = State.DOWN
                return (State.UP, True)
            # Already DOWN
            self._state = State.DOWN
            return (State.DOWN, False)

    def get_state_sync(self) -> State:
        """For UI read-only; no lock to avoid blocking."""
        return self._state
