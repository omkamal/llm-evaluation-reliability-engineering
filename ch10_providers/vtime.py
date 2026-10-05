"""Virtual time for asyncio: sleeps cost nothing and run in order."""
import asyncio
import heapq


class VirtualClock:
    """A clock for tests and demos. Time jumps to the next wake-up."""

    def __init__(self):
        self.t = 0.0
        self.waiters = []            # heap of (wake time, order, future)
        self.count = 0

    def now(self):
        return self.t

    async def sleep(self, seconds):
        future = asyncio.get_running_loop().create_future()
        wake = (self.t + seconds, self.count, future)
        heapq.heappush(self.waiters, wake)
        self.count += 1
        await future                 # a cancel lands here

    async def settle(self):
        for _ in range(50):          # let every task run until it blocks
            await asyncio.sleep(0)

    def run(self, main):
        """Run a coroutine to the end, jumping time between wake-ups."""
        async def driver():
            task = asyncio.ensure_future(main)
            while True:
                for _ in range(20):  # runnable tasks get time to finish
                    await self.settle()
                    while self.waiters and self.waiters[0][2].done():
                        heapq.heappop(self.waiters)   # cancelled
                    if task.done() or self.waiters:
                        break
                if task.done():
                    return task.result()
                if not self.waiters:
                    raise RuntimeError("stuck: nothing waits on time")
                when, _, future = heapq.heappop(self.waiters)
                self.t = max(self.t, when)
                future.set_result(None)
        return asyncio.run(driver())


class RealClock:
    """The production default: the same two methods, real time."""

    def now(self):
        return asyncio.get_running_loop().time()

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)
