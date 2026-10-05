"""Every Chapter 5 idea, with its printed output.

    python3 -m ch05_judge.demo
"""
from dataclasses import replace

from ch04_numbers.stats import paired_bootstrap
from ch05_judge.agreement import (chance_agreement, cohen_kappa, confusion,
                                  labels_from_matrix, landis_koch,
                                  observed_agreement, tpr_tnr)
from ch05_judge.answers import (LEVELS, Answer, expert_label,
                                friday_tweak, make_answers, pad, twin)
from ch05_judge.calibrate import (JudgeCard, calibrate, judge_labels,
                                  kappa_interval, meets_bar, report, split)
from ch05_judge.fixes import (length_gap, self_preference_gap,
                              swap_consistency, tally)
from ch05_judge.jury import aggregate, needs_a_person
from ch05_judge.production import (MixedJudges, ScoreRecord,
                                   monthly_judge_cost, pass_rate)
from ch05_judge.simjudge import JudgeConfig, Temperament, reply, score_of
from ch05_judge.verdict import build_prompt, grade, verdict_gateway

B = Temperament("b")            # the judge's model family
V1 = JudgeConfig("v1", B)       # a plain prompt, no rubric anchors
V2 = JudgeConfig("v2", B, anchored=True, evidence_first=True,
                 few_shot=True, style_note=True)


def pct(x):
    return f"{x:.0%}"


def main():
    question = "How long do I have to return an item?"
    invented = Answer("demo", "returns?", LEVELS["returns"][1], 1,
                      eager=True)

    print("== the judge prompt")
    print(build_prompt(question, invented.text))

    print("== a verdict, validated by the gateway")
    gw = verdict_gateway()
    v = grade(gw, question, invented,
              lambda prompt: reply(V2, question, invented))
    print(f"score {v.score} -> {v.verdict}: {v.evidence}")
    contradiction = ('{"evidence": "Looks fine.", "score": 2, '
                     '"verdict": "pass"}')
    gw.check(contradiction, prompt_version="v2", model_version="judge")
    print("quarantined:", [(loc, kind)
                           for loc, kind, _ in gw.quarantine[0].errors])

    print("== did the Friday tweak get noticed?")
    old = make_answers(200, 21)
    new = friday_tweak(old, 22)
    for cfg in (V1, V2):
        a = [score_of(cfg, x) for x in old]
        b = [score_of(cfg, x) for x in new]
        diff, (lo, hi) = paired_bootstrap(a, b, resamples=2000)
        print(f"judge {cfg.version}: mean score {sum(a) / 200:.2f} -> "
              f"{sum(b) / 200:.2f}, change {diff:+.2f} "
              f"[{lo:+.2f}, {hi:+.2f}]")
    ok_old = sum(x.quality >= 4 for x in old) / 200
    ok_new = sum(x.quality >= 4 for x in new) / 200
    print(f"support lead: pass rate {pct(ok_old)} -> {pct(ok_new)}")

    print("== position bias")
    pairs = [(a, twin(a)) for a in make_answers(200, 2)]
    plain, swap = tally(V1, pairs), tally(V1, pairs, swap=True)
    print(f"listed first, one call: wins {pct(plain['x'])}, "
          f"loses {pct(plain['y'])}, ties {pct(plain['tie'])}")
    print(f"swap rule, two calls:   wins {pct(swap['x'])}, "
          f"loses {pct(swap['y'])}, ties {pct(swap['tie'])}")
    shots = replace(V1, few_shot=True)
    print(f"swap consistency: plain {pct(swap_consistency(V1, pairs))}, "
          f"with examples {pct(swap_consistency(shots, pairs))}")

    print("== verbosity bias")
    padded = [(a, pad(a)) for a in make_answers(200, 4)]
    noted = replace(V1, style_note=True)
    for name, cfg in (("plain", V1), ("style note", noted)):
        t = tally(cfg, padded, swap=True)
        print(f"{name}: padded copy wins {pct(t['y'])}, "
              f"original wins {pct(t['x'])}")
    long_set = make_answers(1000, 3)
    print(f"points added for length: {length_gap(V1, long_set):+.2f} plain,"
          f" {length_gap(noted, long_set):+.2f} with a style note")

    print("== self-preference")
    relay = make_answers(200, 5, author="a")
    rival = make_answers(200, 5, author="b")
    for fam in ("a", "b"):
        cfg = JudgeConfig("x", Temperament(fam))
        gap = self_preference_gap(cfg, relay, rival)
        print(f"family {fam} judge: Relay minus rival {gap:+.2f} points")

    print("== the raw-agreement trap")
    expert = ["pass"] * 90 + ["fail"] * 10
    always = ["pass"] * 100
    tpr, tnr = tpr_tnr(always, expert)
    print(f"always-pass judge: agreement "
          f"{observed_agreement(always, expert):.2f}, "
          f"kappa {cohen_kappa(always, expert):.2f}, "
          f"TPR {tpr:.2f}, TNR {tnr:.2f}")

    print("== the kappa worked example")
    judge, expert = labels_from_matrix(175, 15, 5, 5)
    print("tp, fp, fn, tn:", confusion(judge, expert))
    print(f"observed agreement: {observed_agreement(judge, expert):.2f}")
    print(f"chance agreement:   {chance_agreement(judge, expert):.2f}")
    kappa = cohen_kappa(judge, expert)
    print(f"kappa: {kappa:.2f} ({landis_koch(kappa)})")
    tpr, tnr = tpr_tnr(judge, expert)
    print(f"TPR {tpr:.2f}, TNR {tnr:.2f}")
    k, (lo, hi) = kappa_interval(judge, expert)
    print(f"kappa interval: [{lo:.2f}, {hi:.2f}]")

    print("== the calibration loop")
    dev, test = split(make_answers(240, 11))
    steps = [("plain prompt", V1)]
    cfg = V1
    for name in ("anchored", "evidence_first", "few_shot", "style_note"):
        cfg = replace(cfg, **{name: True})
        steps.append((f"+ {name}", cfg))
    for name, cfg in steps:
        r = calibrate(cfg, dev)
        print(f"{name:<18} kappa {r['kappa']:.2f}  TPR {r['tpr']:.2f}"
              f"  TNR {r['tnr']:.2f}")
    final = calibrate(V2, test)
    print(f"v2 on the test set, once: kappa {final['kappa']:.2f}, "
          f"bar met: {meets_bar(final)}")
    v3 = replace(V2, version="v3", anchored=False)
    again = calibrate(v3, test)
    print(f"v3 (anchors dropped): kappa {again['kappa']:.2f}, "
          f"bar met: {meets_bar(again)}")

    print("== a jury of three families")
    crowd = make_answers(300, 31)
    truth = [expert_label(a) for a in crowd]
    full = dict(anchored=True, evidence_first=True, few_shot=True,
                style_note=True)
    jurors = [JudgeConfig(f"j{f}", replace(B, family=f, wobble=1.0),
                          **full) for f in "cde"]
    kappas = []
    for cfg in jurors:
        kappas.append(calibrate(cfg, crowd)["kappa"])
        print(f"judge {cfg.model.family} alone: kappa {kappas[-1]:.2f}")
    votes = [[score_of(c, a) for c in jurors] for a in crowd]
    majority = [aggregate(v, "majority") for v in votes]
    print(f"majority of three: kappa {report(majority, truth)['kappa']:.2f}")
    unsure = [needs_a_person(v) for v in votes]
    sure = [i for i, u in enumerate(unsure) if not u]
    right = sum(majority[i] == truth[i] for i in sure) / len(sure)
    everyone = sum(m == t for m, t in zip(majority, truth)) / len(crowd)
    print(f"jury right on {pct(everyone)} of all cases")
    hard = [i for i, u in enumerate(unsure) if u]
    hard_right = sum(majority[i] == truth[i] for i in hard) / len(hard)
    print(f"{len(hard)} of {len(crowd)} are borderline: jury right on "
          f"{pct(hard_right)}")
    print(f"the other {len(sure)}: jury right on {pct(right)}")

    print("== four ways to pool 5, 4 and 2")
    scores = [5, 4, 2]
    print(f"mean {aggregate(scores, 'mean'):.2f} | "
          f"median {aggregate(scores, 'median')} | "
          f"majority {aggregate(scores, 'majority')} | "
          f"weighted {aggregate(scores, 'weighted', kappas):.2f}")

    print("== the judge in production")
    mixed = [ScoreRecord("t1", "v1", "pass"), ScoreRecord("t2", "v2", "fail")]
    try:
        pass_rate(mixed)
    except MixedJudges as e:
        print("refused:", e)
    judged, cost = monthly_judge_cost(900_000, 0.05, 1500, 150, 1.0, 4.0)
    _, everything = monthly_judge_cost(900_000, 1.0, 1500, 150, 1.0, 4.0)
    print(f"judged per month: {judged:,.0f}; cost ${cost:,.2f}")
    print(f"judging every task instead: ${everything:,.2f}")

    print("== the judge card")
    interval = kappa_interval(judge_labels(V2, test),
                              [expert_label(a) for a in test])[1]
    card = JudgeCard(V2, final, interval, "the support lead", "2026-10-04")
    print("\n".join(card.lines()))


if __name__ == "__main__":
    main()
