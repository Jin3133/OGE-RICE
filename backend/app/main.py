"""禾灌智析业务后台的最小可运行版本。"""

import os

import httpx
from fastapi import FastAPI, Header, HTTPException
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


class OgeAnalysisRequest(BaseModel):
    coverage_id: str = Field(min_length=1, description="OGE 影像唯一标识")
    product_id: str = Field(min_length=1, description="OGE 产品类型编码")


class OgeAnalysisResponse(BaseModel):
    status: str
    service_name: str
    result: dict


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


@app.post("/api/v1/oge/cultivated-land", response_model=OgeAnalysisResponse)
async def run_oge_cultivated_land(
    payload: OgeAnalysisRequest,
    authorization: str | None = Header(default=None),
) -> OgeAnalysisResponse:
    """调用发布后的 OGE 个人算法服务。

    浏览器登录 Token 由请求头透传；AppKey 仅从服务端环境变量读取，避免写入
    前端代码或 Git 仓库。
    """
    service_name = os.getenv("OGE_CULTIVATED_LAND_SERVICE", "").strip()
    app_key = os.getenv("OGE_APP_KEY", "").strip()
    base_url = os.getenv("OGE_API_BASE_URL", "https://openge.org.cn").rstrip("/")

    if not service_name or not app_key:
        raise HTTPException(
            status_code=503,
            detail="OGE 服务尚未配置，请设置 OGE_CULTIVATED_LAND_SERVICE 和 OGE_APP_KEY",
        )
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 OGE 登录凭证")

    endpoint = (
        f"{base_url}/api/management/gp-service/process/{service_name}/api"
    )
    headers = {
        "Authorization": authorization,
        "appKey": app_key,
        "Content-Type": "application/json",
    }
    body = {
        "coverageID": payload.coverage_id,
        "productID": payload.product_id,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"OGE 服务返回 {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="无法连接 OGE 服务") from exc

    return OgeAnalysisResponse(
        status="submitted",
        service_name=service_name,
        result=response.json(),
    )
