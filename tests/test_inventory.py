from oge_main.data.inventory import paired_samples
from oge_main.data.paths import dataset_root


def test_official_dataset_has_900_pairs() -> None:
    assert len(paired_samples(dataset_root())) == 900

