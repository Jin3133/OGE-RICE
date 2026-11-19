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
    task_path = args.task.resolve()
    task = json.loads(task_path.read_text(encoding="utf-8"))
    for unit in task.get("management_units", []):
        mask_path = Path(unit["candidate_mask_path"])
        if not mask_path.is_absolute():
            unit["candidate_mask_path"] = str((task_path.parent / mask_path).resolve())
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
