"""What the model actually saw: a trim that records what it dropped.

The rule is Chapter 1's: keep the system prompt and the newest turns,
drop the oldest first. Token counts are scripted so that the numbers in
the trace match the scenario (our toy tokenizer cannot make 31,800)."""
from dataclasses import dataclass

ADDRESS = "14 Elm Street, Apt 3"
MUST_KEEP = {"delivery_address": ADDRESS, "order_id": "ORD-004829"}


@dataclass(frozen=True)
class Turn:
    role: str
    text: str
    tokens: int


def long_session():
    """26 turns, 31,800 tokens; the address is the second turn."""
    turns = [Turn("system", "You are Relay, Crateway's assistant.", 600),
             Turn("customer", f"My address is {ADDRESS}.", 60)]
    turns += [Turn("mixed", f"(earlier turn {i})", 1_202)
              for i in range(1, 21)]
    turns += [Turn("tool", "(lookup_order result, ORD-004829)", 2_600),
              Turn("tool", "(lookup_policy result, rescheduling)", 2_500),
              Turn("tool", "(delivery windows result)", 1_900),
              Turn("customer", "Please move it to Thursday morning.", 100)]
    return turns


def trim_oldest_first(turns, budget):
    """(kept, dropped); the system prompt always stays."""
    system, rest = turns[0], turns[1:]
    kept, used = [], system.tokens
    for turn in reversed(rest):                    # newest first
        if used + turn.tokens > budget:
            break
        kept.insert(0, turn)
        used += turn.tokens
    return [system] + kept, rest[: len(rest) - len(kept)]


def summarize(dropped):
    """A lossy stand-in for the Summarizer: keeps the gist, not the
    address."""
    return Turn("summary", "Customer wants a delivery moved; order "
                "ORD-004829.", 200)


def careful_summarize(dropped):
    """The fix: pin every must-keep value found in what is dropped."""
    pinned = [v for v in MUST_KEEP.values()
              if any(v in t.text for t in dropped)]
    return Turn("summary", "Customer wants a delivery moved; order "
                f"ORD-004829. Pinned: {'; '.join(pinned)}.", 200)


def fields_lost(required, turns):
    """Names of required fields whose value no turn still contains."""
    seen = " ".join(t.text for t in turns)
    return [name for name, value in required.items() if value not in seen]


def traced_trim(tracer, turns, budget, summarizer=summarize):
    """Trim inside a state-transition span; return the new context."""
    with tracer.span("context_trim", "state") as sp:
        kept, dropped = trim_oldest_first(turns, budget - 200)
        new = [kept[0], summarizer(dropped)] + kept[1:]
        lost = fields_lost(MUST_KEEP, new)
        before = sum(t.tokens for t in turns)
        sp.set({"relay.context.tokens_before": before,
                "relay.context.tokens_after": sum(t.tokens for t in new),
                "relay.context.turns_dropped": len(dropped),
                "relay.context.fields_lost": lost})
        for name in lost:
            sp.event("field_dropped", field=name)
        return new
