"""Run Dinner Bot and the kitchen evaluator against a LangSmith dataset.

Run from the repo root: uv run python -m dinner_bot.code_eval.eval
"""

import os

from langsmith import evaluate

from dinner_bot.agent import ask
from dinner_bot.code_eval.kitchen_evaluator import uses_only_kitchen

def target(inputs: dict) -> dict:
    """Target function for LangSmith evaluate()."""
    return ask(inputs["message"], inputs["kitchen"])


def main() -> None:
    dataset = os.environ["DATASET_NAME"]

    evaluate(
        target,
        data=dataset,
        evaluators=[uses_only_kitchen],
        experiment_prefix="staples",
    )


if __name__ == "__main__":
    main()
