"""Measure a judge against the expert, and keep its card (Chapter 5)."""
import random
from dataclasses import dataclass

from ch04_numbers.stats import bootstrap_ci, wilson_ci
from ch05_judge.agreement import cohen_kappa, confusion, observed_agreement
from ch05_judge.answers import expert_label
from ch05_judge.simjudge import reply
from ch05_judge.verdict import answer_key, grade, verdict_gateway


def split(items, dev_share=0.5, seed=0):
    """Dev set to tune the prompt on; test set nobody tunes against."""
    items = list(items)
    random.Random(seed).shuffle(items)
    cut = int(len(items) * dev_share)
    return items[:cut], items[cut:]


def judge_labels(cfg, answers):
    """Run the judge over answers; every reply passes the gateway."""
    gateway, labels = verdict_gateway(), []
    for a in answers:
        v = grade(gateway, a.question, a,
                  lambda prompt, a=a: reply(cfg, a.question, a),
                  version=cfg.version, policy=answer_key(a.question))
        labels.append(v.verdict if v else "fail")   # unreadable = fail
    return labels


def rate(hits, n):
    """A rate over one group, with its Wilson interval (Chapter 4)."""
    if n == 0:
        return 0.0, (0.0, 1.0)              # no cases: no knowledge
    return hits / n, wilson_ci(hits, n)


def report(judge, expert):
    """The numbers a judge card needs. TPR is a pass rate over the
    expert's passes and TNR over the expert's fails, so each gets an
    interval; kappa is quoted with the share of fails it was seen at."""
    tp, fp, fn, tn = confusion(judge, expert)
    tpr, tpr_ci = rate(tp, tp + fn)
    tnr, tnr_ci = rate(tn, tn + fp)
    return {"n": len(expert), "fails": tn + fp,
            "agree": observed_agreement(judge, expert),
            "kappa": cohen_kappa(judge, expert),
            "tpr": tpr, "tnr": tnr, "tpr_ci": tpr_ci, "tnr_ci": tnr_ci}


def calibrate(cfg, answers):
    """Judge `answers`, compare with the expert's labels, report."""
    expert = [expert_label(a) for a in answers]
    return report(judge_labels(cfg, answers), expert)


def kappa_interval(judge, expert, resamples=2000, seed=0):
    """95% bootstrap interval for kappa (Chapter 4's bootstrap_ci)."""
    def kappa_of(pairs):
        j, e = zip(*pairs)
        return cohen_kappa(j, e)
    return bootstrap_ci(list(zip(judge, expert)), resamples=resamples,
                        seed=seed, stat=kappa_of)


def labels_needed(rate_seen, floor=0.8, most=10_000):
    """How many labelled cases in one group (fails, for TNR) before a
    judge scoring `rate_seen` shows a Wilson low end at `floor`."""
    for n in range(1, most):
        if wilson_ci(rate_seen * n, n)[0] >= floor:
            return n
    return None


def bar(rep, tpr_min=0.8, tnr_min=0.8):
    """The team's bar, chosen in advance, on both rates. A point
    estimate below it fails; 'met' needs the low end of each interval
    to clear it; anything between is not shown yet: label more."""
    if rep["tpr"] < tpr_min or rep["tnr"] < tnr_min:
        return "failed"
    if rep["tpr_ci"][0] >= tpr_min and rep["tnr_ci"][0] >= tnr_min:
        return "met"
    return "not shown"


def meets_bar(rep, kappa_min=None, tnr_min=0.8, tpr_min=0.8):
    """True only when the bar is met on the intervals. Kappa moves with
    the share of fails, so it is checked only if you ask for it."""
    shown = bar(rep, tpr_min, tnr_min) == "met"
    return shown and (kappa_min is None or rep["kappa"] >= kappa_min)


@dataclass(frozen=True)
class JudgeCard:
    """One page about one judge: what it is and what it was shown."""
    cfg: object
    rep: dict
    interval: tuple         # 95% interval for kappa
    labelled_by: str
    frozen_on: str
    model_id: str = ""      # the pinned snapshot the judge calls

    def lines(self):
        c, r = self.cfg, self.rep
        feats = [n.replace("_", " ") for n in
                 ("anchored", "evidence_first", "few_shot", "style_note")
                 if getattr(c, n)]
        model = f"family {c.model.family}"
        if self.model_id:
            model = f"{self.model_id} ({model})"
        lo, hi = self.interval
        (tl, th), (nl, nh) = r["tpr_ci"], r["tnr_ci"]
        return [
            f"Judge card: relay-quality {c.version}",
            "Grades:      one Relay reply against the policy sheet",
            f"Model:       {model}",
            f"Prompt:      {', '.join(feats) or 'plain'}",
            f"Tested on:   {r['n']} blind cases, labelled by "
            f"{self.labelled_by}",
            f"Good kept:   TPR {r['tpr']:.2f} [{tl:.2f}, {th:.2f}] "
            f"of {r['n'] - r['fails']}",
            f"Bad caught:  TNR {r['tnr']:.2f} [{nl:.2f}, {nh:.2f}] "
            f"of {r['fails']}",
            f"Kappa:       {r['kappa']:.2f} [{lo:.2f}, {hi:.2f}] at "
            f"{r['fails'] / r['n']:.0%} fails; raw {r['agree']:.2f}",
            f"Bar:         TPR, TNR >= 0.8 at the low end: {bar(r)}",
            f"Frozen on:   {self.frozen_on}; re-check on any change, "
            "monthly",
        ]
