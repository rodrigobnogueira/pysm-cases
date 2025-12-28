import threading
from typing import Any
from statemachine import StateMachine, State


class DoBehaviorStateMachine(StateMachine):
    """
    A generic StateMachine that automatically handles 'do_behavior' methods.
    
    If a method named `do_<state_id>` exists, it is spawned as a thread 
    when the state is entered and signaled to stop when the state is exited.
    """
    
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
        if state.id in self._running_behaviors:
            thread, stop_event = self._running_behaviors.pop(state.id)
            
            stop_event.set()
            
            thread.join()
