"""Suggests a dinner from what's in the user's kitchen.

The app keeps track of the user's kitchen and passes it in with every
request as runtime context. The one tool, `get_pantry`, returns that
kitchen plus a built in STAPLES list.

Run from the repo root: uv run python -m dinner_bot.agent
"""

import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.chat_models import init_chat_model
from langchain.tools import ToolRuntime, tool
from langsmith import traceable
from pydantic import BaseModel, Field

load_dotenv()

MODEL_NAME = os.getenv("DINNER_BOT_MODEL", "openai:gpt-5-nano")
REASONING_EFFORT = os.getenv("DINNER_BOT_REASONING_EFFORT", "low")

# Should match the staples the app promises users: salt, pepper, oil, water.
# Bug: the list drifted and now includes items users never added. The fix is
# trimming it back to those four.
STAPLES = ["salt", "pepper", "oil", "butter", "garlic", "onion", "soy sauce", "milk"]

SYSTEM_PROMPT = """You are a dinner assistant in an app that keeps track of the user's kitchen.

When the user asks what to make, call get_pantry to see what they have.
Suggest a dinner using only what's in the user's kitchen.
Use the exact ingredient names that get_pantry returns."""


@dataclass
class Context:
    kitchen: list[str]


class Ingredient(BaseModel):
    name: str = Field(description="Exact pantry name, e.g. 'eggs'")
    quantity: str = Field(description="Amount, e.g. '2' or '200g'")


class Recipe(BaseModel):
    dish: str
    ingredients: list[Ingredient]
    steps: list[str]


@tool
def get_pantry(runtime: ToolRuntime[Context]) -> dict[str, list[str]]:
    """Get everything the user has in their kitchen."""
    return {"kitchen": runtime.context.kitchen, "staples": STAPLES}


# Conditional so an empty DINNER_BOT_REASONING_EFFORT unsets it, which lets
# DINNER_BOT_MODEL swap to a non-reasoning model like `openai:gpt-4o`.
_model_kwargs: dict[str, Any] = {}
if REASONING_EFFORT:
    _model_kwargs["reasoning_effort"] = REASONING_EFFORT

agent = create_agent(
    init_chat_model(MODEL_NAME, **_model_kwargs),
    [get_pantry],
    system_prompt=SYSTEM_PROMPT,
    context_schema=Context,
    # strict makes OpenAI enforce the schema. Without it, gpt-5-nano sometimes
    # returns steps as objects instead of strings and the run crashes.
    response_format=ProviderStrategy(Recipe, strict=True),
    name="dinner_bot",
)


# traceable records message and kitchen as the trace's inputs, so adding a
# trace to a dataset brings the kitchen along.
@traceable(name="dinner_request")
def ask(message: str, kitchen: list[str]) -> dict:
    """Run the agent once. Returns the recipe as readable text plus the
    ingredient names, which the code eval checks against the kitchen."""
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        context=Context(kitchen=kitchen),
    )
    recipe = result["structured_response"]
    return {
        "recipe": format_recipe(recipe),
        "ingredients": [i.name for i in recipe.ingredients],
    }


def format_recipe(recipe: Recipe) -> str:
    """Render a recipe as plain text."""
    lines = [recipe.dish, "", "Ingredients:"]
    lines += [f"- {i.quantity} {i.name}" for i in recipe.ingredients]
    lines += ["", "Steps:"]
    lines += [f"{n}. {step}" for n, step in enumerate(recipe.steps, 1)]
    return "\n".join(lines)


if __name__ == "__main__":
    kitchen = ["pasta", "eggs", "parmesan", "spinach"]
    print(ask("What can I make for dinner?", kitchen)["recipe"])
