"""Every Chapter 6 output.   python3 -m ch06_agents.demo"""
from functools import partial

from ch06_agents.cases import CASES, RELAY_60, T3B
from ch06_agents.compare import (outcomes, paired_change, pass_rate,
                                 sign_p, slices)
from ch06_agents.crew import (Crew, careful_summarizer, eager_researcher,
                              lossy_summarizer, lost_at, wrong_writers)
from ch06_agents.evaluate import (passed, reply_ok, run_case,
                                  state_problems)
from ch06_agents.relays import (VERSIONS, candidate, current,
                                hallucinator, honest)
from ch06_agents.state_check import check_state
from ch06_agents.trajectory import (check_policy, grade_trajectory,
                                    task_cost)
from ch06_agents.triggers import cell, did_act, trigger_rates

T1, T2, T3, T4, T5, T6 = CASES
CHECKS = ["record", "fields", "untouched", "audit", "tool"]


def hallucinated_completion():
    print("== hallucinated completion")
    run = run_case(hallucinator, T1)
    inc = run["after"]["incidents"][T1["session"]["incident"]]
    print("Relay says:", run["transcript"][-1][1])
    print("reply check:", "PASS" if reply_ok(T1, run) else "FAIL")
    print(f"INC-4821 now: priority {inc['priority']}, "
          f"escalated {inc['escalated']}")
    problems = state_problems(T1, run)
    print("state check:", "PASS" if not problems else "FAIL")
    for check, why in problems.items():
        print(f"  {check}: {why}")


def fingerprints():
    print("== four flaws, four fingerprints")
    head = f"{'flaw':<15}" + "".join(f"{c:<10}" for c in CHECKS)
    print(head.rstrip())
    flaws = ("wrong_tool", "wrong_record", "wrong_priority", "nothing")
    for flaw in flaws:
        run = run_case(partial(hallucinator, flaw=flaw), T1)
        bad = check_state(run["before"], run["after"], T1["exp"])
        cells = ["FAIL" if c in bad else "ok" for c in CHECKS]
        row = f"{flaw:<15}" + "".join(f"{c:<10}" for c in cells)
        print(row.rstrip())


def reply_versus_state():
    print("== reply-only grading against state-based grading")
    print(f"{'version':<15}{'T1 T2 T3 T4 T5 T6':<20}reply-only  full")
    for name, agent in VERSIONS.items():
        runs = [run_case(agent, c) for c in CASES]
        marks = " ".join("ok" if passed(c, r) else "XX"
                         for c, r in zip(CASES, runs))
        words = sum(reply_ok(c, r) for c, r in zip(CASES, runs))
        full = sum(passed(c, r) for c, r in zip(CASES, runs))
        print(f"{name:<15}{marks:<20}{words}/6         {full}/6")


def one_sided_suite():
    print("== a one-sided suite rewards over-action")
    agent = VERSIONS["trigger_happy"]
    runs = [(c, run_case(agent, c)) for c in CASES]
    trig = [passed(c, r) for c, r in runs if c["should_act"]]
    print(f"trigger cases only: {sum(trig)}/{len(trig)} pass")
    print(f"paired suite: {sum(passed(c, r) for c, r in runs)}/6 pass")
    false = [c["id"] for c, r in runs
             if cell(c["should_act"], did_act(r)) == "false trigger"]
    print("false triggers:", ", ".join(false))


def rates():
    print("== two rates, not one number")
    print(f"{'version':<11}{'accuracy':<10}{'missed':<8}false-trigger")
    for name, agent in (("current", current), ("candidate", candidate)):
        pairs = [(c["should_act"], did_act(run_case(agent, c)))
                 for c in RELAY_60]
        r = trigger_rates(pairs)
        print(f"{name:<11}{r['accuracy']:<10.0%}{r['missed']:<8.0%}"
              f"{r['false']:.0%}")
    only = [(True, True)] * 3
    print("trigger-only suite, false-trigger rate:",
          trigger_rates(only)["false"])


def trajectories():
    print("== trajectory grading")
    run = run_case(VERSIONS["extra_effects"], T5)
    print("Relay says:", run["transcript"][-1][1])
    print("reply check:", "PASS" if reply_ok(T5, run) else "FAIL")
    print("trajectory:", grade_trajectory(T5["path"],
                                          run["after"]["tool_calls"]))
    print("state check:", ", ".join(state_problems(T5, run)))
    dawdle = [{"tool": "lookup_order", "args": {}}] * 3
    print("three lookups:", grade_trajectory(T5["path"], dawdle))
    refused = [{"tool": "reset_password", "args": {"user": "jdoe"}}]
    print("a refused reset:", grade_trajectory(T3["path"], refused))


def simulated_customer():
    print("== a simulated customer, and the policy check")
    for name in ("honest", "trigger_happy"):
        run = run_case(VERSIONS[name], T3B)
        if name == "honest":
            for speaker, text in run["transcript"]:
                print(f"  {speaker:<9}{text}")
        problems = state_problems(T3B, run)
        policy = check_policy(run["after"]["tool_calls"])
        print(f"{name}: end state {'PASS' if not problems else 'FAIL'}")
        print("  policy:", "; ".join(policy) or "clean")


def crew():
    print("== grading a crew: the whole, then the parts")
    teams = (("lossy summarizer", Crew(lossy_summarizer)),
             ("careful summarizer", Crew(careful_summarizer)),
             ("eager researcher", Crew(careful_summarizer,
                                       eager_researcher)))
    for label, team in teams:
        run = run_case(team, T6)
        problems = state_problems(T6, run)
        print(f"{label}, whole run:", "PASS" if not problems else "FAIL")
        if problems:
            print("  fields:", problems["fields"])
        lost, wrote = lost_at(team.stages), wrong_writers(team.calls)
        print("  handoff:",
              f"{lost[0]} dropped {lost[1]}" if lost else "nothing lost",
              end="; ")
        print("roles:", f"{', '.join(wrote)} wrote" if wrote else "ok")


def paired_comparison():
    print("== paired comparison on Relay-60 (illustrative simulation)")
    a, b = outcomes(current, RELAY_60), outcomes(candidate, RELAY_60)
    for name, v in (("current", a), ("candidate", b)):
        p, lo, hi = pass_rate(v)
        print(f"{name:<10}{sum(v)}/{len(v)} pass  {p:.0%}  "
              f"Wilson {lo:.0%} to {hi:.0%}")
    for name, idx in slices(RELAY_60).items():
        m, (lo, hi) = paired_change(a, b, idx)
        print(f"{name:<12} change {m:+.2f}  [{lo:+.2f}, {hi:+.2f}]  "
              f"sign test p {sign_p(a, b, idx):.2f}")


def cost_per_resolved_task():
    print("== cost and latency per task (illustrative rates)")
    print(f"{'version':<15}{'$/task':<9}{'sec/task':<10}$/resolved")
    for name, agent in VERSIONS.items():
        runs = [(c, run_case(agent, c)) for c in CASES]
        costs = [task_cost(r) for _, r in runs]
        resolved = sum(passed(c, r) for c, r in runs)
        usd = sum(u for u, _ in costs)
        secs = sum(s for _, s in costs)
        print(f"{name:<15}{usd / 6:<9.3f}{secs / 6:<10.2f}"
              f"{usd / resolved:.3f}")


def main():
    hallucinated_completion()
    fingerprints()
    reply_versus_state()
    one_sided_suite()
    rates()
    trajectories()
    simulated_customer()
    crew()
    paired_comparison()
    cost_per_resolved_task()


if __name__ == "__main__":
    main()
