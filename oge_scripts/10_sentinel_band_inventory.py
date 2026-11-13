"""Inspect the bands exposed by one OGE Sentinel-2 L2A scene."""

import oge


oge.initialize()
service = oge.Service()
image = service.getCoverage(
    coverageID="T50RKU_20251005T025529",
    productID="S2_MSIL2A",
)
band_names = service.getProcess("Coverage.bandNames").execute(image)
band_names.log("S2_MSIL2A_BAND_NAMES")
oge.mapclient.centerMap(114.225, 30.25, 10)
