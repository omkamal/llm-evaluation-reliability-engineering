"""The judge in production: its cost, and its version on every score."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreRecord:
    trace_id: str
    judge_version: str      # which judge produced this score
    verdict: str            # "pass" or "fail"


class MixedJudges(Exception):
    pass


def pass_rate(records):
    """Pass rate of one judge version. Mixed versions are refused."""
    versions = {r.judge_version for r in records}
    if len(versions) != 1:
        raise MixedJudges(f"scores from {sorted(versions)}: "
                          "re-score first")
    return sum(r.verdict == "pass" for r in records) / len(records)


def monthly_judge_cost(tasks, sample_rate, tokens_in, tokens_out,
                       usd_in_per_m, usd_out_per_m):
    """Dollars to judge a sample of the period's chats or tasks (Relay
    counts its chat layer over 28 days)."""
    judged = tasks * sample_rate
    per_call = (tokens_in * usd_in_per_m
                + tokens_out * usd_out_per_m) / 1_000_000
    return judged, judged * per_call
