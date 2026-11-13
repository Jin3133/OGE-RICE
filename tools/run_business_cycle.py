"""Run the minimum business cycle from a JSON task and write a versioned result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oge_main.business import run_assessment


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = json.loads(args.task.read_text(encoding="utf-8"))
    result = run_assessment(task)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "task_id": result["task_id"],
        "result_version": result["result_version"],
        "total_candidate_area_mu": result["total_candidate_area_mu"],
        "total_reference_irrigation_demand_m3": result[
            "total_reference_irrigation_demand_m3"
        ],
        "output": str(args.output.resolve()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
