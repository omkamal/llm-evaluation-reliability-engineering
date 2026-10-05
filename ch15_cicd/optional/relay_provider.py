"""A promptfoo Python provider: Relay's scripted stand-in (not run by CI)."""
from common.relay_fake import ask


def call_api(prompt, options, context):
    version = options.get("config", {}).get("version", "v1")
    return {"output": ask(prompt, version)}
