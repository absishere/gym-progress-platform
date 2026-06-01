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

    def test_multi_branch_signup_and_branch_selection(self):
        signup = self.client.post(
            "/api/auth/signup",
            json={
                "gym_name": "North Star Fitness",
                "owner_name": "Nisha Rao",
                "phone": "+91 90000 00001",
                "password": "owner-pass-123",
                "branches": ["Indiranagar", "Koramangala"],
            },
        )
        self.assertEqual(signup.status_code, 201)
        payload = signup.json()
        self.assertTrue(payload["gym"]["multi_branch_enabled"])
        self.assertEqual(len(payload["user"]["branches"]), 2)
        headers = {"Authorization": f"Bearer {payload['token']}"}
        second_branch = payload["user"]["branches"][1]
        selected = self.client.post("/api/auth/select-branch", headers=headers, json={"branch_id": second_branch["id"]})
        self.assertEqual(selected.status_code, 200)
        summary = self.client.get("/api/dashboard/summary", headers=headers)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["branch"]["id"], second_branch["id"])

    def test_owner_can_provision_staff_and_staff_cannot_manage_access(self):
        signup = self.client.post(
            "/api/auth/signup",
            json={
                "gym_name": "Daily Strength",
                "owner_name": "Owner Account",
                "phone": "+91 90000 00002",
                "password": "owner-pass-123",
                "branches": ["Main Floor"],
            },
        ).json()
        owner_headers = {"Authorization": f"Bearer {signup['token']}"}
        branch_id = signup["user"]["branches"][0]["id"]
        created = self.client.post(
            "/api/access/users",
            headers=owner_headers,
            json={
                "name": "Reception Desk",
                "phone": "+91 90000 00003",
                "role": "staff",
                "branch_ids": [branch_id],
                "temporary_password": "staff-pass-123",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["must_change_password"])
        login = self.client.post(
            "/api/auth/login",
            json={
                "workspace_slug": signup["gym"]["workspace_slug"],
                "phone": "+91 90000 00003",
                "password": "staff-pass-123",
            },
        )
        self.assertEqual(login.status_code, 200)
        staff_headers = {"Authorization": f"Bearer {login.json()['token']}"}
        self.assertEqual(self.client.get("/api/dashboard/summary", headers=staff_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/access/users", headers=staff_headers).status_code, 403)
        self.assertEqual(self.client.get("/api/integrations/whatsapp", headers=staff_headers).status_code, 403)
        changed = self.client.post(
            "/api/auth/change-password",
            headers=staff_headers,
            json={"current_password": "staff-pass-123", "new_password": "staff-pass-456"},
        )
        self.assertEqual(changed.status_code, 200)
        me = self.client.get("/api/auth/me", headers=staff_headers)
        self.assertFalse(me.json()["user"]["must_change_password"])
        self.assertEqual(self.client.post("/api/auth/logout", headers=staff_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers=staff_headers).status_code, 401)

    def test_owner_cannot_assign_a_user_to_another_gyms_branch(self):
        first = self.client.post(
            "/api/auth/signup",
            json={
                "gym_name": "First Gym",
                "owner_name": "First Owner",
                "phone": "+91 90000 00004",
                "password": "owner-pass-123",
                "branches": ["First Branch"],
            },
        ).json()
        second = self.client.post(
            "/api/auth/signup",
            json={
                "gym_name": "Second Gym",
                "owner_name": "Second Owner",
                "phone": "+91 90000 00005",
                "password": "owner-pass-123",
                "branches": ["Second Branch"],
            },
        ).json()
        response = self.client.post(
            "/api/access/users",
            headers={"Authorization": f"Bearer {first['token']}"},
            json={
                "name": "Invalid Assignment",
                "phone": "+91 90000 00006",
                "role": "trainer",
                "branch_ids": [second["user"]["branches"][0]["id"]],
                "temporary_password": "trainer-pass-123",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_each_gym_has_an_isolated_owner_managed_whatsapp_connection(self):
        first = self.client.post(
            "/api/auth/signup",
            json={
                "gym_name": "WhatsApp First Gym",
                "owner_name": "First Owner",
                "phone": "+91 90000 00007",
                "password": "owner-pass-123",
                "branches": ["Main Branch"],
            },
        ).json()
        second = self.client.post(
            "/api/auth/signup",
            json={
                "gym_name": "WhatsApp Second Gym",
                "owner_name": "Second Owner",
                "phone": "+91 90000 00008",
                "password": "owner-pass-123",
                "branches": ["Main Branch"],
            },
        ).json()
        first_headers = {"Authorization": f"Bearer {first['token']}"}
        second_headers = {"Authorization": f"Bearer {second['token']}"}
        configured = self.client.put(
            "/api/integrations/whatsapp",
            headers=first_headers,
            json={
                "business_account_id": "waba-1001",
                "phone_number_id": "phone-1001",
                "display_phone_number": "+91 90000 10001",
                "renewal_template_name": "membership_renewal_reminder",
            },
        )
        self.assertEqual(configured.status_code, 200)
        self.assertEqual(configured.json()["status"], "pending-verification")
        self.assertNotIn("access_token", configured.json())
        self.assertEqual(self.client.get("/api/integrations/whatsapp", headers=first_headers).json()["phone_number_id"], "phone-1001")
        self.assertEqual(self.client.get("/api/integrations/whatsapp", headers=second_headers).json()["status"], "not-configured")


if __name__ == "__main__":
    unittest.main()
