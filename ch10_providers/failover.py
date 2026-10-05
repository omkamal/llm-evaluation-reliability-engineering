"""Failover without flooding: hysteresis, capacity, a warm backup."""


class Hysteresis:
    """Leave the primary at 20% errors; return only when calm, slowly."""

    def __init__(self, clock, leave=20.0, back=5.0, hold=300.0,
                 step=240.0, ramp=(0.1, 0.5, 1.0)):
        self.clock = clock
        self.leave, self.back, self.hold = leave, back, hold
        self.step, self.ramp = step, ramp
        self.share = 1.0           # share of traffic sent to the primary
        self.calm_since = None     # when errors last fell to `back`
        self.rung = None           # position on the ramp, if climbing
        self.rung_at = 0.0
        self.log = []              # (time, share) at every change

    def _set(self, share):
        if share != self.share:
            self.share = share
            self.log.append((self.clock.now(), share))

    def observe(self, error_pct):
        now = self.clock.now()
        if error_pct >= self.leave:            # leaving is immediate
            self._set(0.0)
            self.calm_since = self.rung = None
        elif self.share == 0.0:                # away: wait for calm
            if error_pct > self.back:
                self.calm_since = None         # the calm must be unbroken
            elif self.calm_since is None:
                self.calm_since = now
            elif now - self.calm_since >= self.hold:
                self.rung, self.rung_at = 0, now
                self._set(self.ramp[0])
        elif self.rung is not None:            # climbing back
            if error_pct <= self.back and now - self.rung_at >= self.step:
                self.rung += 1
                self.rung_at = now
                self._set(self.ramp[self.rung])
                if self.rung == len(self.ramp) - 1:
                    self.rung = None
        return self.share


class SingleThreshold:
    """The naive rule: one line, crossed in both directions."""

    def __init__(self, clock, line=12.5):
        self.clock, self.line = clock, line
        self.share = 1.0
        self.log = []

    def observe(self, error_pct):
        share = 0.0 if error_pct >= self.line else 1.0
        if share != self.share:
            self.share = share
            self.log.append((self.clock.now(), share))
        return self.share


def plan_shift(demand, free_slots,
               order=("eu_chat", "chat", "background")):
    """Fill the backup's free slots in priority order; the rest waits."""
    placed = {}
    for lane in order:
        take = min(demand.get(lane, 0), free_slots)
        placed[lane] = take
        free_slots -= take
    overflow = {lane: demand.get(lane, 0) - placed[lane]
                for lane in order}
    return placed, overflow


def with_warmup(ranked, rng, warm_share=0.02):
    """Send a small, steady share of real traffic to the runner-up."""
    if len(ranked) > 1 and rng.random() < warm_share:
        return ranked[1]
    return ranked[0]
