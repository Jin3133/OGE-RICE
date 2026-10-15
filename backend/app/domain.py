"""可独立验证的灌溉需水业务计算规则。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StageDemand:
    area_mu: float
    quota_m3_per_mu: float

    @property
    def demand_m3(self) -> float:
        """分阶段参考灌溉需水量：水稻面积 × 对应阶段灌溉定额。"""
        if self.area_mu < 0:
            raise ValueError("水稻面积不能为负数")
        if self.quota_m3_per_mu < 0:
            raise ValueError("阶段灌溉定额不能为负数")
        return self.area_mu * self.quota_m3_per_mu


def attention_level(demand_m3: float, thresholds: tuple[float, float]) -> str:
    """根据用户确认的两个阈值返回低、中、高关注等级。"""
    medium, high = thresholds
    if medium < 0 or high <= medium:
        raise ValueError("关注等级阈值必须满足 0 <= medium < high")
    if demand_m3 >= high:
        return "high"
    if demand_m3 >= medium:
        return "medium"
    return "low"

