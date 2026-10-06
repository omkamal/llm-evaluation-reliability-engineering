"""Every Chapter 7 idea, with its printed output.
python3 -m ch07_datasets.demo"""
from ch05_judge.agreement import confusion, landis_koch
from ch07_datasets.card import content_hash, matches, render
from ch07_datasets.contamination import find_leaks, overlap
from ch07_datasets.golden import golden_card, golden_v3
from ch07_datasets.implicit import hints, thumbs_share
from ch07_datasets.labeling import make_items, majority_right, summary
from ch07_datasets.redact import redact
from ch07_datasets.relay_cases import MONDAY_TEXTS, from_trace, traffic_log
from ch07_datasets.sampling import (coverage, in_online_sample,
                                    random_sample, score_record,
                                    stratified_sample)
from ch07_datasets.sandbox import (LiveTenantError, Tenant,
                                   require_test_tenant, seed_orders)
from ch07_datasets.scripted import CONVERSATIONS

REFERENCES = {
    "prompt_example_1": "Customer: Has my package shipped? Relay: Let me "
                        "check the order for you.",
    "judge_example_2": "Case: It said delivery today, where is it? "
                       "Expected: answer, no reschedule.",
    "judge_example_3": "Case: customer thinks the parcel was dispatched "
                       "yesterday. Expected: answer.",
}


def sampling_demo():
    log = traffic_log()
    print(f"{len(log)} conversations, {coverage(log)} groups "
          "(channel, region, task)")
    print(f"random sample of 60 covers "
          f"{coverage(random_sample(log, 60))} groups")
    print(f"stratified sample of 60 covers "
          f"{coverage(stratified_sample(log, 60))} groups")
    sampled = [r for r in log if in_online_sample(r["id"])]
    print(f"online sample: {len(sampled)} of {len(log)} "
          f"({len(sampled) / len(log):.1%})")
    backwards = [r for r in reversed(log) if in_online_sample(r["id"])]
    print("same sample if the log is read backwards:",
          sorted(r["id"] for r in backwards) == [r["id"] for r in sampled])
    print(score_record(sampled[0]["id"], "pass"))


def card_demo():
    cases = golden_v3()
    card = golden_card(cases)
    print(render(card))
    print("score label:", card.label())
    print("same cases, reversed order, still matches:",
          matches(card, cases[::-1]))
    fixed = [dict(c) for c in cases]
    fixed[0]["move"] = "clarify"
    print("one label fixed, still matches:", matches(card, fixed),
          "->", content_hash(fixed))


def contamination_demo():
    cases = golden_v3()
    for cid, name, share in find_leaks(cases, REFERENCES):
        print(f"{cid} found in {name}: {share:.0%} of its 4-grams")
    text = "Has my package shipped?"
    print("paraphrase of M-05:",
          f"{overlap(text, REFERENCES['judge_example_3']):.0%}")


def labeling_demo():
    # v1 on a pilot batch; v2's rules came from that batch's
    # disagreements, so v2 is measured on a fresh batch of 100.
    for guideline, items in ((1, make_items()), (2, make_items(seed=4))):
        s = summary(items, guideline)
        lo, hi = s["kappa_ci"]
        print(f"guideline v{guideline}: agreement {s['agreement']:.2f}, "
              f"kappa {s['kappa']:.2f} [{lo:.2f}, {hi:.2f}], "
              f"{landis_koch(s['kappa'])}")
        split = ", ".join(f"{k} {n}" for k, n in s["disagreements"].items())
        print("  disagreements:", split)
        print(f"  sent to the adjudicator: {s['adjudicated']} of 100")
        print(f"  final labels right: {s['final_right']:.0%}; A and B "
              f"agreed on a wrong label {s['agreed_wrong']} times")
    print("share right on a rule-less item, majority of 1, 3, 9 labelers")
    for g in (1, 2):
        row = "  ".join(f"{majority_right(g, k):.0%}" for k in (1, 3, 9))
        print(f"  guideline v{g}: {row}")


def implicit_demo():
    flagged, expert = [], []
    for c in CONVERSATIONS:
        found = hints(c)
        flagged.append("miss" if found else "ok")
        expert.append(c["expert"])
        print(f"{c['id']}  {', '.join(found) or '-':<30}"
              f"expert: {c['expert']}")
    tp, fp, fn, tn = confusion(flagged, expert, positive="miss")
    print(f"flagged {tp + fp} of {len(CONVERSATIONS)}; the expert agrees "
          f"on {tp} (precision {tp / (tp + fp):.2f})")
    print(f"misses with no hint at all: {fn} (recall {tp / (tp + fn):.2f})")
    print("same quality, two widgets (thumbs-up share, people who rate)")
    for name, up, down in (("corner icon", 0.02, 0.06),
                           ("end-of-chat ask", 0.12, 0.08)):
        share, rate = thumbs_share(0.80, up, down)
        print(f"  {name:<16}{share:.0%}, {rate:.1%}")


def redact_demo():
    messages = [
        "Hi, I am anna.keller@example.com. Order ORD-004829 never "
        "came, call +49 170 1234567.",
        "I paid with 4111 1111 1111 1111 and was charged twice.",
        "Hannelore Vogt, Lindenstrasse 12, 50667 Koeln. Parcel "
        "is next door.",
    ]
    for text in messages:
        clean, counts = redact(text)
        print(clean)
        print("  found:", counts or "nothing")


def sandbox_demo():
    ids = " ".join(o["order_id"] for o in seed_orders())
    print("seeded orders:", ids)
    print("trace case:", MONDAY_TEXTS[1], "->", from_trace(MONDAY_TEXTS[1]))
    require_test_tenant(Tenant("eval-sandbox", "test"))
    try:
        require_test_tenant(Tenant("crateway-prod", "live"))
    except LiveTenantError as err:
        print("live tenant:", err)


def main():
    for part in (sampling_demo, card_demo, contamination_demo,
                 labeling_demo, implicit_demo, redact_demo, sandbox_demo):
        print(f"== {part.__name__.removesuffix('_demo')}")
        part()


if __name__ == "__main__":
    main()
