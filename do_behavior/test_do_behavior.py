import threading
import time
import warnings
from collections.abc import Callable

import pytest
from statemachine import State

from do_behavior.do_behavior import DoBehaviorStateMachine

TICK = 0.01
"""How often the cooperative test behaviors below wake up."""

RUNAWAY_LIMIT = 5.0
"""Hard stop for the deliberately non-cooperative behavior, so a failing test
cannot leave a thread spinning for the rest of the session."""


class SimpleMachine(DoBehaviorStateMachine):
    idle = State(initial=True)
    working = State()
    done = State()

    start = idle.to(working)
    finish = working.to(done)
    reset = done.to(idle)

    def __init__(self) -> None:
        self.work_counter = 0
        self.idle_counter = 0
        super().__init__()

    def do_working(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.work_counter += 1
            if stop_event.wait(timeout=TICK):
                break

    def do_idle(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.idle_counter += 1
            if stop_event.wait(timeout=TICK):
                break


def test_thread_starts_on_state_entry(wait_until: Callable[..., object]) -> None:
    sm = SimpleMachine()

    wait_until(lambda: sm.idle_counter > 0)

    assert sm.work_counter == 0


def test_thread_stops_on_state_exit(wait_until: Callable[..., object]) -> None:
    sm = SimpleMachine()

    wait_until(lambda: sm.idle_counter > 0)
    idle_thread, _ = sm._running_behaviors["idle"]

    sm.start()

    # `on_exit_state` joins the behavior thread, so once the transition has
    # returned the idle counter can no longer change and comparing it for
    # exact equality is sound -- no timing margin involved.
    assert not idle_thread.is_alive()
    frozen_idle_counter = sm.idle_counter

    # Let real time pass, proving the counter is frozen and not merely read
    # back too quickly.
    wait_until(lambda: sm.work_counter > 0)

    assert sm.idle_counter == frozen_idle_counter


def test_new_thread_starts_after_transition(
    wait_until: Callable[..., object],
) -> None:
    sm = SimpleMachine()

    wait_until(lambda: sm.idle_counter > 0)
    sm.start()
    wait_until(lambda: sm.work_counter > 0)


def test_thread_cleanup_on_multiple_transitions(
    wait_until: Callable[..., object],
) -> None:
    sm = SimpleMachine()

    wait_until(lambda: sm.idle_counter > 0)
    assert list(sm._running_behaviors) == ["idle"]

    sm.start()
    assert list(sm._running_behaviors) == ["working"]

    sm.finish()
    assert sm._running_behaviors == {}


def test_state_without_do_method() -> None:
    sm = SimpleMachine()

    sm.start()
    sm.finish()

    assert sm.current_state_value == "done"
    assert sm._running_behaviors == {}


def test_multiple_cycles(wait_until: Callable[..., object]) -> None:
    sm = SimpleMachine()

    for _ in range(3):
        work_baseline = sm.work_counter

        sm.start()
        wait_until(lambda: sm.work_counter > work_baseline)

        # The working thread is joined by the transition, so its counter is
        # frozen from here on; the idle thread was joined by `start()`, so
        # its counter is frozen too until `reset()` starts a new one.
        sm.finish()
        frozen_work_counter = sm.work_counter
        idle_baseline = sm.idle_counter
        assert frozen_work_counter > work_baseline

        sm.reset()
        wait_until(lambda: sm.idle_counter > idle_baseline)

        assert sm.work_counter == frozen_work_counter


def test_cooperative_behavior_joins_without_warning(
    wait_until: Callable[..., object],
) -> None:
    sm = SimpleMachine()

    wait_until(lambda: sm.idle_counter > 0)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        sm.start()

    assert sm.current_state_value == "working"


class CountingMachine(DoBehaviorStateMachine):
    state_a = State(initial=True)
    state_b = State()

    switch = state_a.to(state_b) | state_b.to(state_a)

    def __init__(self) -> None:
        self.executions: list[str] = []
        super().__init__()

    def do_state_a(self, stop_event: threading.Event) -> None:
        self.executions.append("a_started")
        stop_event.wait()
        self.executions.append("a_stopped")

    def do_state_b(self, stop_event: threading.Event) -> None:
        self.executions.append("b_started")
        stop_event.wait()
        self.executions.append("b_stopped")


def test_thread_execution_order(wait_until: Callable[..., object]) -> None:
    sm = CountingMachine()

    wait_until(lambda: "a_started" in sm.executions)

    sm.switch()
    # The exit callback joined the `state_a` thread before entering
    # `state_b`, so "a_stopped" is already recorded.
    assert "a_stopped" in sm.executions

    wait_until(lambda: "b_started" in sm.executions)

    sm.switch()
    assert "b_stopped" in sm.executions

    wait_until(lambda: sm.executions.count("a_started") == 2)
    assert sm.executions == [
        "a_started",
        "a_stopped",
        "b_started",
        "b_stopped",
        "a_started",
    ]


class StubbornMachine(DoBehaviorStateMachine):
    """A machine whose behavior deliberately ignores its `stop_event`."""

    join_timeout = 0.05

    busy = State(initial=True)
    parked = State()

    park = busy.to(parked)
    resume = parked.to(busy)

    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        super().__init__()

    def do_busy(self, stop_event: threading.Event) -> None:
        self.started.set()
        # Never consults `stop_event` -- this is the misbehaving case.
        self.release.wait(timeout=RUNAWAY_LIMIT)


def test_non_cooperative_behavior_does_not_block_transition(
    wait_until: Callable[..., object],
) -> None:
    sm = StubbornMachine()

    wait_until(sm.started.is_set)
    thread, _ = sm._running_behaviors["busy"]

    started_at = time.monotonic()
    with pytest.warns(RuntimeWarning, match="do_busy"):
        sm.park()
    elapsed = time.monotonic() - started_at

    # The transition returns after the bounded join instead of waiting for a
    # behavior that will never observe its stop_event.
    assert elapsed < RUNAWAY_LIMIT / 2
    assert sm.current_state_value == "parked"
    assert sm._running_behaviors == {}
    assert thread.is_alive()

    sm.release.set()
    wait_until(lambda: not thread.is_alive())
