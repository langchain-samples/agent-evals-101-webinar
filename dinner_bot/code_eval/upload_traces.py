"""Upload 25 saved Dinner Bot traces to your LangSmith project.

The traces in traces.json are real runs of the buggy Dinner Bot. This script
gives them fresh IDs and spreads them over the last day, so they look like
recent traffic. Select them in LangSmith and add them to a dataset.

Run from the repo root: uv run python -m dinner_bot.code_eval.upload_traces
"""

import argparse
import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client, uuid7

load_dotenv()

TRACES_FILE = Path(__file__).parent / "traces.json"

# LangSmith rejects runs that start more than 24 hours ago, so stay under a day.
MAX_DAYS = 0.95


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.getenv("LANGSMITH_PROJECT", "dinner-bot"))
    parser.add_argument("--days", type=float, default=MAX_DAYS, help="Spread traces over this many days")
    args = parser.parse_args()

    if args.days > MAX_DAYS:
        parser.error(f"--days can't be more than {MAX_DAYS}. LangSmith rejects older runs.")

    runs = json.loads(TRACES_FILE.read_text())

    # New IDs so uploading twice makes new traces instead of clashing with old ones.
    id_map = {run["id"]: str(uuid7()) for run in runs}

    traces: dict[str, list[dict]] = {}
    for run in runs:
        traces.setdefault(run["trace_id"], []).append(run)

    client = Client()
    now = datetime.now(timezone.utc)
    window = timedelta(days=args.days)

    for trace_runs in traces.values():
        # Move the whole trace to a random time in the window. Every run in it
        # shifts by the same amount, so the timing inside the trace is unchanged.
        root = next(r for r in trace_runs if r["parent_run_id"] is None)
        old_start = datetime.fromisoformat(root["start_time"])
        new_start = now - window + random.uniform(0, 1) * (window - timedelta(minutes=5))
        shift = new_start - old_start

        # dotted_order is how LangSmith nests runs: the parent's order plus this
        # run's start time and ID.
        by_id = {run["id"]: run for run in trace_runs}
        dotted_orders = {}

        def dotted_order(run: dict) -> str:
            if run["id"] not in dotted_orders:
                start = datetime.fromisoformat(run["start_time"]) + shift
                segment = start.strftime("%Y%m%dT%H%M%S%fZ") + id_map[run["id"]]
                parent = by_id.get(run["parent_run_id"])
                dotted_orders[run["id"]] = (
                    f"{dotted_order(parent)}.{segment}" if parent else segment
                )
            return dotted_orders[run["id"]]

        # Parents first, so a child never arrives before the run it belongs to.
        for run in sorted(trace_runs, key=lambda r: dotted_order(r).count(".")):
            start = datetime.fromisoformat(run["start_time"]) + shift
            end = datetime.fromisoformat(run["end_time"]) + shift if run["end_time"] else None
            new_id = id_map[run["id"]]
            parent_id = id_map.get(run["parent_run_id"])

            client.create_run(
                id=new_id,
                trace_id=id_map[run["trace_id"]],
                parent_run_id=parent_id,
                dotted_order=dotted_order(run),
                name=run["name"],
                run_type=run["run_type"],
                inputs=run["inputs"],
                outputs=run["outputs"],
                error=run["error"],
                extra=run["extra"],
                tags=run["tags"],
                start_time=start,
                end_time=end,
                project_name=args.project,
            )

    client.flush()
    print(f"Uploaded {len(traces)} traces to '{args.project}'.")


if __name__ == "__main__":
    main()
