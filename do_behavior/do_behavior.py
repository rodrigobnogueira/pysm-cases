import threading
import warnings
from typing import Any
from statemachine import StateMachine, State


DEFAULT_JOIN_TIMEOUT = 2.0
"""Seconds to wait for a behavior thread to stop before giving up on it."""


class DoBehaviorStateMachine(StateMachine):
    """
    A generic StateMachine that automatically handles 'do_behavior' methods.

    If a method named `do_<state_id>` exists, it is spawned as a thread
    when the state is entered and signaled to stop when the state is exited.

    A behavior is expected to cooperate with the `stop_event` it receives.
    On exit the machine waits at most `join_timeout` seconds for the thread
    to finish; if the behavior ignores its `stop_event`, the transition still
    completes and a `RuntimeWarning` names the offending state. Subclasses can
    override `join_timeout` to tune that budget.
    """

    join_timeout: float = DEFAULT_JOIN_TIMEOUT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._running_behaviors: dict[str, tuple[threading.Thread, threading.Event]] = {}
        super().__init__(*args, **kwargs)

    def on_enter_state(self, state: State) -> None:
        method_name = f"do_{state.id}"

        if hasattr(self, method_name):
            stop_event = threading.Event()
            method = getattr(self, method_name)

            thread = threading.Thread(
                target=method,
                args=(stop_event,),
                name=f"thread_do_{state.id}",
                daemon=True
            )
            thread.start()

            self._running_behaviors[state.id] = (thread, stop_event)

    def on_exit_state(self, state: State) -> None:
        behavior = self._running_behaviors.pop(state.id, None)
        if behavior is None:
            return

        thread, stop_event = behavior

        stop_event.set()

        # Bounded join: a behavior that ignores its stop_event must not be able
        # to block the transition (and with it the caller) forever.
        thread.join(timeout=self.join_timeout)

        if thread.is_alive():
            warnings.warn(
                f"Behavior 'do_{state.id}' did not stop within "
                f"{self.join_timeout}s of leaving state '{state.id}'; it "
                f"appears to ignore its stop_event. The transition completed "
                f"and the thread was left running as a daemon.",
                RuntimeWarning,
            )
