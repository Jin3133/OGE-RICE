from oge_main.data.inventory import natural_sample_key, paired_samples
from oge_main.data.paths import dataset_root


def test_official_dataset_has_900_pairs() -> None:
    assert len(paired_samples(dataset_root())) == 900


def test_natural_sample_key_supports_business_ids() -> None:
    values = ["yuelai_r01024_c00000", "img10", "img2", "yuelai_r00512_c00000"]

    assert sorted(values, key=natural_sample_key) == [
        "img2",
        "img10",
        "yuelai_r00512_c00000",
        "yuelai_r01024_c00000",
    ]

