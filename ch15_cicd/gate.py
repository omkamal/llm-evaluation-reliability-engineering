"""The eval gate: is this change safe to merge?   python -m ch15_cicd.gate

Reads main's scores and the change's scores, case by case, and decides
PASS, WARN or BLOCK with the evidence. Exit code 0 for PASS and WARN,
1 for BLOCK, 2 when the run cannot be judged: the two runs are not
comparable, or the run is INCOMPLETE (too few cases, a never-fail case
of main's not run, or too many trials that errored).

Each side is {case id: {"slice": ..., "never_fail": ..., "trials": [...]}}
with one 0 or 1 per trial, or None for a trial that errored (a timeout,
a 429). A case's score is its pass rate over the trials that ran.
"""
import argparse
import json
import sys
from dataclasses import dataclass

from ch04_numbers.stats import mean, paired_bootstrap, wilson_interval

ORDER = {"PASS": 0, "SKIP": 1, "WARN": 1, "BLOCK": 2, "INCOMPLETE": 3}
# A skipped rule was not judged, so it ranks with WARN, never with PASS.
MAX_ERRORED = 0.05     # a larger share of errored trials: INCOMPLETE


@dataclass(frozen=True)
class Rule:
    slice: str                # "all", or the name of a slice
    margin: float             # accept a fall of at most this much
    on_unsure: str = "warn"   # "warn" or "block" when the call is open


def verdict(lo, hi, rule):
    """The non-inferiority test: one interval, one margin.

    Rounded to six places so a bound sitting exactly on the margin does
    not flip on float noise."""
    lo, hi = round(lo, 6), round(hi, 6)
    if lo >= -rule.margin:
        return "PASS"       # shown: no worse than main by the margin
    if hi < -rule.margin:
        return "BLOCK"      # shown: worse than the margin allows
    return rule.on_unsure.upper()       # not shown either way


def overall(verdicts):
    """BLOCK if any rule blocks; PASS only if every rule passed. A rule
    that was skipped was not judged: it can make a WARN, never a PASS."""
    if "BLOCK" in verdicts:
        return "BLOCK"
    return "PASS" if set(verdicts) == {"PASS"} else "WARN"


def ran(case):
    """The trials that produced an answer (errored ones are None)."""
    return [t for t in case["trials"] if t is not None]


def rates(side, ids):
    return [mean(ran(side[i])) for i in ids]


def interval(a, b, resamples=10_000, seed=0):
    """Chapter 4's paired bootstrap, kept honest when few cases moved.

    The bootstrap only reshuffles what it saw: twenty cases that did not
    move give [0, 0], and a PASS. But n cases cannot rule out a share of
    regressions that this run happened not to show: up to the Wilson
    limit for 0 of n (16% at n = 20). So the lower end, the one that
    decides a PASS, never sits closer to the change than that."""
    delta, (lo, hi) = paired_bootstrap(a, b, resamples=resamples,
                                       seed=seed)
    unseen = wilson_interval(0, len(a))[1]
    return delta, (min(lo, delta - unseen), hi)


def check_rule(rule, base, new, min_cases, resamples, seed):
    ids = sorted(i for i in new if rule.slice in ("all", new[i]["slice"]))
    if len(ids) < min_cases:
        return {"slice": rule.slice, "n": len(ids), "verdict": "SKIP",
                "note": f"only {len(ids)} cases, need {min_cases}"}
    a, b = rates(base, ids), rates(new, ids)
    delta, (lo, hi) = interval(a, b, resamples=resamples, seed=seed)
    return {"slice": rule.slice, "n": len(ids), "base": mean(a),
            "new": mean(b), "delta": delta, "lo": lo, "hi": hi,
            "margin": rule.margin, "verdict": verdict(lo, hi, rule),
            "note": ""}


def floor_bound(trials, confidence=0.95):
    """Zero failures in n trials is not a failure rate of zero. It says
    the rate is below this (about 3 / n at 95%)."""
    return 1 - (1 - confidence) ** (1 / trials)


def check_floor(new):
    """Zero tolerance: one failed trial of a never-fail case blocks."""
    cases = {i: c for i, c in new.items() if c["never_fail"]}
    failed = {i: c["trials"].count(0) for i, c in cases.items()
              if 0 in c["trials"]}
    trials = sum(len(ran(c)) for c in cases.values())
    return {"cases": len(cases), "trials": trials, "failed": failed,
            "verdict": "BLOCK" if failed else "PASS"}


def incomplete(base, new, min_cases):
    """Why this run cannot be judged, or [] when it can. A run with no
    cases, or without main's never-fail cases, has tested nothing."""
    why = []
    if len(new) < min_cases:
        why.append(f"only {len(new)} cases in the run, need {min_cases}")
    gone = sorted(i for i, c in base.items() if c["never_fail"]
                  and not (i in new and ran(new[i])))
    if gone:
        why.append("never-fail cases not run: " + ", ".join(gone))
    trials = [t for c in new.values() for t in c["trials"]]
    if trials.count(None) > MAX_ERRORED * len(trials):
        why.append(f"{trials.count(None)} of {len(trials)} trials errored")
    return why


def decide(base, new, rules, *, min_cases=20, resamples=10_000, seed=0):
    missing = [i for i in sorted(new) if i not in base]
    if missing:
        raise ValueError(f"main has no score for {missing[:3]}")
    why = incomplete(base, new, min_cases)
    if why:
        return {"verdict": "INCOMPLETE", "rows": [], "floor": None,
                "worse": [], "because": why}
    new = {i: c for i, c in new.items() if ran(c)}
    rows = [check_rule(r, base, new, min_cases, resamples, seed)
            for r in rules]
    floor = check_floor(new)
    final = overall([r["verdict"] for r in rows] + [floor["verdict"]])
    score = lambda side, i: mean(ran(side[i]))
    drops = sorted(new, key=lambda i: score(new, i) - score(base, i))
    worse = [i for i in drops[:3] if score(new, i) < score(base, i)]
    because = [r["slice"] for r in rows
               if ORDER[r["verdict"]] == ORDER[final]]
    if ORDER[floor["verdict"]] == ORDER[final]:
        because.append("never-fail")
    return {"verdict": final, "rows": rows, "floor": floor,
            "worse": worse, "because": because}


FIELDS = ("prompt", "model", "tools", "index", "judge")


def changed_fields(old, new):
    """What differs between the two runs' records, in words."""
    return [f"{k} {old[k]} to {new[k]}" for k in FIELDS if old[k] != new[k]]


def render(result, base, new, changed=()):
    """The decision, with its evidence, as Markdown for a person."""
    lines = [f"### Eval gate: {result['verdict']}", ""]
    if result["verdict"] == "INCOMPLETE":
        return lines + [f"- {why}" for why in result["because"]]
    lines += ["Changed since main: " + (", ".join(changed) or "nothing"),
              "",
              "| slice (cases) | main to PR | change | 95% interval | verdict |",
              "|" + "|".join("-" * n for n in (16, 12, 8, 18, 9)) + "|"]
    for r in result["rows"]:
        name = f"{r['slice']} ({r['n']})"
        if r["verdict"] == "SKIP":
            lines.append(f"| {name} | | | {r['note']} | SKIP |")
            continue
        lines.append(
            f"| {name} | {r['base']:.2f} to {r['new']:.2f} "
            f"| {r['delta']:+.3f} "
            f"| [{r['lo']:+.3f}, {r['hi']:+.3f}] | {r['verdict']} |")
    f = result["floor"]
    lines += ["", f"Never-fail: {f['cases']} cases, {f['trials']} trials, "
              f"{sum(f['failed'].values())} failed: {f['verdict']}"]
    for i, k in sorted(f["failed"].items())[:3]:
        lines.append(f"  - {i} failed {k} of {len(new[i]['trials'])} trials")
    for i in result["worse"]:
        was, now = mean(ran(base[i])), mean(ran(new[i]))
        lines.append(f"worse: {i} {was:.2f} to {now:.2f}")
    if result["verdict"] != "PASS":
        lines.append("decided by: " + ", ".join(result["because"]))
    return lines


def load(path):
    with open(path) as handle:
        return json.load(handle)


def comparable(base, new):
    """Scores from different eval sets or judges must not be compared."""
    return [k for k in ("eval_set", "judge")
            if base["record"][k] != new["record"][k]]


EXIT = {"PASS": 0, "WARN": 0, "BLOCK": 1, "INCOMPLETE": 2}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gate")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--thresholds", required=True)
    ap.add_argument("--resamples", type=int, default=10_000)
    args = ap.parse_args(argv)
    base, new = load(args.baseline), load(args.results)
    cfg = load(args.thresholds)
    odd = comparable(base, new)
    if odd:
        print(f"NOT COMPARABLE: {', '.join(odd)} differ; re-run main")
        return 2
    rules = [Rule(**r) for r in cfg["rules"]]
    result = decide(base["cases"], new["cases"], rules,
                    min_cases=cfg["min_cases"], resamples=args.resamples)
    changed = changed_fields(base["record"], new["record"])
    print("\n".join(render(result, base["cases"], new["cases"], changed)))
    return EXIT[result["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
