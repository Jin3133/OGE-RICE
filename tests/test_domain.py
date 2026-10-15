import unittest

from backend.app.domain import StageDemand, attention_level


class StageDemandTests(unittest.TestCase):
    def test_stage_demand(self):
        result = StageDemand(area_mu=125.5, quota_m3_per_mu=42).demand_m3
        self.assertEqual(result, 5271.0)

    def test_negative_area_is_rejected(self):
        with self.assertRaises(ValueError):
            StageDemand(area_mu=-1, quota_m3_per_mu=42).demand_m3

    def test_attention_level(self):
        self.assertEqual(attention_level(800, (1000, 5000)), "low")
        self.assertEqual(attention_level(2000, (1000, 5000)), "medium")
        self.assertEqual(attention_level(6000, (1000, 5000)), "high")


if __name__ == "__main__":
    unittest.main()

