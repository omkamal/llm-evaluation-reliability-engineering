"""Every Chapter 4 number, with its printed output.

    python3 -m ch04_numbers.demo
"""
import random
from math import sqrt
from statistics import stdev

from ch03_first_eval.cases import CASES
from ch03_first_eval.run_evals import run
from ch04_numbers.ab_scores import prompt_ab_scores
from ch04_numbers.noisy import (case_scores, false_alarm_count,
                                flagged_count, many_trials, one_run)
from ch04_numbers.power import (MILLER_VAR, cases_needed, detectable_drop,
                                detectable_gap, independent_var)
from ch04_numbers.report_card import report_card
from ch04_numbers.stats import (
    bootstrap_ci, cluster_bootstrap_ci, clustered_se, coverage,
    difference_ci, mean, paired_bootstrap, paired_vs_unpaired_se,
    pass_at_k, pass_at_k_rate, pass_hat_k, pass_hat_k_rate, proportion_ci,
    sign_test_p, unpaired_bootstrap, wilson_ci, wilson_difference_ci)

TOPICS = [case["topic"] for case in CASES]


def wald(wins, n):
    """The formula's interval (the Wald interval), unclipped."""
    return proportion_ci(wins, n)[2]


def verdicts(version):
    """The 0/1 verdicts of one deterministic run of Relay-30."""
    return [int(ok) for _, ok, _ in run(version)]


def one_run_lies():
    print("== one run lies")
    rng = random.Random(4)
    for version in ("v1", "v2"):
        scores = [sum(one_run(version, rng)) for _ in range(10)]
        print(f"{version}, ten runs:", *scores,
              f" ({min(scores)} to {max(scores)} of 30)")
    met = {v: sum(sum(one_run(v, rng)) >= 28 for _ in range(10_000))
           for v in ("v1", "v2")}
    for version, runs in met.items():
        print(f'"28 or more" met by {version} in '
              f"{runs / 100:.1f}% of 10,000 runs")


def repeated_trials():
    print("== pass@k and pass^k")
    for k in (3, 8):
        print(f"p = 0.75 per try, k = {k}: "
              f"pass@k {pass_at_k_rate(0.75, k):.1%}, "
              f"pass^k {pass_hat_k_rate(0.75, k):.1%}")
    n, c, k = 10, 7, 3
    print(f"{n} trials, {c} passed, k = {k}")
    print(f"  unbiased: pass@3 = {pass_at_k(n, c, k):.3f}, "
          f"pass^3 = {pass_hat_k(n, c, k):.3f}")
    print(f"  plug-in:  pass@3 = {pass_at_k_rate(c / n, k):.3f}, "
          f"pass^3 = {pass_hat_k_rate(c / n, k):.3f}")
    wins = [sum(t) for t in many_trials("v1", 10, random.Random(1))]
    print("Relay v1 (simulated), 30 cases x 10 trials:")
    print(f"  pass@1 {mean([pass_at_k(10, c, 1) for c in wins]):.2f}, "
          f"pass@3 {mean([pass_at_k(10, c, 3) for c in wins]):.2f}, "
          f"pass^3 {mean([pass_hat_k(10, c, 3) for c in wins]):.2f}")


def error_bars():
    print("== standard error and the 95% interval")
    p, se, (lo, hi) = proportion_ci(40, 50)
    print(f"40 of 50: {p:.2f}, SE {se:.3f}, "
          f"interval {lo:.2f} to {hi:.2f} (+/- {1.96 * se:.2f})")
    print(f"50 cases: SE {proportion_ci(40, 50)[1]:.3f}; "
          f"200 cases: SE {proportion_ci(160, 200)[1]:.3f}")
    for name, wins in (("v1", 28), ("v2", 23)):
        lo, hi = wilson_ci(wins, 30)
        wlo, whi = wald(wins, 30)
        print(f"Relay {name}, {wins} of 30: {wins / 30:.2f}, Wilson "
              f"{lo:.2f} to {hi:.2f} (formula {wlo:.2f} to {whi:.2f})")
    lo, hi = wilson_ci(30, 30)
    wlo, whi = wald(30, 30)
    print(f"30 of 30: Wilson {lo:.2f} to {hi:.2f} "
          f"(formula {wlo:.2f} to {whi:.2f})")
    print(f"true rate 0.95, 30 cases: covered by Wilson "
          f"{coverage(wilson_ci, 30, 0.95):.0%}, "
          f"by the formula {coverage(wald, 30, 0.95):.0%}")


def overlap():
    print("== overlap")
    for wins in (40, 35):          # version 1 scores 40 or 35 of 50
        gap, (lo, hi) = difference_ci(wins, 50, 44, 50)
        _, _, (lo1, hi1) = proportion_ci(wins, 50)
        _, _, (lo2, hi2) = proportion_ci(44, 50)
        print(f"{wins} vs 44 of 50: intervals overlap by "
              f"{hi1 - lo2:.2f}; gap {gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")


def sample_size():
    print("== how many cases")
    print("drop    separate  paired")
    for points in (10, 5, 3, 2):
        gap = points / 100
        alone = cases_needed(gap, independent_var(0.85, 0.85 - gap))
        paired = cases_needed(gap, MILLER_VAR)
        print(f"{points:>2} pts  {alone:>8,}  {paired:>6,}")
    print("30 cases catch, 4 times in 5, a gap of at least:")
    alone = detectable_drop(30, 0.85)
    paired = detectable_gap(30, MILLER_VAR)
    print(f"  {alone:.2f} scored separately, {paired:.2f} paired")


def clusters():
    print("== clusters")
    for version in ("v1", "v2"):
        scores = verdicts(version)
        naive = proportion_ci(sum(scores), len(scores))[1]
        clustered = clustered_se(scores, TOPICS)
        print(f"Relay {version}: SE {naive:.3f} treating cases as "
              f"independent, {clustered:.3f} by topic "
              f"({clustered / naive:.1f}x)")


def bootstrap():
    print("== bootstrap")
    sample = [1] * 24 + [0] * 6
    rng = random.Random(11)
    rng.shuffle(sample)          # only so the picture is not sorted
    means = [mean([sample[rng.randrange(30)] for _ in range(30)])
             for _ in range(3)]
    print("three resample means:", " ".join(f"{m:.2f}" for m in means))
    rate, (lo, hi) = bootstrap_ci(sample, seed=11)
    print(f"10,000 resamples: {rate:.2f}, interval {lo:.2f} to {hi:.2f}")
    wlo, whi = wilson_ci(24, 30)
    print(f"Wilson formula:   interval {wlo:.2f} to {whi:.2f}")


def friday_paired():
    print("== Friday, paired")
    v1, v2 = verdicts("v1"), verdicts("v2")
    diffs = [b - a for a, b in zip(v1, v2)]
    better, worse = diffs.count(1), diffs.count(-1)
    print(f"v1 {sum(v1)} passes, v2 {sum(v2)}: "
          f"{better} cases better, {worse} worse, "
          f"{diffs.count(0)} unchanged")
    gap, (lo, hi) = wilson_difference_ci(sum(v1), 30, sum(v2), 30)
    print(f"unpaired: {gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    gap, (lo, hi) = paired_bootstrap(v1, v2)
    print(f"paired:   {gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    gap, (lo, hi) = cluster_bootstrap_ci(diffs, TOPICS)
    print(f"by topic: {gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    print(f"sign test p = {sign_test_p(better, worse):.2f}")


def why_pairing_helps():
    print("== why pairing helps")
    old, new = prompt_ab_scores()
    paired, unpaired, rho = paired_vs_unpaired_se(old, new)
    print(f"200 simulated scores, correlation {rho:.2f}")
    print(f"SE of the gap: unpaired {unpaired:.3f}, paired {paired:.3f}")
    print(f"with correlation 0.5 the paired SE is "
          f"{1 - (1 - 0.5) ** 0.5:.0%} smaller")


def prompt_ab_test():
    print("== A/B test of a prompt change")
    old, new = prompt_ab_scores()
    gap, (lo, hi) = paired_bootstrap(old, new)
    print(f"paired:   {gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")
    gap, (lo, hi) = unpaired_bootstrap(old, new)
    print(f"unpaired: {gap:+.2f} [{lo:+.2f}, {hi:+.2f}]")


def how_often_flagged():
    print("== how often is Friday flagged? (100 repeats)")
    for trials in (1, 5):
        label = "trial" if trials == 1 else "trials"
        print(f"{trials} {label} per case: "
              f"flagged in {flagged_count(trials, 100)} of 100")


def card():
    print("== report card")
    rng = random.Random(0)
    v1 = case_scores(many_trials("v1", 5, rng))
    v2 = case_scores(many_trials("v2", 5, rng))
    again = case_scores(many_trials("v1", 5, rng))
    print("Relay-30, 5 trials per case, topics as clusters")
    print(*report_card("v1", "v2", v1, v2, clusters=TOPICS), sep="\n")
    print("Same version twice (an A/A check)")
    print(*report_card("v1 run A", "v1 run B", v1, again,
                       clusters=TOPICS), sep="\n")


def aa_false_alarms():
    print("== A/A false alarms (Exercise 2)")
    alarms = false_alarm_count(5, 400)
    print(f"v1 against itself, 5 trials per case: zero excluded "
          f"{alarms} times in 400")


def ten_trials_are_not_ten_cases():
    print("== ten trials of 30 cases (Check your understanding, 6)")
    many, few = (proportion_ci(0.89 * n, n)[1] for n in (300, 30))
    print(f"at 0.89: SE {many:.3f} with n = 300, {few:.3f} with n = 30")
    for seed in range(3):
        rates = case_scores(many_trials("v1", 10, random.Random(seed)))
        print(f"seed {seed}: SE over the 30 case rates "
              f"{stdev(rates) / sqrt(30):.3f}")


def main():
    one_run_lies()
    repeated_trials()
    error_bars()
    overlap()
    sample_size()
    clusters()
    bootstrap()
    friday_paired()
    why_pairing_helps()
    prompt_ab_test()
    how_often_flagged()
    card()
    aa_false_alarms()
    ten_trials_are_not_ten_cases()


if __name__ == "__main__":
    main()
