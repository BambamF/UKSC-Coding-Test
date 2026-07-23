from collections import deque
import threading
import time

class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.wait_calls = 0
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.popleft()

            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                self.wait_calls  += 1
            else:
                sleep_time = 0

        if sleep_time > 0:
            time.sleep(sleep_time)
        self.calls.append(time.monotonic())