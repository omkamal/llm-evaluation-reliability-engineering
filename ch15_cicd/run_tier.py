"""Run one tier of evals and write the scores.

python -m ch15_cicd.run_tier --sample 50                 (pull request)
python -m ch15_cicd.run_tier --trials 3 --check-baseline (nightly)
python -m ch15_cicd.run_tier --trials 5 --safety         (release)
python -m ch15_cicd.run_tier --update-baseline           (main, refresh)
"""
import argparse
import json
from pathlib import Path

from ch07_datasets.sandbox import Tenant, require_test_tenant
from ch15_cicd import gate, record, repo, suite
from ch15_cicd.tiers import TIERS, Tier, pick_sample

BASELINE = repo.ROOT / "evals" / "baseline" / "main.json"


def run_tier(tier, root=repo.ROOT, seed=0):
    """Run `tier` (a Tier, or the name of one) against the repository."""
    tier = TIERS[tier] if isinstance(tier, str) else tier
    config = json.loads((root / "config/relay.json").read_text())
    require_test_tenant(Tenant(**config["tenant"]))   # never a live one
    prompt_text = (root / "prompts/system.md").read_text()
    build = repo.build_of(prompt_text)
    meta = suite.case_meta()
    never = {c["id"] for c in meta if c["never_fail"]}
    ids = pick_sample([c["id"] for c in meta], never, tier.sample, seed)
    rng = suite.rng_for(seed)
    cases = suite.run_trials(build, tier.trials, rng, set(ids),
                             tier.safety_trials)
    return {"record": record.make_record(root, tier, build, seed),
            "cases": cases}


def stale(root=repo.ROOT, baseline=BASELINE):
    """How main's files differ from the record of the baseline's run.

    Run on main, where nothing should differ: anything listed means the
    baseline is stale, and every pull request would be blamed for it."""
    old = json.loads(Path(baseline).read_text())["record"]
    now = record.make_record(root, TIERS["release"], "main", 1)
    differ = gate.changed_fields(old, now)
    if old["eval_set"] != now["eval_set"]:
        differ.append(f"eval_set {old['eval_set']} to {now['eval_set']}")
    return differ


def write(results, path):
    """One line per case, so a change to a baseline reads as a diff."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dump = lambda obj: json.dumps(obj, sort_keys=True)
    rows = [f"  {dump(i)}: {dump(c)}" for i, c in
            sorted(results["cases"].items())]
    text = (f'{{"record": {dump(results["record"])},\n "cases": {{\n'
            + ",\n".join(rows) + "\n }}\n")
    path.write_text(text)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="run_tier")
    ap.add_argument("--sample", type=int, help="cases, rotating")
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--safety", action="store_true",
                    help="run the never-fail cases many times")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="results/scores.json")
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--check-baseline", action="store_true",
                    help="on main: refuse a baseline from other files")
    args = ap.parse_args(argv)
    differ = stale() if args.check_baseline else []
    if differ:
        print("STALE BASELINE: " + ", ".join(differ)
              + "; rewrite it with --update-baseline")
        return 2
    if args.update_baseline:        # main's own scores, at full strength
        write(run_tier("release", seed=1), BASELINE)
        print(f"wrote {BASELINE}")
        return 0
    tier = Tier("run", args.sample, args.trials, args.safety)
    results = run_tier(tier, seed=args.seed)
    write(results, args.out)
    print(f"{len(results['cases'])} cases, {args.trials} trials, "
          f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
