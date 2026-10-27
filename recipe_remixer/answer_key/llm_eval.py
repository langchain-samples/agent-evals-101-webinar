"""Answer key: an LLM judge for Recipe Remixer, and a script to run it.

Asks one question about `outputs["recipe"]`: do the steps only use ingredients
from the ingredient list? Returns 1 for PASS or 0 for FAIL, with a one sentence
reason as the comment. It only needs the recipe, so it can also run online.

A code check can look for swapped out names in the steps, but recipes don't
always use exact names. "Brown the beef" should fail when the recipe uses
lentils, and "add the stock" should pass when it uses vegetable stock.

Run from the repo root:

    uv run python -m recipe_remixer.answer_key.llm_eval          # your agent
    uv run python -m recipe_remixer.answer_key.llm_eval --fixed  # the fixed agent
"""

import argparse
import os
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langsmith import evaluate
from pydantic import BaseModel, Field

load_dotenv()

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai:gpt-4o-mini")
JUDGE_REASONING_EFFORT = os.getenv("JUDGE_REASONING_EFFORT", "")

STEPS_MATCH_PROMPT = """You are grading recipes from an app that changes recipes to fit a diet.

Question: Do the steps only use ingredients from the ingredient list?

A recipe FAILS if any step uses an ingredient that isn't on the list.

A step can call a listed ingredient by a shorter or more general name. For
example, "the stock" for vegetable stock or "the cheese" for vegan cheese is
fine. Salt, pepper, oil, and water are always allowed.

Only judge whether the steps match the ingredients. Do not judge taste, food
safety, or writing quality.

Recipe:
{recipe}

Answer with PASS or FAIL, then one sentence explaining why."""


class Verdict(BaseModel):
    verdict: Literal["PASS", "FAIL"]
    reason: str = Field(description="One sentence explaining why")


_model_kwargs: dict[str, Any] = {}
if JUDGE_REASONING_EFFORT:
    _model_kwargs["reasoning_effort"] = JUDGE_REASONING_EFFORT

_judge = init_chat_model(JUDGE_MODEL, **_model_kwargs).with_structured_output(Verdict)


def steps_match_judge(outputs: dict) -> dict:
    result = _judge.invoke(STEPS_MATCH_PROMPT.format(recipe=outputs["recipe"]))
    return {"score": int(result.verdict == "PASS"), "comment": result.reason}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixed", action="store_true", help="Run the fixed agent in recipe_remixer/answer_key/")
    args = parser.parse_args()

    if args.fixed:
        from recipe_remixer.answer_key.agent import remix
    else:
        from recipe_remixer.agent import remix

    def target(inputs: dict) -> dict:
        return remix(inputs["message"], inputs["recipe"])

    evaluate(
        target,
        data=os.environ["REMIXER_DATASET_NAME"],
        evaluators=[steps_match_judge],
        experiment_prefix="remixer-fixed" if args.fixed else "remixer",
    )


if __name__ == "__main__":
    main()
