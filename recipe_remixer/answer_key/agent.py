"""Answer key: Recipe Remixer with the bug fixed.

Same as recipe_remixer/agent.py except for one word in remix(): rewrite gets
the draft recipe, which has the swaps, not the original.

The agent looks up swaps with its one tool, `get_substitute`, and returns the
new ingredient list. Then `rewrite` updates the steps to match.

Run from the repo root: uv run python -m recipe_remixer.answer_key.agent
"""

import os
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from langsmith import traceable
from pydantic import BaseModel, Field

load_dotenv()

MODEL_NAME = os.getenv("REMIXER_MODEL", "openai:gpt-5-nano")
REASONING_EFFORT = os.getenv("REMIXER_REASONING_EFFORT", "medium")

# Swaps the app knows about, by diet.
SUBSTITUTES = {
    "vegetarian": {
        "chicken breast": "tofu",
        "chicken thighs": "tofu",
        "ground beef": "lentils",
        "bacon": "smoked tempeh",
        "shrimp": "chickpeas",
        "chicken stock": "vegetable stock",
        "fish sauce": "soy sauce",
    },
    "dairy free": {
        "butter": "olive oil",
        "milk": "oat milk",
        "heavy cream": "coconut milk",
        "parmesan": "nutritional yeast",
        "cheddar": "vegan cheese",
        "yogurt": "coconut yogurt",
    },
}

SYSTEM_PROMPT = """You change recipes to fit a diet in an app that stores the user's recipes.

For each ingredient that doesn't fit the diet, call get_substitute.
Return the new dish name and the full ingredient list. Put each swap in place of
the original and keep every other ingredient exactly as it was."""

REWRITE_PROMPT = """Update the steps of this recipe so they match its ingredient list.
Only change what's needed. Return one step per line, with no numbers.

{recipe}"""


class Ingredient(BaseModel):
    name: str = Field(description="Ingredient name without the amount, e.g. 'tofu'")
    quantity: str = Field(description="Amount, e.g. '2' or '200g'")


class Recipe(BaseModel):
    dish: str
    ingredients: list[Ingredient]
    steps: list[str]


class NewIngredients(BaseModel):
    dish: str
    ingredients: list[Ingredient]


_model_kwargs: dict[str, Any] = {}
if REASONING_EFFORT:
    _model_kwargs["reasoning_effort"] = REASONING_EFFORT

model = init_chat_model(MODEL_NAME, **_model_kwargs)


@tool
def get_substitute(ingredient: str, diet: str) -> str:
    """Look up a swap for one ingredient. diet is 'vegetarian' or 'dairy free'."""
    swap = SUBSTITUTES.get(diet.lower(), {}).get(ingredient.lower())
    return swap or f"No substitute found for {ingredient}."


agent = create_agent(
    model,
    [get_substitute],
    system_prompt=SYSTEM_PROMPT,
    response_format=ProviderStrategy(NewIngredients, strict=True),
    name="recipe_remixer",
)


# A plain function, so you can test this one step on its own.
@traceable
def rewrite(recipe: Recipe) -> list[str]:
    """Update a recipe's steps to match its ingredient list."""
    response = model.invoke(REWRITE_PROMPT.format(recipe=format_recipe(recipe)))
    return [line.strip() for line in response.text.splitlines() if line.strip()]


# traceable records message and recipe as the trace's inputs, so adding a
# trace to a dataset brings the recipe along.
@traceable(name="remix_request")
def remix(message: str, recipe: dict) -> dict:
    """Run the agent, then rewrite the steps. Returns the new recipe as
    readable text, plus the ingredient names and steps for the evals."""
    original = Recipe(**recipe)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"{message}\n\n{format_recipe(original)}"}]}
    )
    new = result["structured_response"]
    draft = Recipe(dish=new.dish, ingredients=new.ingredients, steps=original.steps)

    # The fix: rewrite the draft, which has the new ingredients. The buggy
    # version passed the original recipe, so rewrite never saw the swaps.
    steps = rewrite(draft)

    remixed = Recipe(dish=new.dish, ingredients=new.ingredients, steps=steps)
    return {
        "recipe": format_recipe(remixed),
        "ingredients": [i.name for i in remixed.ingredients],
        "steps": remixed.steps,
    }


def format_recipe(recipe: Recipe) -> str:
    """Render a recipe as plain text."""
    lines = [recipe.dish, "", "Ingredients:"]
    lines += [f"- {i.quantity} {i.name}" for i in recipe.ingredients]
    lines += ["", "Steps:"]
    lines += [f"{n}. {step}" for n, step in enumerate(recipe.steps, 1)]
    return "\n".join(lines)


if __name__ == "__main__":
    recipe = {
        "dish": "Chicken Stir Fry",
        "ingredients": [
            {"name": "chicken breast", "quantity": "2"},
            {"name": "broccoli", "quantity": "1 head"},
            {"name": "soy sauce", "quantity": "3 tbsp"},
            {"name": "rice", "quantity": "1 cup"},
        ],
        "steps": [
            "Cook the rice.",
            "Slice the chicken breast into strips.",
            "Stir fry the chicken in a hot pan until cooked through, about 6 minutes.",
            "Add the broccoli and soy sauce and cook 3 more minutes.",
            "Serve the chicken and broccoli over the rice.",
        ],
    }
    print(remix("Make this vegetarian", recipe)["recipe"])
