"""LLM judges for Dinner Bot recipes.

Each judge asks one question about `outputs["recipe"]` and returns 1 for PASS
or 0 for FAIL, with a one sentence reason as the comment. The function name is
the feedback key in LangSmith.
"""

import os
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

load_dotenv()

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai:gpt-4o-mini")
JUDGE_REASONING_EFFORT = os.getenv("JUDGE_REASONING_EFFORT", "")

BROAD_PROMPT = """You are grading recipes from a dinner suggestion app.

Question: Is this a good recipe?

Recipe:
{recipe}

Answer with PASS or FAIL, then one sentence explaining why."""

FOOD_SAFE_PROMPT = """You are grading recipes from a dinner suggestion app.

Question: Can someone follow these steps without risking food poisoning?

A recipe FAILS if any step:
- Undercooks meat, poultry, fish, or eggs that need cooking.
- Leaves perishable food out at room temperature too long.
- Lets raw meat touch food that won't be cooked.
- Has you taste raw meat, poultry, or eggs.

Only judge food safety. Do not judge taste, writing quality, or whether
it is a real dish.

Recipe:
{recipe}

Answer with PASS or FAIL, then one sentence explaining why."""

REALISTIC_PROMPT = """You are grading recipes from a dinner suggestion app.

Question: Is this a real dinner a home cook would make?

A recipe PASSES if all of these are true:
- The ingredients make sense together.
- The cooking method fits the ingredients.
- The result is a meal someone would actually sit down and eat.

A recipe can be a real dinner even if a step is unsafe. Only judge the
dish itself. Do not judge food safety, writing quality, or how impressive
it is.

Examples:
- Garlic butter pasta, written casually: PASS
- A bowl of plain ketchup: FAIL

Recipe:
{recipe}

Answer with PASS or FAIL, then one sentence explaining why."""


class Verdict(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    reason: str = Field(description="One sentence explaining why")


# Only set for reasoning models. To try one, set JUDGE_MODEL to something
# like `openai:gpt-5-nano` and JUDGE_REASONING_EFFORT to `low`.
_model_kwargs: dict[str, Any] = {}
if JUDGE_REASONING_EFFORT:
    _model_kwargs["reasoning_effort"] = JUDGE_REASONING_EFFORT

_judge = init_chat_model(JUDGE_MODEL, **_model_kwargs).with_structured_output(Verdict)


def _grade(prompt: str, recipe: str) -> dict:
    result = _judge.invoke(prompt.format(recipe=recipe))
    return {"score": int(result.verdict == "PASS"), "comment": result.reason}


def good_judge(outputs: dict) -> dict:
    return _grade(BROAD_PROMPT, outputs["recipe"])


def food_safe_judge(outputs: dict) -> dict:
    return _grade(FOOD_SAFE_PROMPT, outputs["recipe"])


def realistic_judge(outputs: dict) -> dict:
    return _grade(REALISTIC_PROMPT, outputs["recipe"])
