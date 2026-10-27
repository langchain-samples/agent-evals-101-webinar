# Agent Evals 101

The repo for LangChain's **Agent Evals 101** webinar. It has two small agents that live in the same kitchen app:

- **Dinner Bot** suggests a recipe from what's in your kitchen. It's the agent from the live demo.
- **Recipe Remixer** changes a recipe to fit a diet, like "make this vegetarian." It's the take home.

Each agent has an intentional bug. You find it in the traces, write evals that catch it, fix it, and rerun.

Everything here works on the LangSmith Developer (free) plan!

## Repo layout

```text
agent-evals-101/
├── .env.example                    # env template: copy to .env and add your keys
├── pyproject.toml                  # dependencies for the whole repo
├── dinner_bot/                     # the live demo agent
│   ├── agent.py                    # the agent, its one tool (get_pantry), and the STAPLES list
│   ├── code_eval/
│   │   ├── traces.json             # 25 saved Dinner Bot traces to build the dataset from
│   │   ├── upload_traces.py        # uploads those traces to your LangSmith project
│   │   ├── kitchen_evaluator.py    # code eval: every ingredient must be in the kitchen
│   │   └── eval.py                 # runs Dinner Bot over a dataset with the code eval
│   └── llm_eval/
│       ├── judges.py               # three LLM judges: good, food_safe, realistic
│       ├── judge_examples.py       # 8 saved recipes with human labels
│       └── judge_experiments.py    # builds the labeled dataset and runs the judges
└── recipe_remixer/                 # the take home agent
    ├── agent.py                    # the agent, its one tool (get_substitute), and the rewrite step
    ├── traces.json                 # 20 saved Recipe Remixer traces to build the dataset from
    ├── upload_traces.py            # uploads those traces to a recipe-remixer project
    └── answer_key/                 # open when you're done
        ├── agent.py                # Recipe Remixer with the bug fixed
        └── llm_eval.py             # an LLM judge that catches the bug
```

## Setup

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/).

1. Install the dependencies:

   ```bash
   uv sync
   ```

2. Create your `.env` from the template:

   ```bash
   cp .env.example .env
   ```

3. Fill in your keys in `.env`:

   | Variable | What it's for | Where to get it |
   | --- | --- | --- |
   | `LANGSMITH_API_KEY` | Sends traces, datasets, and experiments to LangSmith | LangSmith, under **Settings > API Keys** |
   | `OPENAI_API_KEY` | Runs the agents and the LLM judges | [platform.openai.com](https://platform.openai.com/api-keys) |

   If your LangSmith account is in the EU or APAC region, also uncomment the matching `LANGSMITH_ENDPOINT` line. Otherwise your key won't work.

   The rest of `.env.example` already has working defaults. `DATASET_NAME` and `JUDGE_DATASET_NAME` set the names of the datasets the scripts use. The commented out lines at the bottom let you swap models.

`.env` stays on your machine. Don't commit it.

Run every command below from the repo root.

## Dinner Bot (the demo)

Dinner Bot is part of an app that keeps track of your kitchen. The app passes your saved kitchen in with every request. The agent's one tool, `get_pantry`, returns that kitchen plus a built in list of staples the app assumes everyone has.

The bug: the `STAPLES` list in `dinner_bot/agent.py` should only be salt, pepper, oil, and water. Over time it grew to include butter, garlic, onion, and more. So the agent thinks you have butter when you don't.

### Run the agent

```bash
uv run python -m dinner_bot.agent
```

It prints a recipe for a kitchen of pasta, eggs, parmesan, and spinach. Open the trace in LangSmith. The `get_pantry` output shows the kitchen and the staples as separate lists.

### Part 1: Code eval

The code eval in `dinner_bot/code_eval/kitchen_evaluator.py` checks that every ingredient in the recipe is either in your kitchen or one of the four real staples. It doesn't need a reference answer, because the kitchen is part of the input.

1. Run the agent a couple of times and look at the traces. Notice which ingredients show up in the recipes that aren't in the kitchen.

2. Upload 25 saved traces. These are real runs of the buggy Dinner Bot, each with a different kitchen. They go to the project set by `LANGSMITH_PROJECT` (`dinner-bot` by default):

   ```bash
   uv run python -m dinner_bot.code_eval.upload_traces
   ```

3. Create the dataset from the traces. In LangSmith, open the project, select the 25 `dinner_request` traces, and add them to a new dataset. Name it whatever `DATASET_NAME` is set to (`dinner-bot-dataset` by default). The kitchen comes along because it's in each trace's inputs:

   ```json
   {"message": "What can I make for dinner?", "kitchen": ["rice", "eggs", "frozen peas", "carrots"]}
   ```

   The recipe from each trace comes along too, as the reference output. The code eval doesn't use it. You can add your own traces from step 1 the same way.

4. Run the experiment:

   ```bash
   uv run python -m dinner_bot.code_eval.eval
   ```

5. Fix the bug by trimming `STAPLES` in `dinner_bot/agent.py` to `["salt", "pepper", "oil", "water"]`. Run the experiment again and compare the two in LangSmith.

### Part 2: LLM judges

Code can't tell you the quality of a recipe, so this part uses LLM judges. Every judge is checked against human labels.

- `good_judge` asks a broad question: "Is this a good recipe?"
- `food_safe_judge` asks: "Can someone follow these steps without risking food poisoning?"
- `realistic_judge` asks: "Is this a real dinner a home cook would make?"

The recipes in `judge_examples.py` are written by hand so every run sees the same ones. Each has human labels for `food_safe_human` and `realistic_human`. A recipe counts as `good` if it passes both. When a recipe fails, the label comes with a short reviewer note, like "Recipe says to taste the raw turkey mixture."

For the demo, the script adds these human labels for you. In practice, your team would label runs in an [annotation queue](https://docs.langchain.com/langsmith/annotation-queues), and you can use [Align Evals](https://www.langchain.com/blog/introducing-align-evals) in LangSmith to tune a judge until it agrees with those labels.

Build the dataset and run both experiments:

```bash
uv run python -m dinner_bot.llm_eval.judge_experiments
```

This creates two experiments in LangSmith on the same dataset:

| Experiment | Human labels | Judges |
| --- | --- | --- |
| `broad-judge` | `good_human` | `good_judge` |
| `narrow-judges` | `food_safe_human`, `realistic_human` | `food_safe_judge`, `realistic_judge` |

Compare each judge's column with the human column next to it. The broad judge disagrees with the humans more often. The narrow judges ask the same questions the humans did, so they line up. Click a row to read the judge's one sentence reason.

Each run of the script creates two new experiments. It reuses the dataset if it already exists.

## Recipe Remixer (the take home)

New agent, same kitchen. Same setup, new bug.

Before you start, update your `.env` so the take home gets its own project and dataset:

```bash
LANGSMITH_PROJECT=recipe-remixer
REMIXER_DATASET_NAME=recipe-remixer-dataset
```

Otherwise your Recipe Remixer traces land in the `dinner-bot` project with the demo traces. If you've run the take home before, pick new names so you start fresh.

Recipe Remixer takes one of your saved recipes and a request like "make this vegetarian" or "make this dairy free." It works in two steps:

1. The agent looks up swaps with its one tool, `get_substitute(ingredient, diet)`, like chicken breast to tofu. It returns the new ingredient list.
2. `rewrite` is an LLM call that updates the steps to match the new ingredients.

Run it:

```bash
uv run python -m recipe_remixer.agent
```

Each exercise has a hint. Try it without the hint first.

### 1. Find the bug

Run the agent and read the recipe it returns. Then open the trace in LangSmith and find where things go wrong.

<details>
<summary>Hint</summary>

Compare the ingredients the agent returned with the recipe the `rewrite` call was given.

</details>

### 2. Build a dataset

Upload 20 saved traces of the buggy agent. They go to their own `recipe-remixer` project:

```bash
uv run python -m recipe_remixer.upload_traces
```

If you set `LANGSMITH_PROJECT` to a different name, pass it with `--project` so the uploaded traces land next to your own runs:

```bash
uv run python -m recipe_remixer.upload_traces --project your-project-name
```

Add them to a new dataset named whatever `REMIXER_DATASET_NAME` is set to (`recipe-remixer-dataset` by default). The recipe comes along because it's in each trace's inputs, just like the kitchen in Dinner Bot. You can add your own traces from exercise 1 the same way.

<details>
<summary>Hint</summary>

A few of the recipes already fit the diet, like the Lentil Soup. Nothing needs a swap, so a good eval should pass them before and after the fix.

</details>

### 3. Write an evaluator

Write an evaluator that catches the bug and run it on your dataset with `evaluate()`. The Dinner Bot evaluators in `dinner_bot/code_eval/` and `dinner_bot/llm_eval/` are good starting points.

<details>
<summary>Hint</summary>

Read a few failing traces and ask what you'd check by hand. The original recipe is in `inputs["recipe"]`, and the output has the new ingredient list and steps. Before you trust the scores, check that your evaluator passes the recipes that already fit the diet.

</details>

### 4. Write a single step evaluator

Test `rewrite` on its own, without running the whole agent. Give it a recipe, check the steps it returns, and run it with `evaluate()`. What does the result tell you about where the bug is?

<details>
<summary>Hint</summary>

Make each example a recipe whose ingredient list already has the swaps, but whose steps still use the originals. Your target passes it to `rewrite` and returns the steps. Your evaluator checks that the steps match the ingredient list. If `rewrite` passes, the step itself works, and the problem is what it gets in the full agent. Single step evals are faster and cheaper than running the whole agent, and they tell you which part is broken.

</details>

### 5. Fix the bug, rerun, and compare

Fix the agent, then rerun your experiment from exercise 3 and compare it to the first run in LangSmith.

<details>
<summary>Hint</summary>

A prompt change won't work, because the swaps never reach `rewrite`. Look at which recipe `remix` passes to `rewrite`. The fix is one word.

</details>

### 6. Write your own judge

Run the Dinner Bot judges from Part 2 and compare each one to its human column. Then pick a new narrow question, like "Can this be made in 30 minutes?" Label a few recipes yourself and write a judge that agrees with you.

<details>
<summary>Hint</summary>

Start from one of the narrow judges in `dinner_bot/llm_eval/judges.py`. If your judge disagrees with your labels, read its reasons first. The fix is usually a clearer question, not a longer prompt.

</details>

### Answer key

When you're done, compare your work with `recipe_remixer/answer_key/`. `agent.py` is Recipe Remixer with the bug fixed. `llm_eval.py` is one way to catch the bug. Run it on your agent, then on the fixed one:

```bash
uv run python -m recipe_remixer.answer_key.llm_eval
uv run python -m recipe_remixer.answer_key.llm_eval --fixed
```

## Learn more

- [The Most Common Questions About Agent Evals, Answered](https://www.langchain.com/blog/common-questions-about-agent-evals)
- [LangSmith evaluation docs](https://docs.langchain.com/langsmith/evaluation)
