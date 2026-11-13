# OGE script layout

OGE currently presents code scripts as a flat list. The repository therefore keeps the
full engineering structure, while scripts copied to OGE use a numeric prefix and remain
self-contained.

## Platform naming convention

| Prefix | Responsibility | Planned platform script |
| --- | --- | --- |
| `00` | Project configuration and asset checks | `00_hgz_asset_check.py` |
| `10` | Imagery search and quality screening | `10_hgz_imagery_screening.py` |
| `20` | Preprocessing and feature construction | `20_hgz_preprocess_features.py` |
| `30` | Rice model inference | `30_hgz_rice_inference.py` |
| `40` | Post-processing and area statistics | `40_hgz_area_statistics.py` |
| `50` | Weather/context extraction | `50_hgz_weather_context.py` |
| `60` | Result export and service publication | `60_hgz_publish_results.py` |
| `90` | Disposable experiments | `90_hgz_experiment_*.py` |

`hgz` is the stable project prefix for 禾灌智析. Do not encode a satellite or region in
the permanent workflow name; these are task parameters and may change after data screening.

## Rules for OGE scripts

1. Every script begins with a compact `CONFIG` block containing product IDs, coverage IDs,
   analysis bounds and output names.
2. Every script is independently runnable in the OGE development center. It must not rely
   on importing another user script because the platform does not expose a package tree.
3. Shared logic is developed and tested locally first. Only the thin OGE adapter and the
   verified workflow are copied into the platform script.
4. Stable user assets use `myData/hgz_*`; temporary map layers use `HGZ_TMP_*`; published
   outputs use `HGZ_RICE_*`.
5. A platform script is reproducible only after its inputs are registered in
   `data/catalog/oge_asset_registry.csv` and its experiment is logged.

## Data persistence on OGE

- Raster input/output: GeoTIFF, referenced as `myData/<name>.tif`.
- Vector boundaries/samples: GeoJSON, referenced as `myData/<name>.geojson`.
- Catalogs/configuration/statistics: store through **Other data**, referenced as
  `myData/<name>.<extension>`.
- Platform-native imagery remains referenced by `productID` and `coverageID`; it is not
  duplicated merely to create a local copy.
- Long-running derived products should be exported to batch results and then registered.
  Interactive map layers are previews, not durable project assets.

