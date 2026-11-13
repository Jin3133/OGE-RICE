"""OGE smoke test for Wuhan-1 platform segmentation models.

Verified on 2026-11-07:
- The official case coverage can be loaded and displayed.
- Both whu-cultivated_land and whu01_water were accepted by the API, but
  remained in server-side execution without producing their result layer.
"""

import oge

oge.initialize()
service = oge.Service.initialize()

coverage = service.getCoverage(
    coverageID="OGE_Case_Data/LJ3II_MSS_E114.45_N30.66_20250127_Slice1.tif"
)

# Change the process ID to test another platform model.
process_id = "whu-cultivated_land"
result = service.getProcess(process_id).execute(coverage)

coverage.styles(
    {"bands": ["B3", "B2", "B1"], "min": 0, "max": 255}
).getMap("wuhan1_coverage")

result.styles(
    strokeColor="#FF3B30",
    strokeWidth=2.0,
    fill=False,
    outline=True,
).getMap("model_result")

oge.mapclient.centerObject(result)
