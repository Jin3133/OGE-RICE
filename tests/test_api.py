import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_stage_demand_endpoint(self):
        response = self.client.post(
            "/api/v1/stage-demand",
            json={
                "analysis_unit_id": "demo-01",
                "growth_stage": "分蘖期",
                "area_mu": 125.5,
                "quota_m3_per_mu": 42,
                "medium_threshold_m3": 1000,
                "high_threshold_m3": 5000,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reference_demand_m3"], 5271.0)

    def test_oge_endpoint_requires_server_configuration(self):
        response = self.client.post(
            "/api/v1/oge/cultivated-land",
            headers={"Authorization": "Bearer test-token"},
            json={"coverage_id": "coverage", "product_id": "product"},
        )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()

