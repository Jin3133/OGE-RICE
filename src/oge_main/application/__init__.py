"""Application services that coordinate validated domain objects."""

from oge_main.application.assessment import AssessmentService
from oge_main.application.georeferencing import (
    AffineGeoreferencingResult,
    ControlPointResidual,
    GroundControlPoint,
    fit_affine_georeferencing,
)
from oge_main.application.repository import InMemoryDomainRepository
from oge_main.application.spatial_statistics import (
    SpatialStatisticsCommand,
    SpatialStatisticsJob,
    SpatialStatisticsService,
)

__all__ = [
    "AssessmentService",
    "AffineGeoreferencingResult",
    "ControlPointResidual",
    "GroundControlPoint",
    "InMemoryDomainRepository",
    "SpatialStatisticsCommand",
    "SpatialStatisticsJob",
    "SpatialStatisticsService",
    "fit_affine_georeferencing",
]
