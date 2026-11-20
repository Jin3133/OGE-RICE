"""Run durable model-pipeline operations outside the FastAPI process."""

from __future__ import annotations

import argparse
import time

from oge_main.application.model_pipeline import (
    claim_next_model_pipeline_operation,
    execute_model_pipeline_operation,
)
from oge_main.infrastructure.database.session import (
    DatabaseSettings,
    create_session_factory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    factory = create_session_factory(DatabaseSettings.from_environment())
    while True:
        operation_id = claim_next_model_pipeline_operation(factory)
        if operation_id is None:
            if args.once:
                return
            time.sleep(args.poll_seconds)
            continue
        print(f"processing {operation_id}", flush=True)
        execute_model_pipeline_operation(factory, operation_id)
        print(f"finished {operation_id}", flush=True)
        if args.once:
            return


if __name__ == "__main__":
    main()
