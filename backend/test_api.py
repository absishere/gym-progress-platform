import os
import tempfile
import unittest
from datetime import date, timedelta

from fastapi.testclient import TestClient


class GymPlatformApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.database.close()
        os.environ["GYM_DATABASE_PATH"] = cls.database.name
        from main import app

        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        os.unlink(cls.database.name)

    def test_seeded_members_and_expiring_view(self):
        members = self.client.get("/api/members").json()
        expiring = self.client.get("/api/members/expiring").json()
        self.assertGreaterEqual(len(members), 6)
        self.assertTrue(all(0 <= member["days_left"] <= 7 for member in expiring))

    def test_member_plan_and_progress_flow(self):
        created = self.client.post(
            "/api/members",
            json={
                "name": "Test Member",
                "phone": "+91 99999 99999",
                "email": "test@example.com",
                "package": "Monthly",
                "expires_on": (date.today() + timedelta(days=30)).isoformat(),
            },
        )
        self.assertEqual(created.status_code, 201)
        member_id = created.json()["id"]
        plan = self.client.post(
            "/api/plans/generate",
            json={"member_id": member_id, "weight_kg": 72, "height_cm": 174, "age": 30, "goal": "build-muscle"},
        )
        self.assertEqual(plan.status_code, 200)
        self.assertEqual(len(plan.json()["workouts"]), 4)
        progress = self.client.post(f"/api/progress/{member_id}", json={"weight_kg": 72})
        self.assertEqual(progress.status_code, 201)


if __name__ == "__main__":
    unittest.main()

