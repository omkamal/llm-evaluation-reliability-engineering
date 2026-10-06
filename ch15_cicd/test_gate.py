"""The gate: every worked example in Chapter 15 is asserted here."""
import json

import pytest

from ch15_cicd import gate, suite
from ch15_cicd.gate import Rule, decide, verdict

RULE = Rule("all", 0.02)


def row_of(better, worse, rule=RULE):
    main, change = suite.paired_outcomes(better, worse)
    return decide(main, change, [rule])


# --- the three-way verdict --------------------------------------------
def test_the_margin_test_has_three_outcomes():
    assert verdict(-0.01, 0.06, RULE) == "PASS"      # lo above -0.02
    assert verdict(-0.10, -0.03, RULE) == "BLOCK"    # hi below -0.02
    assert verdict(-0.055, 0.025, RULE) == "WARN"    # straddles


def test_a_bound_exactly_on_the_margin_passes():
    assert verdict(-0.02, 0.05, RULE) == "PASS"
    assert verdict(-0.020000000001, 0.05, RULE) == "PASS"   # float dust
    assert verdict(-0.10, -0.02, RULE) == "WARN"      # not below it


def test_on_unsure_decides_between_warn_and_block():
    strict = Rule("all", 0.02, on_unsure="block")
    assert verdict(-0.055, 0.025, strict) == "BLOCK"
    assert verdict(-0.01, 0.06, strict) == "PASS"     # evidence still wins


# --- the worked examples ---------------------------------------------
def test_the_passing_example_is_the_one_from_the_facts_sheet():
    result = row_of(9, 4)
    row = result["rows"][0]
    assert (round(row["delta"], 3), round(row["lo"], 3),
            round(row["hi"], 3)) == (0.025, -0.010, 0.060)
    assert result["verdict"] == "PASS"


def test_the_figure_example_is_inside_the_margin_but_not_shown():
    result = row_of(7, 10)
    row = result["rows"][0]
    assert (round(row["delta"], 3), round(row["lo"], 3),
            round(row["hi"], 3)) == (-0.015, -0.055, 0.025)
    assert row["delta"] > -0.02                     # the guess is inside
    assert result["verdict"] == "WARN"
    assert row_of(7, 10, Rule("all", 0.02, "block"))["verdict"] == "BLOCK"


def test_a_neutral_change_cannot_pass_a_two_point_margin_on_200_cases():
    row = row_of(6, 6)["rows"][0]
    assert round(row["lo"], 3) == -0.035            # wider than the margin
    assert row_of(6, 6)["verdict"] == "WARN"


# --- the hard floor ----------------------------------------------------
def with_floor(failures):
    main, change = suite.paired_outcomes(9, 4)
    for i in range(failures):
        change[f"c{i:03d}"]["never_fail"] = True
        change[f"c{i:03d}"]["trials"] = [0]
    for i in range(failures, 10):
        change[f"c{i:03d}"]["never_fail"] = True
        change[f"c{i:03d}"]["trials"] = [1]
    return main, change


def test_one_failed_never_fail_trial_blocks_a_passing_change():
    main, change = with_floor(1)
    result = decide(main, change, [RULE])
    assert result["rows"][0]["verdict"] in ("PASS", "WARN")
    assert result["floor"]["verdict"] == "BLOCK"
    assert result["verdict"] == "BLOCK"


def test_a_clean_floor_does_not_change_the_verdict():
    main, change = with_floor(0)
    assert decide(main, change, [RULE])["floor"]["verdict"] == "PASS"


def test_no_failures_is_not_a_zero_failure_rate():
    assert gate.floor_bound(20) == pytest.approx(0.139, abs=0.001)
    assert gate.floor_bound(59) < 0.05 < gate.floor_bound(58)
    assert gate.floor_bound(10) > gate.floor_bound(20)


# --- slices ------------------------------------------------------------
def test_a_thin_slice_is_skipped_and_a_skip_is_never_a_pass():
    main, change = suite.paired_outcomes(9, 4, n=200)
    for i in list(change)[:10]:
        change[i]["slice"] = "tiny"
    rules = [RULE, Rule("tiny", 0.02)]
    result = decide(main, change, rules, min_cases=20)
    assert [r["verdict"] for r in result["rows"]] == ["PASS", "SKIP"]
    assert "only 10 cases" in result["rows"][1]["note"]
    assert result["verdict"] == "WARN"          # not judged, not passed
    assert result["because"] == ["tiny"]


def test_twenty_cases_that_did_not_move_do_not_pass():
    same = {f"c{i}": {"slice": "all", "never_fail": False, "trials": [1]}
            for i in range(20)}
    row = decide(same, same, [RULE])["rows"][0]
    assert round(row["lo"], 3) == -0.161     # the bootstrap alone: 0.0
    assert row["verdict"] == "WARN"


def test_the_unseen_floor_leaves_a_well_measured_change_alone():
    for n in (20, 90, 200):
        lo, _ = gate.interval([1] * n, [1] * n, resamples=200)[1]
        assert lo == pytest.approx(-1.96 ** 2 / (n + 1.96 ** 2))
    assert row_of(9, 4)["rows"][0]["lo"] == pytest.approx(-0.010, abs=5e-4)


def test_a_slice_can_block_when_the_overall_rule_only_warns():
    # 30 trigger cases fixed, 30 non-trigger cases broken, same overall
    base, new = {}, {}
    for i in range(30):
        base[f"a{i}"] = {"slice": "trigger", "never_fail": False,
                         "trials": [1 if i < 20 else 0]}
        new[f"a{i}"] = {"slice": "trigger", "never_fail": False,
                        "trials": [1 if i < 28 else 0]}
        base[f"b{i}"] = {"slice": "non-trigger", "never_fail": False,
                         "trials": [1]}
        new[f"b{i}"] = {"slice": "non-trigger", "never_fail": False,
                        "trials": [0 if i < 8 else 1]}
    rules = [Rule("all", 0.02), Rule("trigger", 0.05),
             Rule("non-trigger", 0.02)]
    rows = {r["slice"]: r["verdict"]
            for r in decide(base, new, rules)["rows"]}
    assert rows["trigger"] == "PASS"
    assert rows["non-trigger"] == "BLOCK"
    assert rows["all"] == "WARN"       # the blended number hides it


# --- the decision, with its evidence -----------------------------------
def test_the_report_shows_the_interval_and_the_worst_cases():
    main, change = suite.paired_outcomes(9, 4)
    result = decide(main, change, [RULE])
    text = "\n".join(gate.render(result, main, change, ["prompt a to b"]))
    assert "+0.025" in text and "[-0.010, +0.060]" in text
    assert "Changed since main: prompt a to b" in text
    assert "### Eval gate: PASS" in text


def test_main_must_have_a_score_for_every_case_in_the_run():
    main, change = suite.paired_outcomes(9, 4)
    del main["c000"]
    with pytest.raises(ValueError, match="no score"):
        decide(main, change, [RULE])


# --- a run that tested nothing is not a clean run -------------------------
def with_never_fail():
    """The passing example, with ten cases it gets right made never-fail."""
    main, change = suite.paired_outcomes(9, 4)
    for side in (main, change):
        for i in range(10, 20):
            side[f"c{i:03d}"]["never_fail"] = True
    return main, change


def test_a_run_with_no_cases_is_incomplete():
    main, _ = with_never_fail()
    result = decide(main, {}, [RULE])
    assert result["verdict"] == "INCOMPLETE"
    assert "only 0 cases in the run, need 20" in result["because"]


def test_a_run_without_main_s_never_fail_cases_is_incomplete():
    main, change = with_never_fail()
    for i in (13, 17):
        del change[f"c{i:03d}"]
    result = decide(main, change, [RULE])
    assert result["verdict"] == "INCOMPLETE"
    assert result["because"] == ["never-fail cases not run: c013, c017"]
    text = "\n".join(gate.render(result, main, change))
    assert "### Eval gate: INCOMPLETE" in text


def test_errored_trials_are_left_out_not_counted_as_fails():
    main, change = with_never_fail()
    change["c100"]["trials"] = [None]          # a timeout, not a fail
    result = decide(main, change, [RULE])
    assert result["verdict"] == "PASS"
    assert "c100" not in result["worse"]


def test_too_many_errored_trials_make_the_run_incomplete():
    main, change = with_never_fail()
    for i in range(100, 120):
        change[f"c{i:03d}"]["trials"] = [None]
    result = decide(main, change, [RULE])
    assert result["verdict"] == "INCOMPLETE"
    assert result["because"] == ["20 of 200 trials errored"]


def test_a_never_fail_case_whose_trials_all_errored_was_not_run():
    main, change = with_never_fail()
    change["c014"]["trials"] = [None]
    assert decide(main, change, [RULE])["because"] == [
        "never-fail cases not run: c014"]


# --- the command line ---------------------------------------------------
def write(path, record, cases):
    path.write_text(json.dumps({"record": record, "cases": cases}))


def record(**over):
    base = {"prompt": "system@7", "model": "a-large-v1", "tools": [],
            "index": "i", "judge": "judge_v2", "eval_set": "set v1"}
    return {**base, **over}


def thresholds(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"min_cases": 20, "rules": [
        {"slice": "all", "margin": 0.02, "on_unsure": "warn"}]}))
    return path


def run_cli(tmp_path, better, worse, **over):
    main, change = suite.paired_outcomes(better, worse)
    write(tmp_path / "main.json", record(), main)
    write(tmp_path / "pr.json", record(**over), change)
    return gate.main(["--baseline", str(tmp_path / "main.json"),
                      "--results", str(tmp_path / "pr.json"),
                      "--thresholds", str(thresholds(tmp_path)),
                      "--resamples", "1000"])


def test_exit_codes_pass_warn_block(tmp_path, capsys):
    assert run_cli(tmp_path, 9, 4) == 0
    assert run_cli(tmp_path, 7, 10) == 0              # WARN does not fail
    assert "Eval gate: WARN" in capsys.readouterr().out
    assert run_cli(tmp_path, 0, 40) == 1              # a clear regression


def test_an_empty_run_fails_the_check(tmp_path, capsys):
    main, _ = suite.paired_outcomes(9, 4)
    write(tmp_path / "main.json", record(), main)
    write(tmp_path / "pr.json", record(), {})
    code = gate.main(["--baseline", str(tmp_path / "main.json"),
                      "--results", str(tmp_path / "pr.json"),
                      "--thresholds", str(thresholds(tmp_path))])
    assert code == 2
    assert "Eval gate: INCOMPLETE" in capsys.readouterr().out


def test_main_s_own_run_without_its_never_fail_cases_fails(capsys):
    from ch15_cicd import repo, run_tier
    base = gate.load(run_tier.BASELINE)
    rules = [Rule(**r) for r in gate.load(
        repo.ROOT / "evals/thresholds.json")["rules"]]
    cut = {i: c for i, c in base["cases"].items() if not c["never_fail"]}
    assert decide(base["cases"], cut, rules)["verdict"] == "INCOMPLETE"
    assert decide(base["cases"], {}, rules)["verdict"] == "INCOMPLETE"


def test_different_eval_sets_are_not_compared(tmp_path, capsys):
    assert run_cli(tmp_path, 9, 4, eval_set="set v2") == 2
    assert "NOT COMPARABLE: eval_set" in capsys.readouterr().out


def test_a_different_judge_is_not_compared_either(tmp_path):
    assert run_cli(tmp_path, 9, 4, judge="judge_v3") == 2
