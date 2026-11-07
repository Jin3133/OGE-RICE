"""Fast structural check for the local OGE Wuhan-1 dataset."""

from collections import Counter

import numpy as np
import rasterio

from oge_main.data.inventory import paired_samples
from oge_main.data.paths import dataset_root


def main() -> None:
    root = dataset_root()
    pairs = paired_samples(root)
    image_specs: Counter[tuple[object, ...]] = Counter()
    mask_specs: Counter[tuple[object, ...]] = Counter()
    mask_values: Counter[tuple[int, ...]] = Counter()

    for pair in pairs:
        with rasterio.open(pair.image) as src:
            image_specs[(src.width, src.height, src.count, src.dtypes[0])] += 1
        with rasterio.open(pair.mask) as src:
            values = tuple(int(value) for value in np.unique(src.read(1)))
            mask_specs[(src.width, src.height, src.count, src.dtypes[0])] += 1
            mask_values[values] += 1

    print(f"dataset={root}")
    print(f"paired_samples={len(pairs)}")
    print(f"image_specs={dict(image_specs)}")
    print(f"mask_specs={dict(mask_specs)}")
    print(f"mask_values={dict(mask_values)}")


if __name__ == "__main__":
    main()

