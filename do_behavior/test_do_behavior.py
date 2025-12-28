import threading
import time
import pytest

from statemachine import State
from do_behavior.do_behavior import DoBehaviorStateMachine


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
            if stop_event.wait(timeout=0.1):
                break

    def do_idle(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            self.idle_counter += 1
            if stop_event.wait(timeout=0.1):
                break


def test_thread_starts_on_state_entry() -> None:
    sm = SimpleMachine()
    
    time.sleep(0.3)
    
    assert sm.idle_counter > 0
    assert sm.work_counter == 0


def test_thread_stops_on_state_exit() -> None:
    sm = SimpleMachine()
    
    initial_idle_count = sm.idle_counter
    time.sleep(0.2)
    idle_count_before_transition = sm.idle_counter
    
    assert idle_count_before_transition > initial_idle_count
    
    sm.start()
    time.sleep(0.1)
    
    idle_count_after_transition = sm.idle_counter
    assert idle_count_after_transition == idle_count_before_transition


def test_new_thread_starts_after_transition() -> None:
    sm = SimpleMachine()
    
    sm.start()
    time.sleep(0.3)
    
    assert sm.work_counter > 0
    assert sm.idle_counter > 0


def test_thread_cleanup_on_multiple_transitions() -> None:
    sm = SimpleMachine()
    
    time.sleep(0.2)
    sm.start()
    time.sleep(0.2)
    
    assert len(sm._running_behaviors) == 1
    assert 'working' in sm._running_behaviors
    
    sm.finish()
    
    assert len(sm._running_behaviors) == 0


def test_state_without_do_method() -> None:
    sm = SimpleMachine()
    
    sm.start()
    sm.finish()
    
    assert sm.current_state == sm.done
    assert len(sm._running_behaviors) == 0


def test_multiple_cycles() -> None:
    sm = SimpleMachine()
    
    for _ in range(3):
        sm.start()
        time.sleep(0.15)
        work_count = sm.work_counter
        assert work_count > 0
        
        sm.finish()
        time.sleep(0.05)
        
        assert sm.work_counter == work_count
        
        sm.reset()
        time.sleep(0.15)


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


def test_thread_execution_order() -> None:
    sm = CountingMachine()
    
    time.sleep(0.05)
    assert "a_started" in sm.executions
    
    sm.switch()
    time.sleep(0.05)
    
    assert "a_stopped" in sm.executions
    assert "b_started" in sm.executions
    
    sm.switch()
    time.sleep(0.05)
    
    assert "b_stopped" in sm.executions
    assert sm.executions.count("a_started") == 2
