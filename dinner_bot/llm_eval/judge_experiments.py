"""Build the two labeled experiments for the judge segment.

Creates a dataset of seeded Dinner Bot replies, then runs two experiments on
it. Each experiment gets human labels as feedback, the way an annotation
queue would add them:

- broad-judge: `good_human` vs. `good_judge`
- narrow-judges: `food_safe_human` and `realistic_human` vs. `food_safe_judge`
  and `realistic_judge`

Run from the repo root: uv run python -m dinner_bot.llm_eval.judge_experiments
"""

import os

from dotenv import load_dotenv
from langsmith import Client, evaluate

from dinner_bot.llm_eval.judge_examples import EXAMPLES
from dinner_bot.llm_eval.judges import food_safe_judge, good_judge, realistic_judge

load_dotenv()

MESSAGE = "What can I make for dinner?"

# The target replays the stored reply for each kitchen, so both experiments
# see the exact same recipes every time.
_replies = {tuple(e["kitchen"]): e for e in EXAMPLES}


def dinner_request(inputs: dict) -> dict:
    # The judges only read the recipe text, so the replay skips the
    # ingredients list that Dinner Bot also returns.
    return {"recipe": _replies[tuple(inputs["kitchen"])]["recipe"]}


def _human_labels(example: dict) -> dict[str, bool]:
    labels = {"food_safe": example["food_safe"], "realistic": example["realistic"]}
    # good is computed, not labeled: a recipe is good if it passes both.
    labels["good"] = labels["food_safe"] and labels["realistic"]
    return labels


def _human_comments(example: dict) -> dict[str, str | None]:
    # Reviewers only leave a note when a recipe fails.
    notes = example.get("notes", {})
    comments = {"food_safe": notes.get("food_safe"), "realistic": notes.get("realistic")}
    # good reuses the note from whichever question failed.
    comments["good"] = " ".join(c for c in comments.values() if c) or None
    return comments


def create_dataset(client: Client, dataset_name: str) -> None:
    if client.has_dataset(dataset_name=dataset_name):
        print(f"Dataset {dataset_name} already exists, reusing it.")
        return

    dataset = client.create_dataset(dataset_name)
    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {"inputs": {"message": MESSAGE, "kitchen": e["kitchen"]}}
            for e in EXAMPLES
        ],
    )


def run_experiment(
    client: Client,
    dataset_name: str,
    prefix: str,
    evaluators: list,
    human_keys: list[str],
) -> None:
    results = evaluate(
        dinner_request,
        data=dataset_name,
        evaluators=evaluators,
        experiment_prefix=prefix,
        client=client,
    )
    client.flush()

    for row in results:
        example = _replies[tuple(row["example"].inputs["kitchen"])]
        labels = _human_labels(example)
        comments = _human_comments(example)
        for key in human_keys:
            client.create_feedback(
                row["run"].id,
                key=f"{key}_human",
                score=int(labels[key]),
                comment=comments[key],
                session_id=row["run"].session_id,
            )


def main() -> None:
    client = Client()
    dataset_name = os.environ["JUDGE_DATASET_NAME"]

    create_dataset(client, dataset_name)
    run_experiment(client, dataset_name, "broad-judge", [good_judge], ["good"])
    run_experiment(
        client,
        dataset_name,
        "narrow-judges",
        [food_safe_judge, realistic_judge],
        ["food_safe", "realistic"],
    )


if __name__ == "__main__":
    main()
