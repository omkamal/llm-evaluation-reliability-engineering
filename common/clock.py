"""Clocks. Production code uses SystemClock; tests and demos use FakeClock so time costs nothing."""
import time


class SystemClock:
    def now(self):
        return time.monotonic()      # never jumps backwards, ideal for deadlines

    def sleep(self, seconds):
        time.sleep(seconds)


class FakeClock:
    def __init__(self, start=0.0):
        self.t = start

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds
