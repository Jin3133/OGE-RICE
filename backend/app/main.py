"""禾灌智析业务后台的最小可运行版本。"""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .domain import StageDemand, attention_level


app = FastAPI(
    title="禾灌智析 API",
    description="连接 OGE 遥感成果与分阶段参考灌溉需水业务计算。",
    version="0.1.0",
)


class DemandRequest(BaseModel):
    analysis_unit_id: str = Field(min_length=1, description="分析单元唯一编号")
    growth_stage: str = Field(min_length=1, description="水稻生育阶段")
    area_mu: float = Field(ge=0, description="水稻面积（亩）")
    quota_m3_per_mu: float = Field(ge=0, description="阶段灌溉定额（立方米/亩）")
    medium_threshold_m3: float = Field(ge=0, description="中关注阈值（立方米）")
    high_threshold_m3: float = Field(gt=0, description="高关注阈值（立方米）")


class DemandResponse(BaseModel):
    analysis_unit_id: str
    growth_stage: str
    area_mu: float
    quota_m3_per_mu: float
    reference_demand_m3: float
    attention_level: str
    calculation: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "oge-rice-backend"}


@app.post("/api/v1/stage-demand", response_model=DemandResponse)
def calculate_stage_demand(payload: DemandRequest) -> DemandResponse:
    demand = StageDemand(
        area_mu=payload.area_mu,
        quota_m3_per_mu=payload.quota_m3_per_mu,
    ).demand_m3
    level = attention_level(
        demand,
        (payload.medium_threshold_m3, payload.high_threshold_m3),
    )
    return DemandResponse(
        analysis_unit_id=payload.analysis_unit_id,
        growth_stage=payload.growth_stage,
        area_mu=payload.area_mu,
        quota_m3_per_mu=payload.quota_m3_per_mu,
        reference_demand_m3=demand,
        attention_level=level,
        calculation="水稻面积（亩）× 当前生育阶段灌溉定额（立方米/亩）",
    )

