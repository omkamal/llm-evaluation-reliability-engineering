"""Three small flags: a kill switch, a version pin and a tool switch,
plus two dials (approval, service tier). The flag service is a dict.

Every read names a safe default, so a flag store that cannot answer
leaves Relay in the last known, tested state."""
from collections import namedtuple

from ch10_providers.tiers import MODEL_TOOLS
from common.clock import SystemClock

# One bundle = prompt, model and tools released together. Illustrative
# versions; Chapter 16 builds the release bundle properly.
BUNDLES = {
    "2026.09.17": {"prompt": "planner@v42", "model": "a-large-v2",
                   "tools": "v14"},
    "2026.09.08": {"prompt": "planner@v42", "model": "a-large-v2",
                   "tools": "v13"},
    "2026.08.25": {"prompt": "planner@v41", "model": "a-large-v2",
                   "tools": "v12"},
}
CURRENT, LAST_GOOD = "2026.09.08", "2026.08.25"

# What each flag returns when the flag service cannot answer.
SAFE = {"kill_switch": False, "bundle": LAST_GOOD,
        "disabled_tools": (), "approval_for": (), "max_tier": 1}

AgentConfig = namedtuple("AgentConfig", "mode bundle tools approval")


class FlagStore:
    """Flag values and a change log. reachable=False plays a flag
    service that is down: a read returns the last value it saw, and
    only a flag never read falls back to its safe default."""

    def __init__(self, values=None, clock=None):
        self.values = dict(values or {})
        self.clock = clock or SystemClock()
        self.reachable = True
        self.seen = {}                 # the last value we really read
        self.changes = []              # (time, who, flag, value, why)

    def get(self, flag):
        if self.reachable:
            self.seen[flag] = self.values.get(flag, SAFE[flag])
            return self.seen[flag]
        return self.seen.get(flag, SAFE[flag])   # stale beats a default

    def set(self, flag, value, who, why):
        self.changes.append((self.clock.now(), who, flag, value, why))
        self.values[flag] = value


def resolve(flags):
    """What Relay may do right now. The kill switch is read first."""
    bundle = flags.get("bundle")
    if flags.get("kill_switch"):
        # the router hands every case to a person; no tool runs
        return AgentConfig("handoff", bundle, frozenset(), frozenset())
    off = set(flags.get("disabled_tools"))
    tools = frozenset(MODEL_TOOLS[flags.get("max_tier")] - off)
    asked = frozenset(flags.get("approval_for"))
    return AgentConfig("normal", bundle, tools, asked & tools)
