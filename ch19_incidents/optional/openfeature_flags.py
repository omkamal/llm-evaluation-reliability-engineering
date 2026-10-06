"""The same three flags through OpenFeature (optional, not run by CI).

Run once on 5 October 2026 in a throwaway virtualenv with
openfeature-sdk 0.10.0 (Python 3.12.3). The main chapter code does not
import this file."""
from openfeature import api
from openfeature.provider.in_memory_provider import (InMemoryFlag,
                                                     InMemoryProvider)

LAST_GOOD = "2026.08.25"


def flag(value):
    return InMemoryFlag("on", {"on": value})


def set_flags(kill, bundle, disabled):
    api.set_provider(InMemoryProvider({
        "relay-kill-switch": flag(kill),
        "relay-bundle": flag(bundle),
        "relay-disabled-tools": flag({"tools": disabled}),
    }))


def what_runs(client):
    """Every read names its own default, used if the service cannot
    answer or does not hold the flag: the safe side, so the kill switch
    defaults to ON and the bundle to the last good one."""
    if client.get_boolean_value("relay-kill-switch", True):
        return "handoff", LAST_GOOD, []
    bundle = client.get_string_value("relay-bundle", LAST_GOOD)
    off = client.get_object_value("relay-disabled-tools", {"tools": []})
    return "normal", bundle, off["tools"]


if __name__ == "__main__":
    client = api.get_client("relay")
    for name, args in (
            ("normal", (False, "2026.09.08", [])),
            ("credits off", (False, "2026.09.08", ["issue_refund"])),
            ("pinned", (False, LAST_GOOD, ["issue_refund"])),
            ("killed", (True, LAST_GOOD, ["issue_refund"]))):
        set_flags(*args)               # no redeploy: a flag flip
        print(f"{name:<12} {what_runs(client)}")
    api.shutdown()
    api.set_provider(InMemoryProvider({}))     # a service with no flags
    print(f"{'unknown':<12} {what_runs(api.get_client('relay'))}")
