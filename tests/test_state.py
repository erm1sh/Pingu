"""Unit tests for outage state machine (core.state)."""
import pytest
from core.state import OutageState, State


@pytest.fixture
def state():
    return OutageState()


@pytest.mark.asyncio
async def test_initial_state(state):
    assert state.get_state_sync() == State.UP


@pytest.mark.asyncio
async def test_up_to_down_first_failure(state):
    prev, is_first = await state.record_failure()
    assert prev == State.UP
    assert is_first is True
    assert state.get_state_sync() == State.DOWN


@pytest.mark.asyncio
async def test_down_subsequent_failures_silent(state):
    await state.record_failure()
    prev2, is_first2 = await state.record_failure()
    assert prev2 == State.DOWN
    assert is_first2 is False
    prev3, is_first3 = await state.record_failure()
    assert prev3 == State.DOWN
    assert is_first3 is False


@pytest.mark.asyncio
async def test_down_to_up_reachable_again(state):
    await state.record_failure()
    assert state.get_state_sync() == State.DOWN
    prev, notify_reachable = await state.record_success()
    assert prev == State.DOWN
    assert notify_reachable is True
    assert state.get_state_sync() == State.UP


@pytest.mark.asyncio
async def test_up_success_no_reachable_notification(state):
    prev, notify_reachable = await state.record_success()
    assert prev == State.UP
    assert notify_reachable is False


@pytest.mark.asyncio
async def test_full_cycle(state):
    await state.record_failure()
    await state.record_failure()
    prev, notify_up = await state.record_success()
    assert prev == State.DOWN and notify_up is True
    prev2, first_down = await state.record_failure()
    assert prev2 == State.UP and first_down is True
