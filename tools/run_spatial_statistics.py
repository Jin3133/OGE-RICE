"""Generate one versioned AreaStatistic from raster masks and a boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oge_main.application import SpatialStatisticsJob, SpatialStatisticsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    job_path = args.job.resolve()
    job = SpatialStatisticsJob.model_validate_json(job_path.read_text(encoding="utf-8"))
    result = SpatialStatisticsService().calculate(
        job.to_command(base_directory=job_path.parent)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "statistic_id": result.statistic_id,
                "candidate_area_m2": result.candidate_area_m2,
                "valid_observation_area_m2": result.valid_observation_area_m2,
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
