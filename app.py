import os
import secrets
import sqlite3
import math
from datetime import date
from functools import wraps
from hmac import compare_digest

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SMART_VILLAGE_SECRET", "local-prototype-change-this-secret"),
    DATABASE=DATABASE,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
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
            agriculture TEXT NOT NULL
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
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'viewer'))
        );
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
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
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin"),
        )
    db.commit()
    db.close()


@app.before_request
def protect_post_requests():
    session.setdefault("_csrf_token", secrets.token_urlsafe(32))
    if request.method == "POST":
        submitted_token = request.form.get("_csrf_token", "")
        if not compare_digest(session["_csrf_token"], submitted_token):
            abort(400, description="The form security token is missing or invalid. Please reload and try again.")


@app.context_processor
def inject_template_helpers():
    return {"csrf_token": lambda: session.get("_csrf_token", "")}


def admin_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_role") != "admin":
            flash("Please sign in with an administrator account to manage records.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


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
    return name, village_id, department, budget, start_date, expected_date, status


@app.route("/")
def index():
    db = get_db()
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
    rows = get_db().execute(
        """SELECT * FROM villages
           WHERE name LIKE ? OR district LIKE ?
           ORDER BY name""",
        (f"%{search}%", f"%{search}%"),
    ).fetchall()
    return render_template("villages.html", villages=rows, search=search)


@app.route("/villages/<int:village_id>")
def village_details(village_id):
    db = get_db()
    village = db.execute("SELECT * FROM villages WHERE id = ?", (village_id,)).fetchone()
    if village is None:
        abort(404)
    projects = db.execute(
        "SELECT * FROM projects WHERE village_id = ? ORDER BY start_date DESC",
        (village_id,),
    ).fetchall()
    return render_template("village_details.html", village=village, projects=projects)


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()
    village_count = db.execute("SELECT COUNT(*) FROM villages").fetchone()[0]
    project_count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    return render_template("admin.html", village_count=village_count, project_count=project_count)


@app.route("/admin/villages/new", methods=["GET", "POST"])
@admin_required
def add_village():
    if request.method == "POST":
        try:
            values = read_village_form()
            get_db().execute(
                """INSERT INTO villages
                   (name, district, population, schools, healthcare_centers,
                    road_status, water_availability, agriculture)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                values,
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
@admin_required
def edit_village(village_id):
    db = get_db()
    village = db.execute("SELECT * FROM villages WHERE id = ?", (village_id,)).fetchone()
    if village is None:
        abort(404)
    if request.method == "POST":
        try:
            values = read_village_form()
            db.execute(
                """UPDATE villages SET name=?, district=?, population=?, schools=?,
                   healthcare_centers=?, road_status=?, water_availability=?, agriculture=?
                   WHERE id=?""",
                (*values, village_id),
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
        flash("This village has projects. Move or delete those projects before deleting the village.", "error")
        return redirect(url_for("villages"))
    flash("Village deleted.", "success")
    return redirect(url_for("villages"))


@app.route("/projects")
def projects():
    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    conditions = ["(projects.name LIKE ? OR villages.name LIKE ?)"]
    parameters = [f"%{search}%", f"%{search}%"]
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


@app.route("/analytics")
def analytics():
    villages = get_db().execute("SELECT * FROM villages ORDER BY name").fetchall()
    project_statuses = get_db().execute(
        "SELECT status, COUNT(*) AS total FROM projects GROUP BY status"
    ).fetchall()
    return render_template("analytics.html", villages=villages, project_statuses=project_statuses)


@app.route("/reports")
def reports():
    db = get_db()
    villages = db.execute("SELECT * FROM villages ORDER BY name").fetchall()
    project_total = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    attention_villages = [
        village for village in villages
        if village["water_availability"] < 70 or village["road_status"] == "Needs improvement"
    ]
    return render_template(
        "reports.html",
        villages=villages,
        project_total=project_total,
        attention_villages=attention_villages,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is not None and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["user_role"] = user["role"]
            session["_csrf_token"] = secrets.token_urlsafe(32)
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//") and "\\" not in next_url:
                return redirect(next_url)
            return redirect(url_for("admin_dashboard"))
        flash("Username or password was not recognized.", "error")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("index"))


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="That page or record could not be found."), 404


init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
