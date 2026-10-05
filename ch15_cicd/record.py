"""The run record: every version that produced a score, stamped on it."""
import json

from ch07_datasets.card import content_hash
from ch15_cicd import repo, suite


def eval_set_label(version=1, cases=None):
    """The label a score carries: name, version and content hash."""
    cases = [{k: c[k] for k in ("id", "slice", "text", "never_fail")}
             for c in cases or suite.case_meta()]
    return f"Relay gate set v{version} ({content_hash(cases)})"


def make_record(root, tier, build, seed):
    """Prompt, model, tools, index, eval set and judge, in one place."""
    prompt, _ = repo.read_prompt(
        (root / "prompts/system.md").read_text())
    config = json.loads((root / "config/relay.json").read_text())
    return {"prompt": f"system@{prompt['version']}",
            "model": config["model"],
            "tools": repo.tool_versions(root),
            "index": config["index"],
            "eval_set": eval_set_label(),
            "judge": config["judge"],
            "sample": tier.sample, "trials": tier.trials,
            "safety": tier.safety, "build": build, "seed": seed}


def lines(record):
    """The record as the lines a person reads."""
    return [f"prompt    {record['prompt']}",
            f"model     {record['model']}",
            f"tools     {', '.join(record['tools'])}",
            f"index     {record['index']}",
            f"eval set  {record['eval_set']}",
            f"judge     {record['judge']}"]
