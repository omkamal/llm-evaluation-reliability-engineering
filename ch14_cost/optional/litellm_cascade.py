"""LiteLLM check for Chapter 14: one cascade, priced by LiteLLM itself.

Run once in a throwaway virtualenv; not part of pytest or CI.
Every provider reply is mocked, so no key and no network are needed.
"""
import random
from importlib.metadata import version

from litellm import ModelResponse, Router, cost_per_token
from litellm.types.utils import Usage

router = Router(
    model_list=[
        {"model_name": "small",
         "litellm_params": {"model": "openai/gpt-4.1-mini"}},
        {"model_name": "frontier",
         "litellm_params": {"model": "openai/gpt-4.1"}},
    ],
    fallbacks=[{"small": ["frontier"]}],   # a tier that is down
    num_retries=2,
)


def reply(text):
    """A mocked provider reply: 3,000 tokens in, 250 out."""
    usage = Usage(prompt_tokens=3000, completion_tokens=250,
                  total_tokens=3250)
    message = {"role": "assistant", "content": text}
    return ModelResponse(choices=[{"message": message}], usage=usage)


def ask(hard):
    """Small tier first; step up to frontier when the check fails."""
    messages = [{"role": "user", "content": "Where is order 1042?"}]
    first = router.completion(
        model="small", messages=messages,
        mock_response=reply("UNSURE" if hard else "OK"))
    usd = first._hidden_params["response_cost"]
    if first.choices[0].message.content == "OK":
        return usd, False
    second = router.completion(
        model="frontier", messages=messages, mock_response=reply("OK"))
    return usd + second._hidden_params["response_cost"], True


rng = random.Random(7)
results = [ask(rng.random() < 0.18) for _ in range(1000)]
per_task = sum(usd for usd, _ in results) / len(results)
stepped = sum(up for _, up in results) / len(results)
price_in, price_out = cost_per_token(
    model="openai/gpt-4.1", prompt_tokens=3000, completion_tokens=250)
frontier = price_in + price_out
print(f"litellm {version('litellm')}")
print(f"stepped up: {stepped:.0%}, ${per_task:.4f} per task")
print(f"frontier only: ${frontier:.4f} per task")
print(f"saving: {1 - per_task / frontier:.0%}")
