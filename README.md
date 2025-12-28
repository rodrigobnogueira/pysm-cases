# Python State Machine Cases

A collection of patterns and examples for [python-statemachine](https://github.com/fgmacedo/python-statemachine).

## Do-Behavior Pattern

Implementation of the do-behavior pattern from [Issue #521](https://github.com/fgmacedo/python-statemachine/issues/521).

### Features

- Automatic background thread management for state behaviors
- Clean thread lifecycle (start on entry, stop on exit)
- Generic base class using `on_enter_state` and `on_exit_state` callbacks
- Thread-safe shutdown using `threading.Event`

### Usage

```python
from statemachine import State
from do_behavior import DoBehaviorStateMachine
import threading

class TrafficLight(DoBehaviorStateMachine):
    green = State(initial=True)
    yellow = State()
    red = State()

    cycle = green.to(yellow) | yellow.to(red) | red.to(green)

    def do_green(self, stop_event: threading.Event) -> None:
        print("Green light active...")
        while not stop_event.is_set():
            print("  Safe to go!")
            if stop_event.wait(timeout=1):
                break
```

### Running the Example

```bash
python -m do_behavior.traffic_light_example
```

### Running Tests

```bash
pytest do_behavior/test_do_behavior.py -v
```

### Installation

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install python-statemachine pytest
```

## Important Notes

- Initialize instance attributes **before** calling `super().__init__()`
- The base class initializes `_running_behaviors` before triggering state activation
- Use `stop_event.wait(timeout=...)` instead of `time.sleep()` for responsive shutdown
