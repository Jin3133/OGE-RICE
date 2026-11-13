"""Check whether OGE's S2_MSIL2A product exposes the Sentinel-2 SCL band.

Status on 2026-11-04: the map task did not return within one minute and was stopped.
Do not use SCL in the stable workflow until this test succeeds or product metadata
confirms the band name exposed by OGE.
"""

import oge


oge.initialize()
service = oge.Service()
image = service.getCoverage(
    coverageID="T50RKU_20251005T025529",
    productID="S2_MSIL2A",
)
scl = service.getProcess("Coverage.selectBands").execute(image, ["SCL"])
scl.styles(
    {
        "min": 0,
        "max": 11,
        "palette": [
            "#000000",
            "#ff0000",
            "#2f2f2f",
            "#643200",
            "#00a000",
            "#ffe65a",
            "#0000ff",
            "#808080",
            "#c0c0c0",
            "#ffffff",
            "#64c8ff",
            "#ff96ff",
        ],
    }
).getMap("HGZ_JX_SCL_20251005")
oge.mapclient.centerMap(114.225, 30.25, 10)
