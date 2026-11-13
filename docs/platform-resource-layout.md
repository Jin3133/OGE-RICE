# OGE resource layout for 禾灌智析

## Storage decision

The OGE development center supports three persistent user-data categories:

- raster data: GeoTIFF (`tif`/`tiff`), maximum displayed upload size 2 GB;
- vector data: GeoJSON, maximum displayed upload size 2 GB;
- other data: generic project files with automatically detected file/data types.

Uploaded spatial assets are called with the `myData/` prefix. The project will therefore
store boundaries, samples, selected derived rasters and machine-readable manifests as OGE
user assets instead of leaving them only as search results or map layers.

Platform-native scenes are kept by stable `productID + coverageID` references. The asset
registry is their durable directory; duplicating every platform scene would waste storage
without improving reproducibility.

## Logical project directory

Although OGE displays a flat resource list, resource prefixes enforce this logical layout:

```text
HGZ_RICE/
  00_catalog/       hgz_project_manifest.json, hgz_imagery_inventory.csv
  10_boundaries/    hgz_demo_boundary.geojson, hgz_analysis_units.geojson
  20_samples/       hgz_rice_reference_samples.geojson
  30_imagery/       platform productID + coverageID references
  40_features/      selected reusable feature rasters
  50_predictions/   hgz_rice_prediction_<task>.tif
  60_statistics/    hgz_area_statistics_<task>.csv
  70_services/      published OGE workflow/service identifiers
```

The physical platform names remain flat (`hgz_*`); the registry records their logical role.

## Sources of truth

- OGE: platform-native identifiers, uploaded spatial assets, batch results and services.
- Git: source code, schemas, catalogs, parameters, experiment records and Web/backend code.
- A layer shown by `getMap()` is a preview, not saved data.
- A scene enters the core dataset only after a small-area read or visualization succeeds and
  `verified=true` is recorded.

## Development sequence

1. Screen available high-resolution products and choose one demonstration region.
2. Save the final scene inventory and analysis boundary in the registry/OGE user assets.
3. Run one platform model as the baseline and export its prediction.
4. Create independent validation samples and compare candidate models.
5. Freeze the selected data/model version before area statistics and Web API development.

