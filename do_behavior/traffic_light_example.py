import threading
import time
from statemachine import State

from .do_behavior import DoBehaviorStateMachine


class TrafficLight(DoBehaviorStateMachine):
    green = State(initial=True)
    yellow = State()
    red = State()

    cycle = (
        green.to(yellow) |
        yellow.to(red) |
        red.to(green)
    )

    def do_green(self, stop_event: threading.Event) -> None:
        print("Green light active...")
        while not stop_event.is_set():
            print("  Safe to go!")
            if stop_event.wait(timeout=1):
                break

    def do_yellow(self, stop_event: threading.Event) -> None:
        print("Yellow light active!")
        stop_event.wait(timeout=0.5)

    def do_red(self, stop_event: threading.Event) -> None:
        print("Red light! Stop!")
        while not stop_event.is_set():
            print("  Waiting...")
            if stop_event.wait(timeout=1):
                break


if __name__ == "__main__":
    sm = TrafficLight()

    time.sleep(2)
    sm.cycle()

    time.sleep(1)
    sm.cycle()

    time.sleep(2)
    sm.cycle()

    time.sleep(2)
    print("Done!")
