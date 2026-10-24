import os
import io
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
        self.original_officer_document_folder = smart_village.app.config[
            "OFFICER_DOCUMENT_FOLDER"
        ]
        self.original_officer_verification_provider = smart_village.app.config[
            "OFFICER_VERIFICATION_PROVIDER"
        ]
        smart_village.app.config.update(
            DATABASE=self.database,
            SECRET_KEY=secrets.token_hex(32),
            OFFICER_DOCUMENT_FOLDER=os.path.join(self.temp_dir.name, "private-officer-docs"),
            OFFICER_VERIFICATION_PROVIDER=None,
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
            OFFICER_DOCUMENT_FOLDER=self.original_officer_document_folder,
            OFFICER_VERIFICATION_PROVIDER=self.original_officer_verification_provider,
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
            "unapproved@example.test": 1,
            "citizen@example.test": None,
            "admin@example.test": None,
        }
        for email, village_id in assignments.items():
            password = secrets.token_urlsafe(32)
            self.passwords[email] = password
            is_inactive = email == "inactive@example.test"
            is_unapproved = email == "unapproved@example.test"
            role = {
                "citizen@example.test": "citizen",
                "admin@example.test": "system_admin",
            }.get(email, "village_officer")
            cursor = db.execute(
                """INSERT INTO users
                   (username, password_hash, role, name, email, assigned_village_id,
                    is_approved, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    email,
                    generate_password_hash(password),
                    role,
                    email.split("@", 1)[0],
                    email,
                    village_id,
                    int(not is_unapproved),
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

    def test_officer_can_sign_in_with_assigned_username(self):
        db = sqlite3.connect(self.database)
        db.execute(
            "UPDATE users SET username = ? WHERE email = ?",
            ("officer-a-user", "officer-a@example.test"),
        )
        db.commit()
        db.close()

        client = smart_village.app.test_client()
        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        response = client.post(
            "/api/auth/officer/login",
            json={"email": "officer-a-user", "password": self.passwords["officer-a@example.test"]},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["user"]["email"], "officer-a@example.test")

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
                dashboard = client.get("/officer/dashboard")
                self.assertIn(f"{village} dashboard".encode(), dashboard.data)
                self.assertIn(email.split("@", 1)[0].encode(), dashboard.data)
                if village == "Greenfield":
                    self.assertIn(b"Greenfield School Roof Repair", dashboard.data)
                    self.assertIn(b"Greenfield-only school", dashboard.data)
                    self.assertNotIn(b"Riverbend-only clinic", dashboard.data)
                elif village == "Riverbend":
                    self.assertIn(b"Riverbend Community Health Unit", dashboard.data)
                    self.assertIn(b"Riverbend-only clinic", dashboard.data)
                    self.assertNotIn(b"Greenfield-only school", dashboard.data)

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

    def test_existing_population_is_marked_demo_and_households_are_unavailable(self):
        db = sqlite3.connect(self.database)
        village = db.execute(
            """SELECT population_status, population_source, household_count,
                      household_status, state, taluk
               FROM villages WHERE id=1"""
        ).fetchone()
        db.close()
        self.assertEqual(village, (
            "Sample", "DEMO DATA - fictional sample", None, "Unavailable", "", ""
        ))

        page = self.client.get("/villages/1")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"2,450", page.data)
        self.assertIn(b"Sample", page.data)
        self.assertIn(b"DEMO DATA", page.data)
        self.assertIn(b"Total households", page.data)
        self.assertIn(b"Unavailable", page.data)
        self.assertIn(b"State: Not recorded", page.data)
        self.assertIn(b"Statistics last updated: Not recorded", page.data)

    def test_unavailable_population_is_not_exposed_as_a_number(self):
        csrf = self.login("officer-a@example.test")
        response = self.client.post(
            "/admin/villages/1/edit",
            data={
                "_csrf_token": csrf,
                "name": "Greenfield",
                "district": "North District",
                "population": "",
                "population_status": "Unavailable",
                "population_year": "",
                "population_source": "",
                "household_count": "",
                "household_status": "Unavailable",
                "household_year": "",
                "household_source": "",
                "schools": "3",
                "healthcare_centers": "1",
                "road_status": "Fair",
                "water_availability": "82",
                "agriculture": "Rice, vegetables",
            },
        )
        self.assertEqual(response.status_code, 302)

        public_page = self.client.get("/villages/1")
        self.assertEqual(public_page.status_code, 200)
        self.assertIn(b"Total population</span><strong>Unavailable", public_page.data)
        self.assertNotIn(b"2,450", public_page.data)

        api_response = self.client.get("/api/reports")
        self.assertEqual(api_response.status_code, 200)
        self.assertIsNone(api_response.get_json()["village"]["population"])
        self.assertEqual(
            api_response.get_json()["village"]["population_status"], "Unavailable"
        )
        self.assertIsNone(api_response.get_json()["village"]["population_source"])

    def test_officer_can_save_cited_population_and_household_data_for_assigned_village(self):
        csrf = self.login("officer-a@example.test")
        edit_page = self.client.get("/admin/villages/1/edit")
        self.assertEqual(edit_page.status_code, 200)
        self.assertIn(b"Population data source", edit_page.data)
        response = self.client.post(
            "/admin/villages/1/edit",
            data={
                "_csrf_token": csrf,
                "name": "Greenfield",
                "district": "North District",
                "state": "Sample State",
                "taluk": "North Taluk",
                "population": "3001",
                "population_status": "Official",
                "population_year": "2011",
                "population_source": "Census of India - test citation",
                "household_count": "700",
                "household_status": "Official",
                "household_year": "2011",
                "household_source": "Census of India - test household citation",
                "schools": "3",
                "healthcare_centers": "1",
                "road_status": "Fair",
                "water_availability": "82",
                "agriculture": "Rice, vegetables",
            },
        )
        self.assertEqual(response.status_code, 302)
        db = sqlite3.connect(self.database)
        village = db.execute(
            """SELECT state, taluk, population, population_year, population_source,
                      population_status, household_count, household_year,
                      household_source, household_status, statistics_updated_at
               FROM villages WHERE id=1"""
        ).fetchone()
        db.close()
        self.assertEqual(village[:10], (
            "Sample State", "North Taluk", 3001, 2011,
            "Census of India - test citation", "Official", 700, 2011,
            "Census of India - test household citation", "Official",
        ))
        self.assertIsNotNone(village[10])
        detail = self.client.get("/villages/1")
        self.assertIn(b"3,001", detail.data)
        self.assertIn(b"700", detail.data)
        self.assertIn(b"Official", detail.data)
        self.assertIn(b"2011", detail.data)
        self.assertIn(b"North Taluk", detail.data)

    def test_official_statistics_require_source_and_year_and_officers_are_village_scoped(self):
        csrf = self.login("officer-a@example.test")
        response = self.client.post(
            "/admin/villages/1/edit",
            data={
                "_csrf_token": csrf,
                "name": "Greenfield",
                "district": "North District",
                "population": "3001",
                "population_status": "Official",
                "population_year": "2011",
                "population_source": "",
                "household_count": "",
                "household_status": "Unavailable",
                "household_year": "",
                "household_source": "",
                "schools": "3",
                "healthcare_centers": "1",
                "road_status": "Fair",
                "water_availability": "82",
                "agriculture": "Rice, vegetables",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Official population data requires its source and data year.", response.data)
        db = sqlite3.connect(self.database)
        village = db.execute(
            "SELECT population, population_status FROM villages WHERE id=1"
        ).fetchone()
        db.close()
        self.assertEqual(village, (2450, "Sample"))

        csrf = self.login("officer-b@example.test")
        self.assertEqual(self.client.get("/admin/villages/1/edit").status_code, 403)
        self.assertEqual(
            self.client.post(
                "/admin/villages/1/edit",
                data={"_csrf_token": csrf},
            ).status_code,
            403,
        )

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

    def test_officer_reports_and_api_ignore_client_supplied_village(self):
        for email, village_id, village_name, other_village in (
            ("officer-a@example.test", 1, b"Greenfield", b"Riverbend"),
            ("officer-b@example.test", 2, b"Riverbend", b"Greenfield"),
        ):
            client = smart_village.app.test_client()
            csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
            login_response = client.post(
                "/api/auth/officer/login",
                json={"email": email, "password": self.passwords[email]},
                headers={"X-CSRF-Token": csrf},
            )
            self.assertEqual(login_response.status_code, 200)
            report = client.get("/reports?village=1&village_id=1")
            self.assertEqual(report.status_code, 200)
            self.assertIn(village_name, report.data)
            self.assertNotIn(other_village, report.data)
            api_report = client.get("/api/reports?village=1&village_id=1").get_json()
            self.assertEqual(api_report["village"]["id"], village_id)
            self.assertEqual(api_report["village"]["name"].encode(), village_name)
            self.assertEqual(api_report["village"]["population_status"], "Sample")
            self.assertEqual(api_report["village"]["population"], 2450 if village_id == 1 else 3180)
            self.assertEqual(api_report["village"]["household_count"], None)
            self.assertEqual(api_report["village"]["household_status"], "Unavailable")
            self.assertNotIn(other_village.decode(), str(api_report))
            self.assertIn("generated_at", api_report)

    def test_citizen_cannot_see_or_access_officer_reports(self):
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
        self.assertNotIn(b"Village reports", dashboard.data)
        self.assertNotIn(b">Reports<", dashboard.data)
        self.assertEqual(self.client.get("/reports").status_code, 403)
        self.assertEqual(self.client.get("/officer/reports").status_code, 403)
        self.assertEqual(self.client.get("/api/reports").status_code, 403)

    def test_inactive_or_unapproved_officer_cannot_log_in_and_citizen_cannot_open_officer_pages(self):
        csrf = self.client.get("/api/auth/csrf").get_json()["csrf_token"]
        for email in ("inactive@example.test", "unapproved@example.test"):
            with self.subTest(email=email):
                response = self.client.post(
                    "/api/auth/officer/login",
                    json={"email": email, "password": self.passwords[email]},
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

    def test_officer_login_shows_generic_errors_for_unknown_and_wrong_credentials(self):
        client = smart_village.app.test_client()
        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        for identifier, password in (
            ("missing@example.test", "wrong-password"),
            ("officer-a@example.test", "wrong-password"),
        ):
            with self.subTest(identifier=identifier):
                response = client.post(
                    "/api/auth/officer/login",
                    json={"email": identifier, "password": password},
                    headers={"X-CSRF-Token": csrf},
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(
                    response.get_json()["error"],
                    "Credentials were not recognized, or this account is not active.",
                )
                self.assertNotIn("password", response.get_json()["error"].lower())

        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        page = client.post(
            "/login/officer",
            data={
                "_csrf_token": csrf,
                "email": "officer-a@example.test",
                "password": "wrong-password",
            },
        )
        self.assertEqual(page.status_code, 200)
        self.assertIn(
            b"Credentials were not recognized, or this account is not active.",
            page.data,
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
        self.assertEqual(self.client.get("/reports").status_code, 403)
        self.assertEqual(self.client.get("/api/reports").status_code, 403)
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
        self.assertIn(b"Citizen Login", response.data)
        self.assertIn(b"Village Officer Login", response.data)
        self.assertNotIn(b"System Administrator</h2>", response.data)
        self.assertNotIn(b'href="/login/admin"', response.data)

    def submit_officer_registration(self, client=None, **overrides):
        client = client or smart_village.app.test_client()
        client.get("/register/officer")
        with client.session_transaction() as session:
            csrf_token = session["_csrf_token"]
        data = {
            "_csrf_token": csrf_token,
            "name": "Pending Officer",
            "officer_identifier": "EMP-1001",
            "mobile_number": "+1 555 123 4567",
            "email": "pending-officer@example.test",
            "state": "Sample State",
            "district": "Tampered District",
            "taluk": "North Taluk",
            "assigned_village_id": "1",
            "password": "very-secure-demo-password",
            "confirm_password": "very-secure-demo-password",
            "document_type": "Government ID card",
            "face_capture": "data:image/jpeg;base64,/9j/dGVzdA==",
            "consent": "yes",
        }
        identity_document = overrides.pop(
            "identity_document",
            (io.BytesIO(b"%PDF-1.4\nDemo ID content\n%%EOF"), "officer-id.pdf"),
        )
        data.update(overrides)
        response = client.post(
            "/register/officer",
            data={
                **data,
                "identity_document": identity_document,
            },
            content_type="multipart/form-data",
        )
        return client, response

    def officer_test_provider(self, **result_overrides):
        def verify(details, identity_document, selfie):
            self.assertTrue(identity_document.startswith(b"%PDF-"))
            self.assertTrue(selfie.startswith(b"\xff\xd8\xff"))
            result = {
                "id_verified": True,
                "face_verified": True,
                "liveness_verified": True,
                "authorized": True,
                "name": details["name"],
                "email": details["email"],
                "mobile_number": details["mobile_number"],
                "officer_identifier": details["officer_identifier"],
                "state": details["state"],
                "taluk": details["taluk"],
                "assigned_village_id": 2,
            }
            result.update(result_overrides)
            return result

        return verify

    def test_role_selection_officer_registration_and_auth_headers(self):
        response = self.client.get("/auth")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Citizen Login", response.data)
        self.assertIn(b"Create Account", response.data)
        self.assertIn(b"Village Officer Login", response.data)
        self.assertIn(b"Create Officer Account", response.data)
        self.assertIn(b'href="/login/citizen"', response.data)
        self.assertIn(b'href="/register/citizen"', response.data)
        self.assertIn(b'href="/login/officer"', response.data)
        self.assertIn(b'href="/register/officer"', response.data)
        self.assertIn(
            b"Registration is available only when authorized ID, face/liveness, and officer-registry verification services are configured.",
            response.data,
        )
        self.assertIn(b"Return to Public Dashboard", response.data)
        self.assertNotIn(b'href="/auth">Sign in</a>', response.data)

        for path in (
            "/login/citizen",
            "/register/citizen",
            "/login/officer",
            "/register/officer",
            "/login/admin",
        ):
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertEqual(page.status_code, 200)
                self.assertNotIn(b'href="/auth">Sign in</a>', page.data)
        registration = self.client.get("/register/officer")
        for field in (
            b'name="name"',
            b'name="mobile_number"',
            b'name="email"',
            b'name="officer_identifier"',
            b'name="state"',
            b'name="taluk"',
            b'name="assigned_village_id"',
            b"DEMO MODE",
            b"Officer Details",
            b"ID Verification",
            b"Face Verification",
            b"Registration unavailable in demo mode",
        ):
            self.assertIn(field, registration.data)
        self.assertNotIn(b"Submit for Approval", registration.data)
        self.assertNotIn(b'name="identity_document"', registration.data)
        self.assertEqual(registration.data.count(b"<li>"), 3)

    def test_officer_registration_fails_closed_when_verification_is_unconfigured(self):
        client, response = self.submit_officer_registration()
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"DEMO MODE", response.data)
        self.assertIn(b"No officer account was created.", response.data)
        db = sqlite3.connect(self.database)
        self.assertEqual(
            db.execute(
                "SELECT COUNT(*) FROM users WHERE email = 'pending-officer@example.test'"
            ).fetchone()[0],
            0,
        )
        self.assertEqual(
            db.execute("SELECT COUNT(*) FROM officer_registration_requests").fetchone()[0],
            0,
        )
        db.close()
        self.assertFalse(os.path.exists(os.path.join(
            self.temp_dir.name, "private-officer-docs"
        )))
        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        login = client.post(
            "/api/auth/officer/login",
            json={
                "email": "pending-officer@example.test",
                "password": "very-secure-demo-password",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(login.status_code, 401)

    def test_verified_officer_registers_active_and_uses_authoritative_village(self):
        smart_village.app.config["OFFICER_VERIFICATION_PROVIDER"] = self.officer_test_provider()
        client, response = self.submit_officer_registration()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login/officer")
        self.assertIn(b"Registration successful. You can now log in.", client.get(
            "/login/officer"
        ).data)

        db = sqlite3.connect(self.database)
        user = db.execute(
            """SELECT assigned_village_id, is_approved, is_active,
                      officer_identifier, password_hash
               FROM users WHERE email = 'pending-officer@example.test'"""
        ).fetchone()
        db.close()
        self.assertEqual(user[:4], (2, 1, 1, "EMP-1001"))
        self.assertNotEqual(user[4], "very-secure-demo-password")

        csrf = client.get("/api/auth/csrf").get_json()["csrf_token"]
        login = client.post(
            "/api/auth/officer/login",
            json={
                "email": "pending-officer@example.test",
                "password": "very-secure-demo-password",
            },
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.get_json()["user"]["assigned_village_id"], 2)
        self.assertEqual(client.get("/officer/dashboard").status_code, 200)
        self.assertIn(b"Riverbend dashboard", client.get("/officer/dashboard").data)

    def test_failed_id_face_liveness_and_authorization_never_create_accounts(self):
        failure_cases = (
            ({"id_verified": False}, b"Official ID verification failed"),
            ({"face_verified": False}, b"Face verification or liveness"),
            ({"liveness_verified": False}, b"Face verification or liveness"),
            ({"authorized": False}, b"not authorized as a Village Officer"),
        )
        for index, (failure, expected_message) in enumerate(failure_cases):
            with self.subTest(failure=failure):
                email = f"failed-{index}@example.test"
                smart_village.app.config["OFFICER_VERIFICATION_PROVIDER"] = (
                    self.officer_test_provider(**failure)
                )
                client, response = self.submit_officer_registration(email=email)
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected_message, response.data)
                db = sqlite3.connect(self.database)
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM users WHERE email = ?", (email,)).fetchone()[0],
                    0,
                )
                db.close()

    def test_duplicate_email_or_officer_id_is_rejected(self):
        smart_village.app.config["OFFICER_VERIFICATION_PROVIDER"] = self.officer_test_provider()
        client, created = self.submit_officer_registration()
        self.assertEqual(created.status_code, 302)
        _, duplicate_email = self.submit_officer_registration()
        self.assertEqual(duplicate_email.status_code, 200)
        self.assertIn(b"already exists for this email or officer ID", duplicate_email.data)

        _, duplicate_identifier = self.submit_officer_registration(
            email="different-officer@example.test"
        )
        self.assertEqual(duplicate_identifier.status_code, 200)
        self.assertIn(b"already exists for this email or officer ID", duplicate_identifier.data)
        db = sqlite3.connect(self.database)
        self.assertEqual(
            db.execute(
                "SELECT COUNT(*) FROM users WHERE role='village_officer' AND officer_identifier='EMP-1001'"
            ).fetchone()[0],
            1,
        )
        db.close()

    def test_invalid_id_document_is_rejected_without_storage(self):
        smart_village.app.config["OFFICER_VERIFICATION_PROVIDER"] = self.officer_test_provider()
        _, response = self.submit_officer_registration(
            identity_document=(io.BytesIO(b"not really a PDF"), "officer-id.pdf")
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Upload a valid PDF", response.data)
        db = sqlite3.connect(self.database)
        self.assertEqual(
            db.execute(
                "SELECT COUNT(*) FROM users WHERE email = 'pending-officer@example.test'"
            ).fetchone()[0],
            0,
        )
        db.close()

    def test_officer_login_accepts_username_and_has_password_visibility_control(self):
        response = self.client.get("/login/officer")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Official email or username", response.data)
        self.assertIn(b'id="login-identifier" name="email" type="text"', response.data)
        self.assertIn(b"data-password-toggle", response.data)
        self.assertIn(b"auth.js", response.data)

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
            "/gis-map",
            "/education",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 200)


if __name__ == "__main__":
    unittest.main()
