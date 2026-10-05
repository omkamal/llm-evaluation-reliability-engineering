"""Measure a judge against the expert, and keep its card (Chapter 5)."""
import random
from dataclasses import dataclass

from ch04_numbers.stats import bootstrap_ci
from ch05_judge.agreement import cohen_kappa, observed_agreement, tpr_tnr
from ch05_judge.answers import expert_label
from ch05_judge.simjudge import reply
from ch05_judge.verdict import grade, verdict_gateway


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
                  version=cfg.version)
        labels.append(v.verdict if v else "fail")   # unreadable = fail
    return labels


def report(judge, expert):
    """The four numbers a judge card needs."""
    tpr, tnr = tpr_tnr(judge, expert)
    return {"n": len(expert), "agree": observed_agreement(judge, expert),
            "kappa": cohen_kappa(judge, expert), "tpr": tpr, "tnr": tnr}


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


def meets_bar(rep, kappa_min=0.7, tnr_min=0.8):
    """The team's bar, chosen in advance: agreement beyond chance, and
    real failures actually caught."""
    return rep["kappa"] >= kappa_min and rep["tnr"] >= tnr_min


@dataclass(frozen=True)
class JudgeCard:
    """One page about one judge: what it is and what it was shown."""
    cfg: object
    rep: dict
    interval: tuple         # 95% interval for kappa
    labelled_by: str
    frozen_on: str

    def lines(self):
        c, r = self.cfg, self.rep
        feats = [n.replace("_", " ") for n in
                 ("anchored", "evidence_first", "few_shot", "style_note")
                 if getattr(c, n)]
        lo, hi = self.interval
        return [
            f"Judge card: relay-quality {c.version}",
            "Grades:      one Relay reply against the policy sheet",
            f"Model:       family {c.model.family}",
            f"Prompt:      {', '.join(feats) or 'plain'}",
            f"Labelled by: {self.labelled_by}, {r['n']} blind cases",
            f"Agreement:   {r['agree']:.2f} raw; kappa {r['kappa']:.2f} "
            f"[{lo:.2f}, {hi:.2f}]",
            f"Catches:     TPR {r['tpr']:.2f} good kept, "
            f"TNR {r['tnr']:.2f} bad caught",
            f"Frozen on:   {self.frozen_on}",
            "Re-check if: prompt, rubric or model changes; monthly",
        ]
