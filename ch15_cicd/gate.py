"""The eval gate: is this change safe to merge?   python -m ch15_cicd.gate

Reads main's scores and the change's scores, case by case, and decides
PASS, WARN or BLOCK with the evidence. Exit code 0 for PASS and WARN,
1 for BLOCK, 2 when the two runs cannot be compared.

Each side is {case id: {"slice": ..., "never_fail": ..., "trials": [...]}}
with one 0 or 1 per trial. A case's score is its pass rate over trials.
"""
import argparse
import json
import sys
from dataclasses import dataclass

from ch04_numbers.stats import mean, paired_bootstrap

ORDER = {"PASS": 0, "SKIP": 0, "WARN": 1, "BLOCK": 2}


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


def rates(side, ids):
    return [mean(side[i]["trials"]) for i in ids]


def check_rule(rule, base, new, min_cases, resamples, seed):
    ids = sorted(i for i in new if rule.slice in ("all", new[i]["slice"]))
    if len(ids) < min_cases:
        return {"slice": rule.slice, "n": len(ids), "verdict": "SKIP",
                "note": f"only {len(ids)} cases, need {min_cases}"}
    a, b = rates(base, ids), rates(new, ids)
    delta, (lo, hi) = paired_bootstrap(a, b, resamples=resamples,
                                       seed=seed)
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
    trials = sum(len(c["trials"]) for c in cases.values())
    return {"cases": len(cases), "trials": trials, "failed": failed,
            "verdict": "BLOCK" if failed else "PASS"}


def decide(base, new, rules, *, min_cases=20, resamples=10_000, seed=0):
    ids = sorted(new)
    missing = [i for i in ids if i not in base]
    if missing:
        raise ValueError(f"main has no score for {missing[:3]}")
    rows = [check_rule(r, base, new, min_cases, resamples, seed)
            for r in rules]
    floor = check_floor(new)
    worst = max(rows + [floor], key=lambda r: ORDER[r["verdict"]])
    drops = sorted(ids, key=lambda i: mean(new[i]["trials"])
                   - mean(base[i]["trials"]))
    worse = [i for i in drops[:3] if mean(new[i]["trials"])
             < mean(base[i]["trials"])]
    because = [r["slice"] for r in rows if r["verdict"] == worst["verdict"]]
    if floor["verdict"] == worst["verdict"]:
        because.append("never-fail")
    return {"verdict": worst["verdict"], "rows": rows, "floor": floor,
            "worse": worse, "because": because}


FIELDS = ("prompt", "model", "tools", "index", "judge")


def changed_fields(old, new):
    """What differs between the two runs' records, in words."""
    return [f"{k} {old[k]} to {new[k]}" for k in FIELDS if old[k] != new[k]]


def render(result, base, new, changed=()):
    """The decision, with its evidence, as Markdown for a person."""
    lines = [f"### Eval gate: {result['verdict']}", "",
             "Changed since main: " + (", ".join(changed) or "nothing"),
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
        was, now = mean(base[i]["trials"]), mean(new[i]["trials"])
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
    return 1 if result["verdict"] == "BLOCK" else 0


if __name__ == "__main__":
    sys.exit(main())
