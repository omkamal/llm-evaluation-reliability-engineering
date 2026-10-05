"""Prompts as code: read the repository, and review a change to it.

The miniature Relay project in `relay/` has the layout a real one needs:
prompt, tool schemas, config and eval thresholds, all in one repository so
that one commit changes them together.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent / "relay"
PINNED = re.compile(r"^a-(large|small)-v\d+$")     # a snapshot, not an alias


def read_prompt(text):
    """Split a prompt file into its header (version, owner) and body."""
    head, _, body = text.partition("\n---\n")
    header = dict(line.split(": ", 1) for line in head.splitlines())
    return {**header, "version": int(header["version"])}, body.strip()


def build_of(prompt_text):
    """Which scripted Relay this prompt makes. The stand-in reads the
    prompt: the Friday sentence turns main's Relay into the tweaked one."""
    _, body = read_prompt(prompt_text)
    return "friday" if "be more proactive" in body.lower() else "main"


def tool_versions(root=ROOT):
    """Name and version of every tool schema, e.g. reset_password@1."""
    schemas = [json.loads(p.read_text())
               for p in sorted((root / "schemas").glob("*.json"))]
    return [f"{s['name']}@{s['version']}" for s in schemas]


def snapshot(root=ROOT):
    """The files a change can touch, as {relative path: text}."""
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "baseline" not in path.parts:
            files[str(path.relative_to(root))] = path.read_text()
    return files


def check_change(before, after):
    """Problems a reviewer should not have to find by eye."""
    problems = []
    old, old_body = read_prompt(before["prompts/system.md"])
    new, new_body = read_prompt(after["prompts/system.md"])
    if new_body != old_body and new["version"] <= old["version"]:
        problems.append(f"prompt text changed, version still "
                        f"{new['version']}")
    if new["version"] > old["version"]:
        entry = re.compile(rf"^{new['version']}\s", re.M)
        if not entry.search(after["prompts/CHANGELOG.md"]):
            problems.append(f"no CHANGELOG line for version "
                            f"{new['version']}")
    model = json.loads(after["config/relay.json"])["model"]
    if not PINNED.match(model):
        problems.append(f"model {model!r} is not a pinned snapshot")
    return problems


def schema_hash(root=ROOT):
    """A short fact about the tool schemas: any edit changes it."""
    text = "".join(p.read_text()
                   for p in sorted((root / "schemas").glob("*.json")))
    return hashlib.sha256(text.encode()).hexdigest()[:8]
