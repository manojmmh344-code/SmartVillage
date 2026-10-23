import os
import secrets
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

import app as smart_village


class VillageOfficerAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = smart_village.app.config["DATABASE"]
        self.original_secret = smart_village.app.config["SECRET_KEY"]
        self.original_testing = smart_village.app.testing
        self.database = os.path.join(self.temp_dir.name, "test.db")
        smart_village.app.config.update(
            DATABASE=self.database,
            SECRET_KEY=secrets.token_hex(32),
            TESTING=True,
        )
        smart_village.init_db()
        self.passwords = {}
        self.officer_ids = {}
        self.complaint_ids = {}
        self.citizen_id = None
        self._create_test_accounts_and_records()
        self.client = smart_village.app.test_client()

    def tearDown(self):
        smart_village.app.config.update(
            DATABASE=self.original_database,
            SECRET_KEY=self.original_secret,
            TESTING=self.original_testing,
        )
        self.temp_dir.cleanup()

    def _create_test_accounts_and_records(self):
        db = sqlite3.connect(self.database)
        db.execute("PRAGMA foreign_keys = ON")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        assignments = {
            "officer-a@example.test": 1,
            "officer-b@example.test": 2,
            "officer-c@example.test": 3,
            "inactive@example.test": 1,
            "citizen@example.test": None,
            "admin@example.test": None,
        }
        for email, village_id in assignments.items():
            password = secrets.token_urlsafe(32)
            self.passwords[email] = password
            is_inactive = email == "inactive@example.test"
            role = {
                "citizen@example.test": "citizen",
                "admin@example.test": "system_admin",
            }.get(email, "village_officer")
            cursor = db.execute(
                """INSERT INTO users
                   (username, password_hash, role, name, email, assigned_village_id,
                    is_approved, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                (
                    email,
                    generate_password_hash(password),
                    role,
                    email.split("@", 1)[0],
                    email,
                    village_id,
                    int(not is_inactive),
                    now,
                    now,
                ),
            )
            if role == "village_officer":
                self.officer_ids[email] = cursor.lastrowid
            elif role == "citizen":
                self.citizen_id = cursor.lastrowid

        for village_id, complaint_id in ((1, "TEST-GREENFIELD"), (2, "TEST-RIVERBEND")):
            cursor = db.execute(
                """INSERT INTO complaints
                   (complaint_id, tracking_token_hash, citizen_name, village_id,
                    owner_user_id, category, title, description, location_description,
                    status, created_at, updated_at)
                   VALUES (?, ?, 'Test Citizen', ?, NULL, 'Other', ?, 'Test complaint description',
                           'Test location', 'Pending', ?, ?)""",
                (
                    complaint_id,
                    secrets.token_hex(32),
                    village_id,
                    f"Complaint for village {village_id}",
                    now,
                    now,
                ),
            )
            self.complaint_ids[village_id] = cursor.lastrowid

        db.execute(
            "UPDATE complaints SET owner_user_id = ? WHERE id = ?",
            (self.citizen_id, self.complaint_ids[1]),
        )
        db.execute(
            """INSERT INTO facilities
               (village_id, facility_name, facility_type, latitude, longitude,
                address, description, coordinates_verified)
               VALUES (1, 'Greenfield-only school', 'School', 12.9716, 77.5946, '', '', 1)"""
        )
        db.execute(
            """INSERT INTO facilities
               (village_id, facility_name, facility_type, latitude, longitude,
                address, description, coordinates_verified)
               VALUES (2, 'Riverbend-only clinic', 'Healthcare Center', 10, 20, '', '', 1)"""
        )
        db.execute(
            """UPDATE villages SET latitude=12.9716, longitude=77.5946,
               coordinates_verified=1 WHERE id=1"""
        )
        db.commit()
        db.close()

    def login(self, email):
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post(
            "/api/auth/officer/login",
            json={"email": email, "password": self.passwords[email]},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["assigned_village_id"], {
            "officer-a@example.test": 1,
            "officer-b@example.test": 2,
            "officer-c@example.test": 3,
        }[email])
        return response.get_json()["csrf_token"]

    def test_three_officers_are_routed_to_their_assigned_villages(self):
        expected = {
            "officer-a@example.test": "Greenfield",
            "officer-b@example.test": "Riverbend",
            "officer-c@example.test": "Sunrise Hamlet",
        }
        for email, village in expected.items():
            with self.subTest(email=email):
                client = smart_village.app.test_client()
                csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
                response = client.post(
                    "/login/officer",
                    data={"email": email, "password": self.passwords[email], "_csrf_token": csrf},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.headers["Location"], "/officer/dashboard")
                self.assertIn(
                    f"{village} dashboard".encode(),
                    client.get("/officer/dashboard").data,
                )

    def test_officer_cannot_access_or_reassign_other_village_projects(self):
        csrf = self.login("officer-a@example.test")
        self.assertEqual(self.client.get("/officer/projects/2/edit").status_code, 403)
        self.assertEqual(self.client.get("/admin/facilities/1/edit").status_code, 403)
        response = self.client.post(
            "/officer/projects/1/edit",
            data={
                "_csrf_token": csrf,
                "name": "Attempted reassignment",
                "village_id": "2",
                "department": "Public Works",
                "budget": "10",
                "start_date": "2026-01-01",
                "expected_completion_date": "2026-02-01",
                "status": "Planned",
            },
        )
        self.assertEqual(response.status_code, 403)
        db = sqlite3.connect(self.database)
        assigned_village = db.execute("SELECT village_id FROM projects WHERE id=1").fetchone()[0]
        db.close()
        self.assertEqual(assigned_village, 1)

    def test_officer_can_update_a_complaint_in_their_own_village(self):
        csrf = self.login("officer-a@example.test")
        response = self.client.post(
            f"/officer/complaints/{self.complaint_ids[1]}",
            data={"_csrf_token": csrf, "status": "In Progress", "remarks": "Assigned"},
        )
        self.assertEqual(response.status_code, 302)
        db = sqlite3.connect(self.database)
        status = db.execute(
            "SELECT status FROM complaints WHERE id=?", (self.complaint_ids[1],)
        ).fetchone()[0]
        db.close()
        self.assertEqual(status, "In Progress")

    def test_officer_statistics_update_cannot_change_verified_map_coordinates(self):
        csrf = self.login("officer-a@example.test")
        response = self.client.post(
            "/admin/villages/1/edit",
            data={
                "_csrf_token": csrf,
                "name": "Greenfield",
                "district": "North District",
                "population": "2451",
                "schools": "3",
                "healthcare_centers": "1",
                "road_status": "Fair",
                "water_availability": "82",
                "agriculture": "Rice, vegetables",
                "latitude": "-50",
                "longitude": "-100",
                "coordinates_verified": "yes",
            },
        )
        self.assertEqual(response.status_code, 302)
        db = sqlite3.connect(self.database)
        village = db.execute(
            "SELECT population, latitude, longitude, coordinates_verified FROM villages WHERE id=1"
        ).fetchone()
        db.close()
        self.assertEqual(village, (2451, 12.9716, 77.5946, 1))

    def test_officer_cannot_view_or_update_another_villages_complaint(self):
        csrf = self.login("officer-b@example.test")
        response = self.client.post(
            f"/officer/complaints/{self.complaint_ids[1]}",
            data={"_csrf_token": csrf, "status": "Resolved", "remarks": "Unauthorized"},
        )
        self.assertEqual(response.status_code, 403)
        db = sqlite3.connect(self.database)
        status = db.execute(
            "SELECT status FROM complaints WHERE id=?", (self.complaint_ids[1],)
        ).fetchone()[0]
        db.close()
        self.assertEqual(status, "Pending")
        self.assertEqual(
            self.client.get(
                f"/admin/complaints/{self.complaint_ids[1]}/photo"
            ).status_code,
            403,
        )

    def test_officer_gis_analytics_reports_and_public_lists_are_village_scoped(self):
        self.login("officer-a@example.test")
        gis = self.client.get("/gis-map")
        self.assertEqual(gis.status_code, 200)
        self.assertIn(b"Greenfield GIS Map", gis.data)
        self.assertIn(b"Greenfield-only school", gis.data)
        self.assertNotIn(b"Riverbend-only clinic", gis.data)
        self.assertIn(b"[12.9716, 77.5946]", gis.data)
        self.assertEqual(self.client.get("/gis-map?village=2").status_code, 403)
        self.assertEqual(self.client.get("/villages/2").status_code, 403)
        for route in ("/analytics", "/reports", "/", "/villages", "/projects"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Greenfield", response.data)
                self.assertNotIn(b"Riverbend", response.data)

    def test_inactive_officer_cannot_log_in_and_citizen_cannot_open_officer_pages(self):
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post(
            "/api/auth/officer/login",
            json={
                "email": "inactive@example.test",
                "password": self.passwords["inactive@example.test"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("officer-a@example.test", self.passwords)

        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post(
            "/api/auth/citizen/login",
            json={
                "email": "citizen@example.test",
                "password": self.passwords["citizen@example.test"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/officer/dashboard").status_code, 403)
        self.assertEqual(self.client.get("/officer/reports").status_code, 403)
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        self.assertEqual(
            self.client.post(
                "/api/admin/officers",
                json={},
                headers={"X-CSRF-Token": csrf},
            ).status_code,
            403,
        )

    def test_citizen_can_access_only_their_own_complaints(self):
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post(
            "/api/auth/citizen/login",
            json={
                "email": "citizen@example.test",
                "password": self.passwords["citizen@example.test"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        dashboard = self.client.get("/citizen/dashboard")
        self.assertIn(b"Complaint for village 1", dashboard.data)
        self.assertNotIn(b"Complaint for village 2", dashboard.data)

    def test_only_administrator_can_reset_officer_password(self):
        officer_client = smart_village.app.test_client()
        csrf = officer_client.get("/api/auth/csrf").get_json()["csrf_token"]
        officer_client.post(
            "/api/auth/officer/login",
            json={
                "email": "officer-a@example.test",
                "password": self.passwords["officer-a@example.test"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post(
            "/api/auth/admin/login",
            json={
                "email": "admin@example.test",
                "password": self.passwords["admin@example.test"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        new_password = secrets.token_urlsafe(32)
        response = self.client.post(
            f"/admin/officers/{self.officer_ids['officer-a@example.test']}/reset-password",
            data={
                "_csrf_token": response.get_json()["csrf_token"],
                "password": new_password,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(officer_client.get("/officer/dashboard").status_code, 302)
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post(
            "/api/auth/officer/login",
            json={
                "email": "officer-a@example.test",
                "password": self.passwords["officer-a@example.test"],
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 401)
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = self.client.post(
            "/api/auth/officer/login",
            json={"email": "officer-a@example.test", "password": new_password},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)

    def test_public_login_shows_only_citizen_and_officer_options(self):
        response = self.client.get("/auth")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Citizen login", response.data)
        self.assertIn(b"Village Officer login", response.data)
        self.assertNotIn(b"System Administrator</h2>", response.data)
        self.assertNotIn(b'href="/login/admin"', response.data)

    def test_invalid_officer_village_assignment_is_rejected_by_database(self):
        db = sqlite3.connect(self.database)
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute(
                """INSERT INTO users
                   (password_hash, role, name, is_approved, is_active, created_at, updated_at)
                   VALUES ('hash', 'village_officer', 'Invalid', 1, 1, 'now', 'now')"""
            )
        db.close()

    def test_existing_public_modules_remain_available(self):
        for route in (
            "/",
            "/villages",
            "/projects",
            "/analytics",
            "/reports",
            "/gis-map",
            "/education",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)


if __name__ == "__main__":
    unittest.main()
