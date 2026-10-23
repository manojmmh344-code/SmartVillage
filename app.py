import os
import secrets
import sqlite3
import hashlib
import math
import re
import time
from datetime import date, datetime, timezone
from functools import wraps
from hmac import compare_digest

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "complaints")
COMPLAINT_CATEGORIES = (
    "Drinking Water",
    "Roads and Transportation",
    "Electricity",
    "Waste Management",
    "Drainage and Sanitation",
    "Education",
    "Healthcare",
    "Agriculture",
    "Other",
)
COMPLAINT_STATUSES = ("Pending", "In Progress", "Resolved", "Rejected")
FACILITY_TYPES = (
    "School",
    "Healthcare Center",
    "Drinking Water Facility",
    "Roads and Infrastructure Project",
    "Government Service Center",
)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SMART_VILLAGE_SECRET") or secrets.token_hex(32),
    DATABASE=DATABASE,
    MAX_CONTENT_LENGTH=6 * 1024 * 1024,
    COMPLAINT_UPLOAD_FOLDER=UPLOAD_FOLDER,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SMART_VILLAGE_COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)

VILLAGE_SAMPLES = [
    ("Greenfield", "North District", 2450, 3, 1, "Fair", 82, "Rice, vegetables"),
    ("Riverbend", "North District", 3180, 4, 2, "Good", 96, "Rice, fisheries"),
    ("Sunrise Hamlet", "East District", 1760, 2, 1, "Needs improvement", 58, "Millet, pulses"),
    ("Meadowbrook", "West District", 2890, 3, 1, "Good", 91, "Wheat, dairy"),
    ("Hillview", "South District", 1320, 1, 0, "Fair", 67, "Tea, spices"),
]

PROJECT_SAMPLES = [
    ("Greenfield School Roof Repair", "Greenfield", "Education", 850000, "2026-01-15", "2026-08-30", "In Progress"),
    ("Riverbend Community Health Unit", "Riverbend", "Health", 2400000, "2025-11-01", "2026-06-30", "In Progress"),
    ("Sunrise Hamlet Water Connection", "Sunrise Hamlet", "Water Resources", 1250000, "2026-02-01", "2026-09-15", "Planned"),
    ("Meadowbrook Road Resurfacing", "Meadowbrook", "Public Works", 1750000, "2025-08-10", "2026-03-30", "Completed"),
    ("Hillview Farm Irrigation Support", "Hillview", "Agriculture", 620000, "2025-12-01", "2026-05-31", "In Progress"),
    ("Greenfield Solar Street Lights", "Greenfield", "Energy", 480000, "2026-04-01", "2026-10-31", "Planned"),
]

EDUCATION_SERVICES = [
    {
        "slug": "resources",
        "category": "Learning Resources",
        "title": "Online Learning Resources",
        "description": "Access educational materials, e-books, notes, and learning videos.",
        "action": "View Resources",
        "icon": "▤",
        "color": "blue",
        "intro": "Explore learning content from national education platforms. Availability and languages vary by class and subject.",
        "sources": [
            ("DIKSHA", "Digital learning resources and courses from India's education initiative.", "https://diksha.gov.in/"),
            ("ePathshala", "NCERT textbooks and digital learning materials.", "https://epathshala.nic.in/"),
            ("SWAYAM", "Online courses across school and higher-education subjects.", "https://swayam.gov.in/"),
        ],
    },
    {
        "slug": "classrooms",
        "category": "Learning Resources",
        "title": "Digital Classroom",
        "description": "Discover digital classrooms, online lessons, and educational learning tools.",
        "action": "Explore Classrooms",
        "icon": "▣",
        "color": "purple",
        "intro": "Use the official platforms below to find digital lessons and classroom resources. Check device, language, and connectivity requirements before starting.",
        "sources": [
            ("DIKSHA", "Digital lessons, learning materials, and teacher resources.", "https://diksha.gov.in/"),
            ("PM eVIDYA", "Government of India's digital and broadcast education initiative.", "https://pmevidya.education.gov.in/"),
        ],
    },
    {
        "slug": "courses",
        "category": "Courses",
        "title": "Online Courses",
        "description": "Explore skill development courses and career learning opportunities.",
        "action": "Explore Courses",
        "icon": "▱",
        "color": "green",
        "intro": "Course availability, eligibility, fees, and certificates are set by each provider. Review the official course page before enrolling.",
        "sources": [
            ("SWAYAM", "Online courses offered by participating national institutions.", "https://swayam.gov.in/"),
            ("National Digital Library of India", "Search learning resources from participating institutions.", "https://ndl.iitkgp.ac.in/"),
        ],
    },
    {
        "slug": "scholarships",
        "category": "Scholarships",
        "title": "Scholarships",
        "description": "Find scholarship information, eligibility criteria, application deadlines, and official application links.",
        "action": "View Scholarships",
        "icon": "✦",
        "color": "orange",
        "intro": "Scholarship schemes, eligibility, and deadlines change. This page does not publish deadlines; verify current notices and application requirements on the official portal.",
        "sources": [
            ("National Scholarship Portal", "Check available central and participating scholarship schemes and their current application notices.", "https://scholarships.gov.in/"),
            ("Ministry of Education", "Official notices and information from the Ministry of Education.", "https://www.education.gov.in/"),
        ],
    },
    {
        "slug": "exams",
        "category": "Exams",
        "title": "Exams and Results",
        "description": "Access official exam schedules, examination information, and result links.",
        "action": "Check Now",
        "icon": "✓",
        "color": "blue",
        "intro": "Exam schedules and results are published by the relevant board or examination authority. Select the authority that applies to you and confirm details on its official site.",
        "sources": [
            ("CBSE", "Central Board of Secondary Education examination notices and services.", "https://www.cbse.gov.in/"),
            ("CBSE Results", "Official CBSE results portal; result availability depends on the board's announcements.", "https://results.cbse.nic.in/"),
            ("National Testing Agency", "Examination information and notices from NTA.", "https://nta.ac.in/"),
        ],
    },
    {
        "slug": "careers",
        "category": "Career Guidance",
        "title": "Career Guidance",
        "description": "Explore career paths, skill development guidance, and job preparation resources.",
        "action": "Get Guidance",
        "icon": "↗",
        "color": "purple",
        "intro": "Explore career information and employment services from official sources. Career choices depend on your interests, qualifications, and local opportunities.",
        "sources": [
            ("National Career Service", "Career information, counselling, and employment-related services from the Ministry of Labour and Employment.", "https://www.ncs.gov.in/"),
            ("Skill India Digital Hub", "Explore skill-development information and learning opportunities.", "https://www.skillindiadigital.gov.in/"),
        ],
    },
]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS villages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            district TEXT NOT NULL,
            population INTEGER NOT NULL CHECK (population >= 0),
            schools INTEGER NOT NULL CHECK (schools >= 0),
            healthcare_centers INTEGER NOT NULL CHECK (healthcare_centers >= 0),
            road_status TEXT NOT NULL,
            water_availability INTEGER NOT NULL CHECK (water_availability BETWEEN 0 AND 100),
            agriculture TEXT NOT NULL,
            latitude REAL CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
            longitude REAL CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
            coordinates_verified INTEGER NOT NULL DEFAULT 0 CHECK (coordinates_verified IN (0, 1))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            village_id INTEGER NOT NULL,
            department TEXT NOT NULL,
            budget REAL NOT NULL CHECK (budget >= 0),
            start_date TEXT NOT NULL,
            expected_completion_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('Planned', 'In Progress', 'Completed')),
            FOREIGN KEY (village_id) REFERENCES villages (id)
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN (
                'citizen', 'village_officer', 'system_admin', 'viewer'
            )),
            name TEXT NOT NULL,
            email TEXT COLLATE NOCASE,
            mobile_number TEXT,
            assigned_village_id INTEGER,
            department TEXT,
            is_approved INTEGER NOT NULL DEFAULT 0 CHECK (is_approved IN (0, 1)),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            can_import INTEGER NOT NULL DEFAULT 0 CHECK (can_import IN (0, 1)),
            session_version INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (assigned_village_id) REFERENCES villages (id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT NOT NULL UNIQUE,
            tracking_token_hash TEXT NOT NULL,
            citizen_name TEXT NOT NULL,
            contact_number TEXT,
            village_id INTEGER NOT NULL,
            owner_user_id INTEGER,
            category TEXT NOT NULL CHECK (category IN (
                'Drinking Water', 'Roads and Transportation', 'Electricity',
                'Waste Management', 'Drainage and Sanitation', 'Education',
                'Healthcare', 'Agriculture', 'Other'
            )),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location_description TEXT NOT NULL,
            photo_path TEXT,
            status TEXT NOT NULL DEFAULT 'Pending'
                CHECK (status IN ('Pending', 'In Progress', 'Resolved', 'Rejected')),
            assigned_officer TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (village_id) REFERENCES villages (id) ON DELETE RESTRICT,
            FOREIGN KEY (owner_user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS complaint_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            previous_status TEXT CHECK (
                previous_status IS NULL OR previous_status IN (
                    'Pending', 'In Progress', 'Resolved', 'Rejected'
                )
            ),
            new_status TEXT NOT NULL
                CHECK (new_status IN ('Pending', 'In Progress', 'Resolved', 'Rejected')),
            remarks TEXT NOT NULL DEFAULT '',
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (complaint_id) REFERENCES complaints (id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            village_id INTEGER NOT NULL,
            facility_name TEXT NOT NULL,
            facility_type TEXT NOT NULL CHECK (facility_type IN (
                'School', 'Healthcare Center', 'Drinking Water Facility',
                'Roads and Infrastructure Project', 'Government Service Center'
            )),
            latitude REAL CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),
            longitude REAL CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),
            address TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            coordinates_verified INTEGER NOT NULL DEFAULT 0 CHECK (coordinates_verified IN (0, 1)),
            FOREIGN KEY (village_id) REFERENCES villages (id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            attempt_key TEXT NOT NULL,
            attempted_at INTEGER NOT NULL
        );
        """
    )
    user_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(users)").fetchall()
    }
    if "email" not in user_columns:
        db.execute("PRAGMA foreign_keys = OFF")
        db.execute("DROP TABLE IF EXISTS users_new")
        db.execute(
            """
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN (
                    'citizen', 'village_officer', 'system_admin', 'viewer'
                )),
                name TEXT NOT NULL,
                email TEXT COLLATE NOCASE,
                mobile_number TEXT,
                assigned_village_id INTEGER,
                department TEXT,
                is_approved INTEGER NOT NULL DEFAULT 0 CHECK (is_approved IN (0, 1)),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                can_import INTEGER NOT NULL DEFAULT 0 CHECK (can_import IN (0, 1)),
                session_version INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (assigned_village_id) REFERENCES villages (id) ON DELETE RESTRICT
            );
            """
        )
        migration_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
        legacy_users = db.execute("SELECT * FROM users").fetchall()
        for legacy_user in legacy_users:
            legacy_role = legacy_user["role"]
            migrated_role = "system_admin" if legacy_role == "admin" else "viewer"
            # Old demo administrators have a publicly documented password; require secure bootstrap.
            active = int(legacy_role != "admin")
            db.execute(
                """INSERT INTO users_new
                   (id, username, password_hash, role, name, is_approved, is_active,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)""",
                (
                    legacy_user["id"], legacy_user["username"], legacy_user["password_hash"],
                    migrated_role, legacy_user["username"], active, migration_time, migration_time,
                ),
            )
        db.execute("DROP TABLE users")
        db.execute("ALTER TABLE users_new RENAME TO users")
        db.commit()
        db.execute("PRAGMA foreign_keys = ON")
    elif "session_version" not in user_columns:
        db.execute(
            "ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0"
        )
    db.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS users_email_nocase_idx
            ON users (email COLLATE NOCASE) WHERE email IS NOT NULL;
        CREATE INDEX IF NOT EXISTS users_village_role_idx
            ON users (assigned_village_id, role, is_active);
        CREATE INDEX IF NOT EXISTS login_attempts_time_idx ON login_attempts (attempted_at);
        """
    )
    db.execute(
        """UPDATE users SET is_approved=0, is_active=0
           WHERE role='village_officer'
             AND (assigned_village_id IS NULL OR NOT EXISTS (
                 SELECT 1 FROM villages WHERE villages.id = users.assigned_village_id
             ))"""
    )
    db.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS users_officer_village_insert
        BEFORE INSERT ON users
        WHEN NEW.role = 'village_officer'
          AND (NEW.assigned_village_id IS NULL OR NOT EXISTS (
              SELECT 1 FROM villages WHERE villages.id = NEW.assigned_village_id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'Village officers must be assigned to an existing village');
        END;
        CREATE TRIGGER IF NOT EXISTS users_officer_village_update
        BEFORE UPDATE OF role, assigned_village_id ON users
        WHEN NEW.role = 'village_officer'
          AND (NEW.assigned_village_id IS NULL OR NOT EXISTS (
              SELECT 1 FROM villages WHERE villages.id = NEW.assigned_village_id
          ))
        BEGIN
            SELECT RAISE(ABORT, 'Village officers must be assigned to an existing village');
        END;
        """
    )
    village_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(villages)").fetchall()
    }
    if "latitude" not in village_columns:
        db.execute(
            "ALTER TABLE villages ADD COLUMN latitude REAL "
            "CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90)"
        )
    if "longitude" not in village_columns:
        db.execute(
            "ALTER TABLE villages ADD COLUMN longitude REAL "
            "CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180)"
        )
    if "coordinates_verified" not in village_columns:
        db.execute(
            "ALTER TABLE villages ADD COLUMN coordinates_verified INTEGER NOT NULL "
            "DEFAULT 0 CHECK (coordinates_verified IN (0, 1))"
        )
    complaint_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(complaints)").fetchall()
    }
    if "owner_user_id" not in complaint_columns:
        db.execute(
            "ALTER TABLE complaints ADD COLUMN owner_user_id INTEGER "
            "REFERENCES users (id) ON DELETE SET NULL"
        )
    db.executescript(
        """
        CREATE INDEX IF NOT EXISTS complaints_village_idx ON complaints (village_id);
        CREATE INDEX IF NOT EXISTS complaints_status_idx ON complaints (status);
        CREATE INDEX IF NOT EXISTS complaints_owner_idx ON complaints (owner_user_id);
        CREATE INDEX IF NOT EXISTS complaint_history_complaint_idx
            ON complaint_status_history (complaint_id, updated_at);
        CREATE INDEX IF NOT EXISTS facilities_village_idx ON facilities (village_id);
        """
    )
    seeded = db.execute(
        "SELECT value FROM app_meta WHERE key = 'sample_data_initialized'"
    ).fetchone()
    if seeded is None:
        if db.execute("SELECT COUNT(*) FROM villages").fetchone()[0] == 0:
            db.executemany(
                """INSERT INTO villages
                   (name, district, population, schools, healthcare_centers,
                    road_status, water_availability, agriculture)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                VILLAGE_SAMPLES,
            )
        if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            village_ids = {
                row["name"]: row["id"]
                for row in db.execute("SELECT id, name FROM villages").fetchall()
            }
            sample_projects = [
                (name, village_ids[village], department, budget, start, end, status)
                for name, village, department, budget, start, end, status in PROJECT_SAMPLES
                if village in village_ids
            ]
            db.executemany(
                """INSERT INTO projects
                   (name, village_id, department, budget, start_date,
                    expected_completion_date, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                sample_projects,
            )
        db.execute(
            "INSERT INTO app_meta (key, value) VALUES ('sample_data_initialized', 'yes')"
        )
    db.commit()
    db.close()


@app.before_request
def protect_post_requests():
    user_id = session.get("user_id")
    g.current_user = None
    if user_id:
        user = get_db().execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if (
            user is None
            or not user["is_active"]
            or not user["is_approved"]
            or user["session_version"] != session.get("session_version")
        ):
            session.clear()
        else:
            g.current_user = user
            session["user_role"] = user["role"]
    session.setdefault("_csrf_token", secrets.token_urlsafe(32))
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        submitted_token = request.form.get("_csrf_token", "") or request.headers.get(
            "X-CSRF-Token", ""
        )
        if not compare_digest(session["_csrf_token"], submitted_token):
            abort(400, description="The form security token is missing or invalid. Please reload and try again.")


@app.context_processor
def inject_template_helpers():
    return {
        "csrf_token": lambda: session.get("_csrf_token", ""),
        "current_user": getattr(g, "current_user", None),
    }


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        user = getattr(g, "current_user", None)
        if user is None:
            flash("Please sign in with an administrator account to manage records.", "warning")
            return redirect(url_for("admin_login", next=request.path))
        if user["role"] != "system_admin":
            abort(403)
        return view(**kwargs)

    return wrapped_view


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                login_endpoint = (
                    "officer_login" if "village_officer" in roles else "citizen_login"
                )
                return redirect(url_for(login_endpoint, next=request.path))
            if user["role"] not in roles:
                abort(403)
            return view(**kwargs)

        return wrapped_view

    return decorator


def api_roles_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return jsonify({"error": "Authentication required."}), 401
            if user["role"] not in roles:
                return jsonify({"error": "Insufficient permissions."}), 403
            return view(**kwargs)

        return wrapped_view

    return decorator


def assigned_village_id():
    user = getattr(g, "current_user", None)
    if user is None or user["role"] != "village_officer":
        abort(403)
    if not user["is_approved"] or not user["is_active"] or not user["assigned_village_id"]:
        abort(403)
    if not get_db().execute(
        "SELECT 1 FROM villages WHERE id = ?", (user["assigned_village_id"],)
    ).fetchone():
        abort(403)
    return user["assigned_village_id"]


def validate_email(value):
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(value):
    if len(value) < 12 or len(value) > 256:
        raise ValueError("Password must be between 12 and 256 characters.")
    return value


def auth_payload():
    if request.is_json:
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}
    return request.form


def auth_error(message, status=400):
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), status
    flash(message, "error")
    return None


def login_attempt_key(identifier, role):
    material = "|".join(
        (identifier.strip().casefold(), request.remote_addr or "unknown", role, app.config["SECRET_KEY"])
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def login_is_limited(key):
    now = int(time.time())
    db = get_db()
    db.execute("DELETE FROM login_attempts WHERE attempted_at < ?", (now - 900,))
    attempts = db.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE attempt_key = ? AND attempted_at >= ?",
        (key, now - 900),
    ).fetchone()[0]
    db.commit()
    return attempts >= 5


def record_login_failure(key):
    db = get_db()
    db.execute(
        "INSERT INTO login_attempts (attempt_key, attempted_at) VALUES (?, ?)",
        (key, int(time.time())),
    )
    db.commit()


def establish_login(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["name"]
    session["user_role"] = user["role"]
    session["session_version"] = user["session_version"]
    session["_csrf_token"] = secrets.token_urlsafe(32)


def login_redirect(user):
    if user["role"] == "citizen":
        return url_for("citizen_dashboard")
    if user["role"] == "village_officer":
        return url_for("officer_dashboard")
    if user["role"] == "system_admin":
        return url_for("admin_dashboard")
    return url_for("index")


def login_for_role(role, identifier, password):
    key = login_attempt_key(identifier, role)
    if login_is_limited(key):
        return None, True
    if role == "village_officer":
        user = get_db().execute(
            """SELECT * FROM users
               WHERE email = ? COLLATE NOCASE
                 AND role = ? AND is_active = 1 AND is_approved = 1""",
            (identifier, role),
        ).fetchone()
    else:
        user = get_db().execute(
            """SELECT * FROM users
               WHERE (email = ? COLLATE NOCASE OR username = ?)
                 AND role = ? AND is_active = 1 AND is_approved = 1""",
            (identifier, identifier, role),
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        record_login_failure(key)
        return None, False
    db = get_db()
    db.execute("DELETE FROM login_attempts WHERE attempt_key = ?", (key,))
    db.commit()
    return user, False


def read_village_form():
    name = request.form.get("name", "").strip()
    district = request.form.get("district", "").strip()
    road_status = request.form.get("road_status", "").strip()
    agriculture = request.form.get("agriculture", "").strip()
    try:
        population = int(request.form.get("population", ""))
        schools = int(request.form.get("schools", ""))
        healthcare_centers = int(request.form.get("healthcare_centers", ""))
        water_availability = int(request.form.get("water_availability", ""))
    except ValueError:
        raise ValueError("Population, facilities, and water availability must be whole numbers.") from None
    if not all((name, district, road_status, agriculture)):
        raise ValueError("Please complete every village field.")
    if min(population, schools, healthcare_centers) < 0:
        raise ValueError("Population and facility counts cannot be negative.")
    if road_status not in ("Good", "Fair", "Needs improvement"):
        raise ValueError("Choose a valid road status.")
    if not 0 <= water_availability <= 100:
        raise ValueError("Water availability must be from 0 to 100 percent.")
    if len(name) > 100 or len(district) > 100 or len(agriculture) > 200:
        raise ValueError("Please keep village text fields within the displayed length limits.")
    return (name, district, population, schools, healthcare_centers, road_status, water_availability, agriculture)


def read_project_form():
    name = request.form.get("name", "").strip()
    department = request.form.get("department", "").strip()
    status = request.form.get("status", "").strip()
    start_date = request.form.get("start_date", "").strip()
    expected_date = request.form.get("expected_completion_date", "").strip()
    try:
        village_id = int(request.form.get("village_id", ""))
        budget = float(request.form.get("budget", ""))
    except ValueError:
        raise ValueError("Choose a village and enter a valid budget.") from None
    if not all((name, department, start_date, expected_date)):
        raise ValueError("Please complete every project field.")
    if not math.isfinite(budget) or budget < 0:
        raise ValueError("Budget cannot be negative.")
    if len(name) > 160 or len(department) > 100:
        raise ValueError("Please keep the project name and department within the displayed length limits.")
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(expected_date)
    except ValueError:
        raise ValueError("Enter valid start and expected completion dates.") from None
    if end < start:
        raise ValueError("Expected completion date cannot be before the start date.")
    if status not in ("Planned", "In Progress", "Completed"):
        raise ValueError("Choose a valid project status.")
    if not get_db().execute("SELECT id FROM villages WHERE id = ?", (village_id,)).fetchone():
        raise ValueError("Choose an existing village.")
    user = getattr(g, "current_user", None)
    if user is not None and user["role"] == "village_officer":
        if assigned_village_id() != village_id:
            abort(403)
    return name, village_id, department, budget, start_date, expected_date, status


def read_coordinates_form():
    latitude_text = request.form.get("latitude", "").strip()
    longitude_text = request.form.get("longitude", "").strip()
    verified = request.form.get("coordinates_verified") == "yes"
    if not latitude_text and not longitude_text:
        if verified:
            raise ValueError("Enter both coordinates before confirming them as verified.")
        return None, None, 0
    if not latitude_text or not longitude_text or not verified:
        raise ValueError("Enter both coordinates and confirm they have been verified.")
    try:
        latitude = float(latitude_text)
        longitude = float(longitude_text)
    except ValueError:
        raise ValueError("Enter valid numeric coordinates.") from None
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180.")
    return latitude, longitude, 1


def read_complaint_form():
    user = getattr(g, "current_user", None)
    if user is None or user["role"] != "citizen":
        abort(403)
    citizen_name = user["name"].strip()
    contact_number = request.form.get("contact_number", "").strip()
    category = request.form.get("category", "").strip()
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    location_description = request.form.get("location_description", "").strip()
    try:
        village_id = int(request.form.get("village_id", ""))
    except ValueError:
        raise ValueError("Choose a village from the list.") from None
    if not citizen_name or not category or not title or not description or not location_description:
        raise ValueError("Complete all required complaint fields.")
    if len(citizen_name) > 100 or len(contact_number) > 30:
        raise ValueError("Keep the citizen name and mobile number within the displayed limits.")
    if contact_number and (
        not re.fullmatch(r"[0-9+() -]{7,30}", contact_number)
        or sum(character.isdigit() for character in contact_number) < 7
    ):
        raise ValueError("Enter a valid mobile number or leave it blank.")
    if category not in COMPLAINT_CATEGORIES:
        raise ValueError("Choose a valid complaint category.")
    if not 5 <= len(title) <= 160:
        raise ValueError("The complaint title must be between 5 and 160 characters.")
    if not 10 <= len(description) <= 5000:
        raise ValueError("The description must be between 10 and 5,000 characters.")
    if len(location_description) > 300:
        raise ValueError("The problem location must be 300 characters or fewer.")
    if not get_db().execute(
        "SELECT id FROM villages WHERE id = ?", (village_id,)
    ).fetchone():
        raise ValueError("Choose an existing village.")

    photo = request.files.get("photo")
    photo_bytes = None
    photo_extension = None
    if photo and photo.filename:
        photo_extension = os.path.splitext(photo.filename)[1].lower()
        photo_bytes = photo.stream.read(MAX_UPLOAD_BYTES + 1)
        signatures = {
            ".jpg": photo_bytes.startswith(b"\xff\xd8\xff"),
            ".jpeg": photo_bytes.startswith(b"\xff\xd8\xff"),
            ".png": photo_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
            ".webp": (
                len(photo_bytes) >= 12
                and photo_bytes[:4] == b"RIFF"
                and photo_bytes[8:12] == b"WEBP"
            ),
        }
        if len(photo_bytes) > MAX_UPLOAD_BYTES:
            raise ValueError("The photo must be 5 MB or smaller.")
        if photo_extension not in signatures or not signatures[photo_extension]:
            raise ValueError("Upload a valid JPG, PNG, or WebP image.")
    return (
        citizen_name,
        contact_number or None,
        village_id,
        category,
        title,
        description,
        location_description,
        photo_bytes,
        photo_extension,
    )


@app.route("/")
def index():
    db = get_db()
    user = getattr(g, "current_user", None)
    if user is not None and user["role"] == "village_officer":
        village_id = assigned_village_id()
        villages = db.execute(
            "SELECT * FROM villages WHERE id = ? ORDER BY name", (village_id,)
        ).fetchall()
        projects = db.execute(
            """SELECT projects.*, villages.name AS village_name
               FROM projects JOIN villages ON villages.id = projects.village_id
               WHERE projects.village_id = ? ORDER BY projects.id DESC LIMIT 6""",
            (village_id,),
        ).fetchall()
        village = villages[0]
        counts = {
            "villages": 1,
            "schools": village["schools"],
            "healthcare": village["healthcare_centers"],
            "projects": db.execute(
                "SELECT COUNT(*) FROM projects WHERE village_id = ?", (village_id,)
            ).fetchone()[0],
            "completed": db.execute(
                "SELECT COUNT(*) FROM projects WHERE village_id = ? AND status = 'Completed'",
                (village_id,),
            ).fetchone()[0],
            "in_progress": db.execute(
                "SELECT COUNT(*) FROM projects WHERE village_id = ? AND status = 'In Progress'",
                (village_id,),
            ).fetchone()[0],
        }
    else:
        villages = db.execute("SELECT * FROM villages ORDER BY name").fetchall()
        projects = db.execute(
            """SELECT projects.*, villages.name AS village_name
               FROM projects JOIN villages ON villages.id = projects.village_id
               ORDER BY projects.id DESC LIMIT 6"""
        ).fetchall()
        counts = {
            "villages": db.execute("SELECT COUNT(*) FROM villages").fetchone()[0],
            "schools": db.execute("SELECT COALESCE(SUM(schools), 0) FROM villages").fetchone()[0],
            "healthcare": db.execute("SELECT COALESCE(SUM(healthcare_centers), 0) FROM villages").fetchone()[0],
            "projects": db.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "completed": db.execute("SELECT COUNT(*) FROM projects WHERE status = 'Completed'").fetchone()[0],
            "in_progress": db.execute("SELECT COUNT(*) FROM projects WHERE status = 'In Progress'").fetchone()[0],
        }
    return render_template("index.html", villages=villages, projects=projects, counts=counts)


@app.route("/villages")
def villages():
    search = request.args.get("q", "").strip()
    user = getattr(g, "current_user", None)
    village_scope = (
        assigned_village_id()
        if user is not None and user["role"] == "village_officer"
        else None
    )
    rows = get_db().execute(
        """SELECT * FROM villages
           WHERE (? IS NULL OR id = ?)
             AND (name LIKE ? OR district LIKE ?)
           ORDER BY name""",
        (village_scope, village_scope, f"%{search}%", f"%{search}%"),
    ).fetchall()
    return render_template("villages.html", villages=rows, search=search)


@app.route("/villages/<int:village_id>")
def village_details(village_id):
    db = get_db()
    user = getattr(g, "current_user", None)
    if (
        user is not None
        and user["role"] == "village_officer"
        and assigned_village_id() != village_id
    ):
        abort(403)
    village = db.execute("SELECT * FROM villages WHERE id = ?", (village_id,)).fetchone()
    if village is None:
        abort(404)
    projects = db.execute(
        "SELECT * FROM projects WHERE village_id = ? ORDER BY start_date DESC",
        (village_id,),
    ).fetchall()
    facilities = db.execute(
        "SELECT * FROM facilities WHERE village_id = ? ORDER BY facility_type, facility_name",
        (village_id,),
    ).fetchall()
    return render_template(
        "village_details.html", village=village, projects=projects, facilities=facilities
    )


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    village_count = db.execute("SELECT COUNT(*) FROM villages").fetchone()[0]
    project_count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    complaint_count = db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    facility_count = db.execute("SELECT COUNT(*) FROM facilities").fetchone()[0]
    return render_template(
        "admin.html",
        village_count=village_count,
        project_count=project_count,
        complaint_count=complaint_count,
        facility_count=facility_count,
    )


@app.get("/citizen/dashboard")
@roles_required("citizen")
def citizen_dashboard():
    db = get_db()
    user_id = g.current_user["id"]
    complaints = db.execute(
        """SELECT complaints.*, villages.name AS village_name
           FROM complaints JOIN villages ON villages.id = complaints.village_id
           WHERE complaints.owner_user_id = ? ORDER BY complaints.created_at DESC""",
        (user_id,),
    ).fetchall()
    return render_template("citizen_dashboard.html", complaints=complaints)


@app.route("/citizen/profile", methods=["GET", "POST"])
@roles_required("citizen")
def citizen_profile():
    user = g.current_user
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile_number", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        if not 2 <= len(name) <= 100:
            flash("Enter a name between 2 and 100 characters.", "error")
        elif mobile and (
            len(mobile) > 30
            or not re.fullmatch(r"[0-9+() -]{7,30}", mobile)
            or sum(character.isdigit() for character in mobile) < 7
        ):
            flash("Enter a valid mobile number or leave it blank.", "error")
        elif new_password and (
            not check_password_hash(user["password_hash"], current_password)
        ):
            flash("Enter your current password to change it.", "error")
        elif new_password and new_password != request.form.get("confirm_password", ""):
            flash("New password and confirmation do not match.", "error")
        elif new_password and (len(new_password) < 12 or len(new_password) > 256):
            flash("New password must be between 12 and 256 characters.", "error")
        else:
            db = get_db()
            if new_password:
                db.execute(
                    """UPDATE users SET name=?, mobile_number=?, password_hash=?,
                       session_version=session_version+1, updated_at=?
                       WHERE id=?""",
                    (
                        name, mobile, generate_password_hash(new_password),
                        datetime.now(timezone.utc).isoformat(timespec="seconds"), user["id"],
                    ),
                )
            else:
                db.execute(
                    "UPDATE users SET name=?, mobile_number=?, updated_at=? WHERE id=?",
                    (
                        name, mobile, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        user["id"],
                    ),
                )
            db.commit()
            if new_password:
                session.clear()
                flash("Password changed. Sign in again with your new password.", "success")
                return redirect(url_for("citizen_login"))
            session["username"] = name
            flash("Your profile was updated.", "success")
            return redirect(url_for("citizen_profile"))
    return render_template("citizen_profile.html", user=user)


@app.get("/officer/dashboard")
@roles_required("village_officer")
def officer_dashboard():
    village_id = assigned_village_id()
    db = get_db()
    village = db.execute("SELECT * FROM villages WHERE id = ?", (village_id,)).fetchone()
    complaints = db.execute(
        """SELECT complaint_id, title, category, status, created_at
           FROM complaints WHERE village_id = ? ORDER BY created_at DESC LIMIT 8""",
        (village_id,),
    ).fetchall()
    project_counts = db.execute(
        "SELECT status, COUNT(*) AS total FROM projects WHERE village_id = ? GROUP BY status",
        (village_id,),
    ).fetchall()
    complaint_counts = db.execute(
        "SELECT status, COUNT(*) AS total FROM complaints WHERE village_id = ? GROUP BY status",
        (village_id,),
    ).fetchall()
    return render_template(
        "officer_dashboard.html",
        village=village,
        complaints=complaints,
        project_counts=project_counts,
        complaint_counts=complaint_counts,
    )


@app.get("/officer/complaints")
@roles_required("village_officer")
def officer_complaints():
    village_id = assigned_village_id()
    complaints = get_db().execute(
        """SELECT complaints.*, villages.name AS village_name
           FROM complaints JOIN villages ON villages.id = complaints.village_id
           WHERE complaints.village_id = ? ORDER BY complaints.created_at DESC""",
        (village_id,),
    ).fetchall()
    return render_template("officer_complaints.html", complaints=complaints)


@app.route("/officer/complaints/<int:complaint_row_id>", methods=["GET", "POST"])
@roles_required("village_officer")
def officer_complaint_details(complaint_row_id):
    village_id = assigned_village_id()
    db = get_db()
    complaint = db.execute(
        """SELECT complaints.*, villages.name AS village_name
           FROM complaints JOIN villages ON villages.id = complaints.village_id
           WHERE complaints.id = ?""",
        (complaint_row_id,),
    ).fetchone()
    if complaint is None:
        abort(404)
    if complaint["village_id"] != village_id:
        abort(403)
    if request.method == "POST":
        status = request.form.get("status", "").strip()
        remarks = request.form.get("remarks", "").strip()
        if status not in COMPLAINT_STATUSES:
            flash("Choose a valid complaint status.", "error")
        elif len(remarks) > 1500:
            flash("Remarks must be 1,500 characters or fewer.", "error")
        else:
            updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                if status != complaint["status"] or remarks:
                    db.execute(
                        """INSERT INTO complaint_status_history
                           (complaint_id, previous_status, new_status, remarks, updated_by, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            complaint_row_id, complaint["status"], status, remarks,
                            g.current_user["name"], updated_at,
                        ),
                    )
                db.execute(
                    """UPDATE complaints SET status=?, updated_at=?
                       WHERE id=? AND village_id=?""",
                    (status, updated_at, complaint_row_id, village_id),
                )
                db.commit()
            except sqlite3.Error:
                db.rollback()
                app.logger.exception("Officer complaint update failed")
                flash("The complaint could not be updated.", "error")
            else:
                flash("Complaint updated.", "success")
                return redirect(url_for("officer_complaint_details", complaint_row_id=complaint_row_id))
    history = db.execute(
        """SELECT * FROM complaint_status_history WHERE complaint_id = ?
           ORDER BY updated_at DESC, id DESC""",
        (complaint_row_id,),
    ).fetchall()
    return render_template(
        "admin_complaint_details.html", complaint=complaint,
        history=history, statuses=COMPLAINT_STATUSES,
    )


@app.get("/officer/projects")
@roles_required("village_officer")
def officer_projects():
    projects = get_db().execute(
        """SELECT projects.*, villages.name AS village_name
           FROM projects JOIN villages ON villages.id = projects.village_id
           WHERE projects.village_id = ? ORDER BY projects.start_date DESC""",
        (assigned_village_id(),),
    ).fetchall()
    return render_template("officer_projects.html", projects=projects)


@app.route("/officer/projects/new", methods=["GET", "POST"])
@roles_required("village_officer")
def officer_add_project():
    db = get_db()
    village_id = assigned_village_id()
    if request.method == "POST":
        try:
            values = read_project_form()
        except ValueError as error:
            flash(str(error), "error")
        else:
            db.execute(
                """INSERT INTO projects
                   (name, village_id, department, budget, start_date,
                    expected_completion_date, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            db.commit()
            flash("Project added.", "success")
            return redirect(url_for("officer_projects"))
    villages = db.execute("SELECT id, name FROM villages WHERE id = ?", (village_id,)).fetchall()
    return render_template("project_form.html", project=None, villages=villages, form_title="Add project")


@app.route("/officer/projects/<int:project_id>/edit", methods=["GET", "POST"])
@roles_required("village_officer")
def officer_edit_project(project_id):
    db = get_db()
    village_id = assigned_village_id()
    project = db.execute(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if project is None:
        abort(404)
    if project["village_id"] != village_id:
        abort(403)
    if request.method == "POST":
        try:
            values = read_project_form()
        except ValueError as error:
            flash(str(error), "error")
        else:
            db.execute(
                """UPDATE projects SET name=?, village_id=?, department=?, budget=?,
                   start_date=?, expected_completion_date=?, status=?
                   WHERE id=? AND village_id=?""",
                (*values, project_id, village_id),
            )
            db.commit()
            flash("Project updated.", "success")
            return redirect(url_for("officer_projects"))
    villages = db.execute("SELECT id, name FROM villages WHERE id = ?", (village_id,)).fetchall()
    return render_template("project_form.html", project=project, villages=villages, form_title="Edit project")


@app.get("/officer/reports")
@roles_required("village_officer")
def officer_reports():
    return redirect(url_for("reports"))


@app.route("/admin/villages/new", methods=["GET", "POST"])
@admin_required
def add_village():
    if request.method == "POST":
        try:
            values = read_village_form()
            coordinates = read_coordinates_form()
            get_db().execute(
                """INSERT INTO villages
                   (name, district, population, schools, healthcare_centers,
                    road_status, water_availability, agriculture,
                    latitude, longitude, coordinates_verified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*values, *coordinates),
            )
            get_db().commit()
        except ValueError as error:
            flash(str(error), "error")
        except sqlite3.IntegrityError:
            flash("A village with that name already exists.", "error")
        else:
            flash("Village added successfully.", "success")
            return redirect(url_for("villages"))
    return render_template("village_form.html", village=None, form_title="Add village")


@app.route("/admin/villages/<int:village_id>/edit", methods=["GET", "POST"])
@roles_required("system_admin", "village_officer")
def edit_village(village_id):
    db = get_db()
    village = db.execute("SELECT * FROM villages WHERE id = ?", (village_id,)).fetchone()
    if village is None:
        abort(404)
    user = getattr(g, "current_user", None)
    if user["role"] == "village_officer" and user["assigned_village_id"] != village_id:
        abort(403)
    if request.method == "POST":
        try:
            values = read_village_form()
            coordinates = (
                read_coordinates_form()
                if user["role"] == "system_admin"
                else (
                    village["latitude"],
                    village["longitude"],
                    village["coordinates_verified"],
                )
            )
            db.execute(
                """UPDATE villages SET name=?, district=?, population=?, schools=?,
                   healthcare_centers=?, road_status=?, water_availability=?, agriculture=?,
                   latitude=?, longitude=?, coordinates_verified=?
                   WHERE id=?""",
                (*values, *coordinates, village_id),
            )
            db.commit()
        except ValueError as error:
            flash(str(error), "error")
        except sqlite3.IntegrityError:
            flash("A village with that name already exists.", "error")
        else:
            flash("Village updated successfully.", "success")
            return redirect(url_for("village_details", village_id=village_id))
    return render_template("village_form.html", village=village, form_title="Edit village")


@app.post("/admin/villages/<int:village_id>/delete")
@admin_required
def delete_village(village_id):
    db = get_db()
    try:
        cursor = db.execute("DELETE FROM villages WHERE id = ?", (village_id,))
        if cursor.rowcount == 0:
            abort(404)
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        flash("This village has linked projects, complaints, or facilities. Move or delete those records before deleting the village.", "error")
        return redirect(url_for("villages"))
    flash("Village deleted.", "success")
    return redirect(url_for("villages"))


@app.route("/projects")
def projects():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    conditions = ["(projects.name LIKE ? OR villages.name LIKE ?)"]
    parameters = [f"%{search}%", f"%{search}%"]
    user = getattr(g, "current_user", None)
    if user is not None and user["role"] == "village_officer":
        conditions.append("projects.village_id = ?")
        parameters.append(assigned_village_id())
    if status_filter in ("Planned", "In Progress", "Completed"):
        conditions.append("projects.status = ?")
        parameters.append(status_filter)
    rows = get_db().execute(
        """SELECT projects.*, villages.name AS village_name
           FROM projects JOIN villages ON villages.id = projects.village_id
           WHERE """ + " AND ".join(conditions) + " ORDER BY projects.start_date DESC",
        parameters,
    ).fetchall()
    return render_template("projects.html", projects=rows, search=search, status_filter=status_filter)


@app.route("/admin/projects/new", methods=["GET", "POST"])
@admin_required
def add_project():
    db = get_db()
    if request.method == "POST":
        try:
            values = read_project_form()
            db.execute(
                """INSERT INTO projects
                   (name, village_id, department, budget, start_date,
                    expected_completion_date, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            db.commit()
        except ValueError as error:
            flash(str(error), "error")
        else:
            flash("Project added successfully.", "success")
            return redirect(url_for("projects"))
    village_rows = db.execute("SELECT id, name FROM villages ORDER BY name").fetchall()
    return render_template("project_form.html", project=None, villages=village_rows, form_title="Add project")


@app.route("/admin/projects/<int:project_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_project(project_id):
    db = get_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        abort(404)
    if request.method == "POST":
        try:
            values = read_project_form()
            db.execute(
                """UPDATE projects SET name=?, village_id=?, department=?, budget=?,
                   start_date=?, expected_completion_date=?, status=? WHERE id=?""",
                (*values, project_id),
            )
            db.commit()
        except ValueError as error:
            flash(str(error), "error")
        else:
            flash("Project updated successfully.", "success")
            return redirect(url_for("projects"))
    village_rows = db.execute("SELECT id, name FROM villages ORDER BY name").fetchall()
    return render_template("project_form.html", project=project, villages=village_rows, form_title="Edit project")


@app.post("/admin/projects/<int:project_id>/delete")
@admin_required
def delete_project(project_id):
    db = get_db()
    cursor = db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    if cursor.rowcount == 0:
        abort(404)
    db.commit()
    flash("Project deleted.", "success")
    return redirect(url_for("projects"))


@app.route("/manage-complaints", methods=["GET", "POST"])
@roles_required("citizen")
def manage_complaints():
    db = get_db()
    village_rows = db.execute("SELECT id, name FROM villages ORDER BY name").fetchall()
    if request.method == "POST":
        try:
            values = read_complaint_form()
        except ValueError as error:
            flash(str(error), "error")
        else:
            citizen_name, contact_number, village_id, category, title, description, location, photo_bytes, photo_extension = values
            complaint_id = f"SV-{datetime.now(timezone.utc).year}-{secrets.token_hex(6).upper()}"
            tracking_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(tracking_token.encode("utf-8")).hexdigest()
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                cursor = db.execute(
                    """INSERT INTO complaints
                       (complaint_id, tracking_token_hash, citizen_name, contact_number,
                        village_id, category, title, description, location_description,
                        status, created_at, updated_at, owner_user_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)""",
                    (
                        complaint_id, token_hash, citizen_name, contact_number,
                        village_id, category, title, description, location, timestamp, timestamp,
                        g.current_user["id"],
                    ),
                )
                if photo_bytes is not None:
                    os.makedirs(app.config["COMPLAINT_UPLOAD_FOLDER"], exist_ok=True)
                    photo_name = f"{secrets.token_hex(24)}{photo_extension}"
                    photo_path = os.path.join(app.config["COMPLAINT_UPLOAD_FOLDER"], photo_name)
                    with open(photo_path, "xb") as photo_file:
                        photo_file.write(photo_bytes)
                    db.execute(
                        "UPDATE complaints SET photo_path = ? WHERE id = ?",
                        (photo_name, cursor.lastrowid),
                    )
                db.execute(
                    """INSERT INTO complaint_status_history
                       (complaint_id, previous_status, new_status, remarks, updated_by, updated_at)
                       VALUES (?, NULL, 'Pending', 'Complaint submitted', 'Citizen', ?)""",
                    (cursor.lastrowid, timestamp),
                )
                db.commit()
            except (OSError, sqlite3.Error):
                db.rollback()
                if "photo_path" in locals() and os.path.isfile(photo_path):
                    try:
                        os.remove(photo_path)
                    except OSError:
                        app.logger.exception("Unable to clean up an incomplete complaint upload")
                app.logger.exception("Complaint submission failed")
                flash("The complaint could not be saved. Please try again.", "error")
            else:
                response = render_template(
                    "complaint_form.html",
                    villages=village_rows,
                    categories=COMPLAINT_CATEGORIES,
                    submitted={
                        "complaint_id": complaint_id,
                        "created_at": timestamp,
                    },
                )
                app_response = app.make_response(response)
                app_response.headers["Cache-Control"] = "no-store"
                return app_response, 201
    return render_template(
        "complaint_form.html", villages=village_rows, categories=COMPLAINT_CATEGORIES
    )


@app.route("/track-complaint", methods=["GET", "POST"])
@roles_required("citizen")
def track_complaint():
    complaint = None
    history = []
    lookup_failed = False
    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", "").strip().upper()
        row = None
        if len(complaint_id) <= 40:
            row = get_db().execute(
                """SELECT complaints.*, villages.name AS village_name
                   FROM complaints JOIN villages ON villages.id = complaints.village_id
                   WHERE complaints.complaint_id = ? AND complaints.owner_user_id = ?""",
                (complaint_id, g.current_user["id"]),
            ).fetchone()
        if row is not None:
            complaint = row
            history = get_db().execute(
                """SELECT previous_status, new_status, remarks, updated_at
                   FROM complaint_status_history WHERE complaint_id = ?
                   ORDER BY updated_at, id""",
                (row["id"],),
            ).fetchall()
        else:
            lookup_failed = True
    response = app.make_response(
        render_template(
            "track_complaint.html",
            complaint=complaint,
            history=history,
            lookup_failed=lookup_failed,
        )
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/admin/complaints")
@admin_required
def admin_complaints():
    db = get_db()
    search = request.args.get("q", "").strip()[:160]
    village_filter = request.args.get("village", "").strip()
    category_filter = request.args.get("category", "").strip()
    status_filter = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    conditions = ["(complaints.complaint_id LIKE ? OR complaints.title LIKE ?)"]
    parameters = [f"%{search}%", f"%{search}%"]
    if village_filter.isdigit() and len(village_filter) <= 10:
        conditions.append("complaints.village_id = ?")
        parameters.append(int(village_filter))
    if category_filter in COMPLAINT_CATEGORIES:
        conditions.append("complaints.category = ?")
        parameters.append(category_filter)
    if status_filter in COMPLAINT_STATUSES:
        conditions.append("complaints.status = ?")
        parameters.append(status_filter)
    for label, value in (("start", date_from), ("end", date_to)):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                flash(f"Choose a valid {label} date.", "error")
                if label == "start":
                    date_from = ""
                else:
                    date_to = ""
    if date_from and date_to and date_from > date_to:
        flash("The start date cannot be after the end date.", "error")
        date_from = ""
        date_to = ""
    if date_from:
        conditions.append("date(complaints.created_at) >= date(?)")
        parameters.append(date_from)
    if date_to:
        conditions.append("date(complaints.created_at) <= date(?)")
        parameters.append(date_to)
    complaints = db.execute(
        """SELECT complaints.*, villages.name AS village_name
           FROM complaints JOIN villages ON villages.id = complaints.village_id
           WHERE """ + " AND ".join(conditions) + " ORDER BY complaints.created_at DESC",
        parameters,
    ).fetchall()
    counts = {
        "total": db.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
        "pending": db.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Pending'").fetchone()[0],
        "in_progress": db.execute("SELECT COUNT(*) FROM complaints WHERE status = 'In Progress'").fetchone()[0],
        "resolved": db.execute("SELECT COUNT(*) FROM complaints WHERE status = 'Resolved'").fetchone()[0],
    }
    category_totals = {
        row["category"]: row["total"]
        for row in db.execute(
            "SELECT category, COUNT(*) AS total FROM complaints GROUP BY category"
        ).fetchall()
    }
    status_totals = {
        row["status"]: row["total"]
        for row in db.execute(
            "SELECT status, COUNT(*) AS total FROM complaints GROUP BY status"
        ).fetchall()
    }
    return render_template(
        "admin_complaints.html",
        complaints=complaints,
        counts=counts,
        categories=COMPLAINT_CATEGORIES,
        statuses=COMPLAINT_STATUSES,
        villages=db.execute("SELECT id, name FROM villages ORDER BY name").fetchall(),
        filters={
            "q": search,
            "village": village_filter,
            "category": category_filter,
            "status": status_filter,
            "date_from": date_from,
            "date_to": date_to,
        },
        category_totals=[category_totals.get(name, 0) for name in COMPLAINT_CATEGORIES],
        status_totals=[status_totals.get(name, 0) for name in COMPLAINT_STATUSES],
    )


@app.route("/admin/complaints/<int:complaint_row_id>", methods=["GET", "POST"])
@admin_required
def admin_complaint_details(complaint_row_id):
    db = get_db()
    complaint = db.execute(
        """SELECT complaints.*, villages.name AS village_name
           FROM complaints JOIN villages ON villages.id = complaints.village_id
           WHERE complaints.id = ?""",
        (complaint_row_id,),
    ).fetchone()
    if complaint is None:
        abort(404)
    if request.method == "POST":
        new_status = request.form.get("status", "").strip()
        assigned_officer = request.form.get("assigned_officer", "").strip()
        remarks = request.form.get("remarks", "").strip()
        if new_status not in COMPLAINT_STATUSES:
            flash("Choose a valid complaint status.", "error")
        elif len(assigned_officer) > 100 or len(remarks) > 1500:
            flash("Officer name or remarks exceed the allowed length.", "error")
        else:
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                if new_status != complaint["status"] or remarks:
                    db.execute(
                        """INSERT INTO complaint_status_history
                           (complaint_id, previous_status, new_status, remarks, updated_by, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            complaint_row_id, complaint["status"], new_status, remarks,
                            session.get("username", "Administrator"), timestamp,
                        ),
                    )
                db.execute(
                    """UPDATE complaints SET status = ?, assigned_officer = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_status, assigned_officer or None, timestamp, complaint_row_id),
                )
                db.commit()
            except sqlite3.Error:
                db.rollback()
                app.logger.exception("Complaint update failed")
                flash("The complaint could not be updated. Please try again.", "error")
            else:
                flash("Complaint updated successfully.", "success")
                return redirect(url_for("admin_complaint_details", complaint_row_id=complaint_row_id))
    history = db.execute(
        """SELECT * FROM complaint_status_history WHERE complaint_id = ?
           ORDER BY updated_at DESC, id DESC""",
        (complaint_row_id,),
    ).fetchall()
    return render_template(
        "admin_complaint_details.html",
        complaint=complaint,
        history=history,
        statuses=COMPLAINT_STATUSES,
    )


@app.post("/admin/complaints/<int:complaint_row_id>/delete")
@admin_required
def delete_complaint(complaint_row_id):
    db = get_db()
    complaint = db.execute(
        "SELECT photo_path FROM complaints WHERE id = ?", (complaint_row_id,)
    ).fetchone()
    if complaint is None:
        abort(404)
    cursor = db.execute("DELETE FROM complaints WHERE id = ?", (complaint_row_id,))
    db.commit()
    if cursor.rowcount and complaint["photo_path"]:
        photo_path = os.path.join(
            app.config["COMPLAINT_UPLOAD_FOLDER"],
            os.path.basename(complaint["photo_path"]),
        )
        if os.path.isfile(photo_path):
            try:
                os.remove(photo_path)
            except OSError:
                app.logger.exception("Unable to remove deleted complaint photo")
                flash("Complaint deleted, but its uploaded photo could not be removed.", "warning")
    flash("Complaint deleted.", "success")
    return redirect(url_for("admin_complaints"))


@app.get("/admin/complaints/<int:complaint_row_id>/photo")
@roles_required("system_admin", "village_officer")
def complaint_photo(complaint_row_id):
    user = g.current_user
    if user["role"] == "village_officer":
        complaint = get_db().execute(
            "SELECT village_id, photo_path FROM complaints WHERE id = ?",
            (complaint_row_id,),
        ).fetchone()
        if complaint is not None and complaint["village_id"] != assigned_village_id():
            abort(403)
    else:
        complaint = get_db().execute(
            "SELECT photo_path FROM complaints WHERE id = ?", (complaint_row_id,)
        ).fetchone()
    if complaint is None or not complaint["photo_path"]:
        abort(404)
    filename = os.path.basename(complaint["photo_path"])
    path = os.path.join(app.config["COMPLAINT_UPLOAD_FOLDER"], filename)
    if not os.path.isfile(path):
        abort(404)
    mimetype = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(os.path.splitext(filename)[1].lower(), "application/octet-stream")
    response = app.make_response(
        send_file(path, mimetype=mimetype, as_attachment=False, conditional=True)
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def read_facility_form():
    facility_name = request.form.get("facility_name", "").strip()
    facility_type = request.form.get("facility_type", "").strip()
    address = request.form.get("address", "").strip()
    description = request.form.get("description", "").strip()
    try:
        village_id = int(request.form.get("village_id", ""))
    except ValueError:
        raise ValueError("Choose a village.") from None
    if not facility_name or facility_type not in FACILITY_TYPES:
        raise ValueError("Enter a facility name and choose a valid facility type.")
    if len(facility_name) > 160 or len(address) > 300 or len(description) > 1500:
        raise ValueError("One or more facility fields exceed their allowed length.")
    if not get_db().execute("SELECT id FROM villages WHERE id = ?", (village_id,)).fetchone():
        raise ValueError("Choose an existing village.")
    coordinates = read_coordinates_form()
    return village_id, facility_name, facility_type, *coordinates[:2], address, description, coordinates[2]


@app.route("/admin/facilities/new", methods=["GET", "POST"])
@admin_required
def add_facility():
    db = get_db()
    if request.method == "POST":
        try:
            values = read_facility_form()
        except ValueError as error:
            flash(str(error), "error")
        else:
            db.execute(
                """INSERT INTO facilities
                   (village_id, facility_name, facility_type, latitude, longitude,
                    address, description, coordinates_verified)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
            )
            db.commit()
            flash("Facility added successfully.", "success")
            return redirect(url_for("gis_map"))
    return render_template(
        "facility_form.html",
        facility=None,
        villages=db.execute("SELECT id, name FROM villages ORDER BY name").fetchall(),
        facility_types=FACILITY_TYPES,
        form_title="Add facility",
    )


@app.route("/admin/facilities/<int:facility_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_facility(facility_id):
    db = get_db()
    facility = db.execute(
        "SELECT * FROM facilities WHERE id = ?", (facility_id,)
    ).fetchone()
    if facility is None:
        abort(404)
    if request.method == "POST":
        try:
            values = read_facility_form()
        except ValueError as error:
            flash(str(error), "error")
        else:
            db.execute(
                """UPDATE facilities SET village_id=?, facility_name=?, facility_type=?,
                   latitude=?, longitude=?, address=?, description=?, coordinates_verified=?
                   WHERE id=?""",
                (*values, facility_id),
            )
            db.commit()
            flash("Facility updated successfully.", "success")
            return redirect(url_for("gis_map"))
    return render_template(
        "facility_form.html",
        facility=facility,
        villages=db.execute("SELECT id, name FROM villages ORDER BY name").fetchall(),
        facility_types=FACILITY_TYPES,
        form_title="Edit facility",
    )


@app.post("/admin/facilities/<int:facility_id>/delete")
@admin_required
def delete_facility(facility_id):
    cursor = get_db().execute("DELETE FROM facilities WHERE id = ?", (facility_id,))
    if cursor.rowcount == 0:
        abort(404)
    get_db().commit()
    flash("Facility deleted.", "success")
    return redirect(url_for("gis_map"))


@app.get("/gis-map")
def gis_map():
    db = get_db()
    user = getattr(g, "current_user", None)
    officer_village_id = (
        assigned_village_id()
        if user is not None and user["role"] == "village_officer"
        else None
    )
    selected_village = request.args.get("village", "")
    if officer_village_id is not None:
        if selected_village and selected_village != str(officer_village_id):
            abort(403)
        selected_village = str(officer_village_id)
    village_filter = "WHERE villages.id = ?" if officer_village_id is not None else ""
    scope_parameters = (officer_village_id,) if officer_village_id is not None else ()
    villages = db.execute(
        f"""SELECT villages.*,
                   (SELECT COUNT(*) FROM facilities WHERE facilities.village_id = villages.id
                    AND facilities.facility_type = 'School') AS mapped_schools,
                   (SELECT COUNT(*) FROM facilities WHERE facilities.village_id = villages.id
                    AND facilities.facility_type = 'Healthcare Center') AS mapped_healthcare,
                   (SELECT COUNT(*) FROM facilities WHERE facilities.village_id = villages.id
                    AND facilities.facility_type = 'Drinking Water Facility') AS mapped_water,
                   (SELECT COUNT(*) FROM projects WHERE projects.village_id = villages.id) AS project_count,
                   (SELECT COUNT(*) FROM projects WHERE projects.village_id = villages.id
                    AND projects.status = 'Planned') AS planned_projects,
                   (SELECT COUNT(*) FROM projects WHERE projects.village_id = villages.id
                    AND projects.status = 'In Progress') AS in_progress_projects,
                   (SELECT COUNT(*) FROM projects WHERE projects.village_id = villages.id
                    AND projects.status = 'Completed') AS completed_projects
            FROM villages {village_filter} ORDER BY villages.name""",
        scope_parameters,
    ).fetchall()
    facilities = db.execute(
        f"""SELECT facilities.*, villages.name AS village_name, villages.district
            FROM facilities JOIN villages ON villages.id = facilities.village_id
            {("WHERE facilities.village_id = ?" if officer_village_id is not None else "")}
            ORDER BY villages.name, facilities.facility_type, facilities.facility_name""",
        scope_parameters,
    ).fetchall()
    mapped_villages = sum(
        1 for village in villages
        if village["coordinates_verified"] and village["latitude"] is not None
        and village["longitude"] is not None
    )
    mapped_facilities = sum(
        1 for facility in facilities
        if facility["coordinates_verified"] and facility["latitude"] is not None
        and facility["longitude"] is not None
    )
    return render_template(
        "gis_map.html",
        villages=villages,
        facilities=facilities,
        mapped_villages=mapped_villages,
        mapped_facilities=mapped_facilities,
        facility_types=FACILITY_TYPES,
        selected_village=selected_village,
        village_data=[dict(village) for village in villages],
        facility_data=[dict(facility) for facility in facilities],
        officer_map_center=(
            [villages[0]["latitude"], villages[0]["longitude"]]
            if officer_village_id is not None
            and villages
            and villages[0]["coordinates_verified"]
            and villages[0]["latitude"] is not None
            and villages[0]["longitude"] is not None
            else None
        ),
    )


@app.route("/analytics")
def analytics():
    db = get_db()
    user = getattr(g, "current_user", None)
    if user is not None and user["role"] == "village_officer":
        village_id = assigned_village_id()
        villages = db.execute(
            "SELECT * FROM villages WHERE id = ? ORDER BY name", (village_id,)
        ).fetchall()
        project_statuses = db.execute(
            """SELECT status, COUNT(*) AS total FROM projects
               WHERE village_id = ? GROUP BY status""",
            (village_id,),
        ).fetchall()
    else:
        villages = db.execute("SELECT * FROM villages ORDER BY name").fetchall()
        project_statuses = db.execute(
            "SELECT status, COUNT(*) AS total FROM projects GROUP BY status"
        ).fetchall()
    return render_template("analytics.html", villages=villages, project_statuses=project_statuses)


@app.route("/reports")
def reports():
    db = get_db()
    user = getattr(g, "current_user", None)
    if user is not None and user["role"] == "village_officer":
        village_id = assigned_village_id()
        villages = db.execute(
            "SELECT * FROM villages WHERE id = ? ORDER BY name", (village_id,)
        ).fetchall()
        project_total = db.execute(
            "SELECT COUNT(*) FROM projects WHERE village_id = ?", (village_id,)
        ).fetchone()[0]
        complaint_statuses = db.execute(
            """SELECT status, COUNT(*) AS total FROM complaints
               WHERE village_id = ? GROUP BY status""",
            (village_id,),
        ).fetchall()
    else:
        villages = db.execute("SELECT * FROM villages ORDER BY name").fetchall()
        project_total = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        complaint_statuses = db.execute(
            "SELECT status, COUNT(*) AS total FROM complaints GROUP BY status"
        ).fetchall()
    complaint_total = sum(row["total"] for row in complaint_statuses)
    attention_villages = [
        village for village in villages
        if village["water_availability"] < 70 or village["road_status"] == "Needs improvement"
    ]
    return render_template(
        "reports.html",
        villages=villages,
        project_total=project_total,
        complaint_total=complaint_total,
        complaint_statuses=complaint_statuses,
        attention_villages=attention_villages,
    )


@app.route("/education")
def education():
    return render_template("education.html", services=EDUCATION_SERVICES)


@app.route("/education/<slug>")
def education_service(slug):
    service = next((item for item in EDUCATION_SERVICES if item["slug"] == slug), None)
    if service is None:
        abort(404)
    return render_template("education_service.html", service=service)


def create_citizen_account(payload):
    name = str(payload.get("name", "")).strip()
    email = validate_email(str(payload.get("email", "")))
    mobile = str(payload.get("mobile_number", "")).strip()
    password = validate_password(str(payload.get("password", "")))
    confirmation = str(payload.get("confirm_password", ""))
    if not 2 <= len(name) <= 100:
        raise ValueError("Full name must be between 2 and 100 characters.")
    if mobile and (
        len(mobile) > 30
        or not re.fullmatch(r"[0-9+() -]{7,30}", mobile)
        or sum(character.isdigit() for character in mobile) < 7
    ):
        raise ValueError("Enter a valid mobile number or leave it blank.")
    if password != confirmation:
        raise ValueError("Password and confirmation do not match.")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = get_db()
    cursor = db.execute(
        """INSERT INTO users
           (username, password_hash, role, name, email, mobile_number,
            is_approved, is_active, created_at, updated_at)
           VALUES (?, ?, 'citizen', ?, ?, ?, 1, 1, ?, ?)""",
        (
            email, generate_password_hash(password), name, email, mobile or None,
            timestamp, timestamp,
        ),
    )
    db.commit()
    return db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()


def register_citizen_response(payload, json_response=False):
    email = str(payload.get("email", ""))
    key = login_attempt_key(email, "citizen-register")
    if login_is_limited(key):
        if json_response:
            return jsonify({"error": "Too many registration attempts. Try again later."}), 429
        flash("Too many registration attempts. Try again later.", "error")
        return render_template("citizen_register.html"), 429
    record_login_failure(key)
    try:
        create_citizen_account(payload)
    except ValueError as error:
        if json_response:
            return jsonify({"error": str(error)}), 400
        flash(str(error), "error")
        return None
    except sqlite3.IntegrityError:
        get_db().rollback()
        if json_response:
            return jsonify({"error": "An account with that email already exists."}), 409
        flash("An account with that email already exists.", "error")
        return None
    if json_response:
        return jsonify({"message": "Citizen account created. You can now sign in."}), 201
    flash("Registration successful. Sign in to continue.", "success")
    return redirect(url_for("citizen_login"))


@app.get("/auth")
def auth_landing():
    if getattr(g, "current_user", None) is not None:
        return redirect(login_redirect(g.current_user))
    return render_template("auth_landing.html")


@app.route("/register/citizen", methods=["GET", "POST"])
def citizen_register():
    if request.method == "POST":
        result = register_citizen_response(request.form)
        if result is not None:
            return result
    return render_template("citizen_register.html")


@app.route("/login/citizen", methods=["GET", "POST"])
def citizen_login():
    return handle_role_login("citizen", "Citizen login", "Enter the email and password for your citizen account.")


@app.route("/login/officer", methods=["GET", "POST"])
def officer_login():
    return handle_role_login(
        "village_officer", "Village Officer login",
        "Sign in with the official email or assigned username issued by your administrator.",
    )


@app.route("/login/admin", methods=["GET", "POST"])
def admin_login():
    return handle_role_login(
        "system_admin", "System Administrator login",
        "This protected account is created through the one-time administrator bootstrap.",
    )


def handle_role_login(role, title, description):
    if request.method == "POST":
        payload = auth_payload()
        identifier = str(payload.get("email", payload.get("username", ""))).strip()
        password = str(payload.get("password", ""))
        if not identifier or len(identifier) > 254 or len(password) > 256:
            message = "Credentials were not recognized, or this account is not active."
            if request.path.startswith("/api/"):
                return jsonify({"error": message}), 401
            flash(message, "error")
        else:
            user, limited = login_for_role(role, identifier, password)
            if limited:
                message = "Too many sign-in attempts. Try again in 15 minutes."
                if request.path.startswith("/api/"):
                    return jsonify({"error": message}), 429
                flash(message, "error")
                return render_template(
                    "role_login.html", title=title, description=description, role=role
                ), 429
            elif user is None:
                message = "Credentials were not recognized, or this account is not active."
                if request.path.startswith("/api/"):
                    return jsonify({"error": message}), 401
                flash(message, "error")
            else:
                establish_login(user)
                if request.path.startswith("/api/"):
                    return jsonify(
                        {"user": public_user(user), "csrf_token": session["_csrf_token"]}
                    )
                if user["role"] == "village_officer":
                    return redirect(url_for("officer_dashboard"))
                next_url = request.args.get("next", "")
                if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
                    return redirect(next_url)
                return redirect(login_redirect(user))
    if request.path.startswith("/api/"):
        return jsonify({"error": "Method not allowed."}), 405
    return render_template(
        "role_login.html", title=title, description=description, role=role
    )


def public_user(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "assigned_village_id": user["assigned_village_id"],
        "department": user["department"],
    }


@app.get("/api/auth/csrf")
def api_csrf_token():
    return jsonify({"csrf_token": session["_csrf_token"]})


@app.post("/api/auth/citizen/register")
def api_citizen_register():
    return register_citizen_response(auth_payload(), json_response=True)


@app.post("/api/auth/citizen/login")
def api_citizen_login():
    return handle_role_login("citizen", "Citizen login", "")


@app.post("/api/auth/officer/login")
def api_officer_login():
    return handle_role_login("village_officer", "Village Officer login", "")


@app.post("/api/auth/admin/login")
def api_admin_login():
    return handle_role_login("system_admin", "System Administrator login", "")


@app.get("/api/auth/me")
def api_auth_me():
    user = getattr(g, "current_user", None)
    if user is None:
        return jsonify({"error": "Authentication required.", "csrf_token": session["_csrf_token"]}), 401
    return jsonify({"user": public_user(user), "csrf_token": session["_csrf_token"]})


@app.post("/api/auth/logout")
def api_auth_logout():
    user = getattr(g, "current_user", None)
    if user is not None:
        db = get_db()
        db.execute(
            "UPDATE users SET session_version=session_version+1 WHERE id=?",
            (user["id"],),
        )
        db.commit()
    session.clear()
    session["_csrf_token"] = secrets.token_urlsafe(32)
    return jsonify({"message": "Signed out."})


@app.route("/login", methods=["GET", "POST"])
def login():
    return redirect(url_for("admin_login", **request.args))


@app.route("/admin/officers")
@admin_required
def admin_officers():
    officers = get_db().execute(
        """SELECT users.*, villages.name AS village_name
           FROM users LEFT JOIN villages ON villages.id = users.assigned_village_id
           WHERE users.role = 'village_officer' ORDER BY users.created_at DESC"""
    ).fetchall()
    return render_template("admin_officers.html", officers=officers)


@app.route("/admin/officers/new", methods=["GET", "POST"])
@admin_required
def admin_create_officer():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        try:
            email = validate_email(request.form.get("email", ""))
            password = validate_password(request.form.get("password", ""))
            village_id = int(request.form.get("assigned_village_id", ""))
        except ValueError as error:
            flash(str(error), "error")
        else:
            if not 2 <= len(name) <= 100 or len(department) > 100:
                flash("Enter a valid officer name and department.", "error")
            elif not db.execute("SELECT id FROM villages WHERE id = ?", (village_id,)).fetchone():
                flash("Choose an existing village.", "error")
            else:
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                try:
                    db.execute(
                        """INSERT INTO users
                           (username, password_hash, role, name, email, assigned_village_id,
                            department, is_approved, is_active, can_import, created_at, updated_at)
                           VALUES (?, ?, 'village_officer', ?, ?, ?, ?, 0, 0, ?, ?, ?)""",
                        (
                            email, generate_password_hash(password), name, email, village_id,
                            department or None, int(request.form.get("can_import") == "yes"), now, now,
                        ),
                    )
                    db.commit()
                except sqlite3.IntegrityError:
                    db.rollback()
                    flash("An account with that email already exists.", "error")
                else:
                    flash("Officer account created. Approve and activate it before first sign-in.", "success")
                    return redirect(url_for("admin_officers"))
    villages = db.execute("SELECT id, name FROM villages ORDER BY name").fetchall()
    return render_template("officer_form.html", officer=None, villages=villages)


@app.route("/admin/officers/<int:officer_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_edit_officer(officer_id):
    db = get_db()
    officer = db.execute(
        "SELECT * FROM users WHERE id = ? AND role = 'village_officer'", (officer_id,)
    ).fetchone()
    if officer is None:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        approved = request.form.get("is_approved") == "yes"
        active = request.form.get("is_active") == "yes" and approved
        can_import = request.form.get("can_import") == "yes"
        try:
            email = validate_email(request.form.get("email", ""))
            village_id = int(request.form.get("assigned_village_id", ""))
        except ValueError as error:
            flash(str(error), "error")
        else:
            if not 2 <= len(name) <= 100 or len(department) > 100:
                flash("Enter a valid officer name and department.", "error")
            elif not db.execute("SELECT id FROM villages WHERE id = ?", (village_id,)).fetchone():
                flash("Choose an existing village.", "error")
            else:
                now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                try:
                    db.execute(
                        """UPDATE users SET username=?, name=?, email=?, assigned_village_id=?,
                           department=?, is_approved=?, is_active=?, can_import=?, updated_at=?
                           WHERE id=? AND role='village_officer'""",
                        (
                            email, name, email, village_id, department or None,
                            int(approved), int(active), int(can_import), now, officer_id,
                        ),
                    )
                    db.commit()
                except sqlite3.IntegrityError:
                    db.rollback()
                    flash("An account with that email already exists.", "error")
                else:
                    flash("Officer account updated.", "success")
                    return redirect(url_for("admin_officers"))
    villages = db.execute("SELECT id, name FROM villages ORDER BY name").fetchall()
    return render_template("officer_form.html", officer=officer, villages=villages)


@app.post("/admin/officers/<int:officer_id>/reset-password")
@admin_required
def admin_reset_officer_password(officer_id):
    officer = get_db().execute(
        "SELECT id FROM users WHERE id = ? AND role = 'village_officer'",
        (officer_id,),
    ).fetchone()
    if officer is None:
        abort(404)
    try:
        password = validate_password(request.form.get("password", ""))
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin_edit_officer", officer_id=officer_id))
    db = get_db()
    db.execute(
        """UPDATE users SET password_hash=?, session_version=session_version+1,
           updated_at=? WHERE id=? AND role='village_officer'""",
        (
            generate_password_hash(password),
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            officer_id,
        ),
    )
    db.commit()
    flash("Officer password reset. Any existing officer sessions have been signed out.", "success")
    return redirect(url_for("admin_edit_officer", officer_id=officer_id))


@app.post("/api/admin/officers")
@api_roles_required("system_admin")
def api_create_officer():
    payload = auth_payload()
    name = str(payload.get("name", "")).strip()
    department = str(payload.get("department", "")).strip()
    try:
        email = validate_email(str(payload.get("email", "")))
        password = validate_password(str(payload.get("password", "")))
        village_id = int(payload.get("assigned_village_id", ""))
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error) or "Enter valid officer details."}), 400
    if not 2 <= len(name) <= 100 or len(department) > 100:
        return jsonify({"error": "Enter a valid officer name and department."}), 400
    db = get_db()
    if not db.execute("SELECT id FROM villages WHERE id = ?", (village_id,)).fetchone():
        return jsonify({"error": "Choose an existing village."}), 400
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        cursor = db.execute(
            """INSERT INTO users
               (username, password_hash, role, name, email, assigned_village_id,
                department, is_approved, is_active, can_import, created_at, updated_at)
               VALUES (?, ?, 'village_officer', ?, ?, ?, ?, 0, 0, ?, ?, ?)""",
            (
                email, generate_password_hash(password), name, email, village_id,
                department or None, int(payload.get("can_import") is True), now, now,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"error": "An account with that email already exists."}), 409
    officer = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"officer": public_user(officer), "is_approved": False, "is_active": False}), 201


@app.patch("/api/admin/officers/<int:officer_id>")
@api_roles_required("system_admin")
def api_update_officer(officer_id):
    payload = auth_payload()
    db = get_db()
    officer = db.execute(
        "SELECT * FROM users WHERE id=? AND role='village_officer'", (officer_id,)
    ).fetchone()
    if officer is None:
        return jsonify({"error": "Officer account not found."}), 404
    allowed_fields = {
        "name", "email", "assigned_village_id", "department",
        "is_approved", "is_active", "can_import",
    }
    if not isinstance(payload, dict) or set(payload) - allowed_fields:
        return jsonify({"error": "The request contains unsupported fields."}), 400
    for field in ("is_approved", "is_active", "can_import"):
        if field in payload and not isinstance(payload[field], bool):
            return jsonify({"error": f"{field} must be true or false."}), 400
    name = str(payload.get("name", officer["name"])).strip()
    department = str(payload.get("department", officer["department"] or "")).strip()
    try:
        email = validate_email(str(payload.get("email", officer["email"])))
        village_id = int(payload.get("assigned_village_id", officer["assigned_village_id"]))
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error) or "Enter valid officer details."}), 400
    if not 2 <= len(name) <= 100 or len(department) > 100:
        return jsonify({"error": "Enter a valid officer name and department."}), 400
    if not db.execute("SELECT id FROM villages WHERE id = ?", (village_id,)).fetchone():
        return jsonify({"error": "Choose an existing village."}), 400
    approved = bool(payload.get("is_approved", officer["is_approved"]))
    active = bool(payload.get("is_active", officer["is_active"])) and approved
    can_import = bool(payload.get("can_import", officer["can_import"]))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        db.execute(
            """UPDATE users SET username=?, name=?, email=?, assigned_village_id=?,
               department=?, is_approved=?, is_active=?, can_import=?, updated_at=?
               WHERE id=? AND role='village_officer'""",
            (
                email, name, email, village_id, department or None,
                int(approved), int(active), int(can_import), now, officer_id,
            ),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify({"error": "An account with that email already exists."}), 409
    updated = db.execute("SELECT * FROM users WHERE id=?", (officer_id,)).fetchone()
    return jsonify(
        {
            "officer": public_user(updated),
            "is_approved": bool(updated["is_approved"]),
            "is_active": bool(updated["is_active"]),
            "can_import": bool(updated["can_import"]),
        }
    )


@app.get("/officer/profile")
@roles_required("village_officer")
def officer_profile():
    return redirect(url_for("officer_dashboard"))


@app.post("/logout")
def logout():
    user = getattr(g, "current_user", None)
    if user is not None:
        db = get_db()
        db.execute(
            "UPDATE users SET session_version=session_version+1 WHERE id=?",
            (user["id"],),
        )
        db.commit()
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth_landing"))


@app.cli.command("bootstrap-admin")
def bootstrap_admin_command():
    """Create the first system administrator from environment variables."""
    import click

    name = os.environ.get("SMART_VILLAGE_ADMIN_NAME", "").strip()
    raw_email = os.environ.get("SMART_VILLAGE_ADMIN_EMAIL", "").strip()
    password = os.environ.get("SMART_VILLAGE_ADMIN_PASSWORD", "")
    if not name or not raw_email or not password:
        raise click.ClickException(
            "Set SMART_VILLAGE_ADMIN_NAME, SMART_VILLAGE_ADMIN_EMAIL, and "
            "SMART_VILLAGE_ADMIN_PASSWORD before bootstrapping."
        )
    try:
        email = validate_email(raw_email)
        validate_password(password)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    if not 2 <= len(name) <= 100:
        raise click.ClickException("Administrator name must be between 2 and 100 characters.")
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA foreign_keys = ON")
    try:
        existing_admin = db.execute(
            "SELECT 1 FROM users WHERE role='system_admin' AND is_active=1 AND is_approved=1 LIMIT 1"
        ).fetchone()
        if existing_admin:
            raise click.ClickException("An active system administrator already exists.")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        db.execute(
            """INSERT INTO users
               (username, password_hash, role, name, email, is_approved, is_active,
                created_at, updated_at)
               VALUES (?, ?, 'system_admin', ?, ?, 1, 1, ?, ?)""",
            (email, generate_password_hash(password), name, email, now, now),
        )
        db.commit()
    except sqlite3.IntegrityError as error:
        db.rollback()
        raise click.ClickException("That email already belongs to an account.") from error
    finally:
        db.close()
    click.echo(f"System administrator account created for {email}.")


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="That page or record could not be found."), 404


@app.errorhandler(400)
def bad_request(error):
    message = getattr(error, "description", "The request could not be processed.")
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), 400
    return render_template("error.html", code=400, message=message), 400


@app.errorhandler(403)
def forbidden(_error):
    message = "Your account does not have permission to access this page."
    if request.path.startswith("/api/"):
        return jsonify({"error": message}), 403
    return render_template("error.html", code=403, message=message), 403


@app.errorhandler(413)
def request_too_large(_error):
    return render_template(
        "error.html", code=413, message="The uploaded request is too large. Complaint photos must be 5 MB or smaller."
    ), 413


init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
