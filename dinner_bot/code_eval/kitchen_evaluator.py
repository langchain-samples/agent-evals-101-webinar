"""Code evaluator for recipes that use ingredients the user doesn't have."""

# The product rule: every user is assumed to have these. Defined here instead
# of imported from the agent, so the eval doesn't inherit the agent's bug.
ASSUMED_STAPLES = {"salt", "pepper", "oil", "water"}

def uses_only_kitchen(inputs: dict, outputs: dict) -> dict:
    allowed = set(inputs["kitchen"]) | ASSUMED_STAPLES
    used = {i.lower() for i in outputs["ingredients"]}
    missing = used - allowed
    return {"score": not missing, "comment": f"Not in kitchen: {sorted(missing)}"}
