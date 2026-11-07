"""Create a deterministic first-pass train/validation/test split."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from oge_main.data.inventory import paired_samples
from oge_main.data.paths import dataset_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=Path("data/splits/oge_farm_v1.json"))
    args = parser.parse_args()

    sample_ids = [sample.sample_id for sample in paired_samples(dataset_root())]
    random.Random(args.seed).shuffle(sample_ids)
    split = {
        "metadata": {
            "seed": args.seed,
            "warning": (
                "Initial random split. Replace with similarity-grouped split before "
                "reporting final accuracy."
            ),
        },
        "train": sample_ids[:720],
        "validation": sample_ids[720:810],
        "test": sample_ids[810:],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(split, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output}: 720 train / 90 validation / 90 test")


if __name__ == "__main__":
    main()

