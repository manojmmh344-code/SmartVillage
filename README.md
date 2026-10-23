# Smart Village Informatics and Development Dashboard

A beginner-friendly Flask, SQLite, HTML, CSS, JavaScript, and Chart.js college project. It keeps fictional village and development-project records in a local SQLite database and displays them in a responsive dashboard.

> **Important:** All starter villages, populations, facilities, budgets, dates, and projects are fictional sample data. This project does not access live government systems and must not be used as an official source.
>
> The referenced flow diagram proposes React, Express, MongoDB/Mongoose, and JWT. This existing project is server-rendered Flask with SQLite and signed, HttpOnly-cookie sessions. The authentication work stays on this established stack rather than destructively migrating the application.

## 1. Requirements

- Python 3.9 or newer
- Visual Studio Code
- A web browser
- Internet access for the Chart.js CDN (the website itself does not use paid APIs)

## 2. Open the project in VS Code

Open this project folder in VS Code, then open **Terminal → New Terminal**. The commands below use Windows PowerShell.

## 3. Create a virtual environment and install Flask

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks environment activation, run the following in the current terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Bootstrap the first System Administrator and start the app

There is no public administrator registration and no default administrator password. Set a private initial account in the PowerShell terminal, then run the one-time bootstrap command:

```powershell
$env:SMART_VILLAGE_ADMIN_NAME = "Village System Administrator"
$env:SMART_VILLAGE_ADMIN_EMAIL = "admin@example.org"
$env:SMART_VILLAGE_ADMIN_PASSWORD = "choose-a-private-password-of-at-least-12-characters"
$env:SMART_VILLAGE_SECRET = "replace-with-a-long-random-secret"
python -m flask --app app bootstrap-admin
Remove-Item Env:SMART_VILLAGE_ADMIN_PASSWORD
python app.py
```

The Flask CLI initializes `database.db` and its migrations before bootstrapping, so run the command before starting the web server. The bootstrap command refuses to create another administrator once an active one exists. Citizen and officer passwords are hashed using Werkzeug's built-in scrypt password hashing. Set `SMART_VILLAGE_COOKIE_SECURE=1` when serving the site over HTTPS; keep a strong, stable `SMART_VILLAGE_SECRET` outside source control in any deployment. The sample legacy `admin` account is migrated as inactive because its old password was publicly documented; bootstrap a new administrator before using the protected administration area.

Open <http://127.0.0.1:5000> in your browser after the server starts. The SQLite file is created automatically and kept between restarts.

## 5. Authentication and roles

- **Citizen:** Register with a unique email and password, sign in separately, submit complaints, see only complaints owned by their account, and update their own name, mobile number, or password.
- **Village Officer:** Cannot self-register. A System Administrator creates an account with a village assignment, department, and optional import permission, then explicitly approves and activates it. Officer pages and database queries are scoped to that assigned village. The current project has no data-import endpoint, so no import action is available yet.
- **System Administrator:** The initial administrator is bootstrapped from private environment variables. Only administrators can create, assign, approve, deactivate, and grant import permission to officer accounts.
- All browser state-changing requests use the existing CSRF-protected Flask session. Login/registration attempts are rate-limited. Sessions are rechecked against the active database account on each request.
- The same role checks are enforced in the Flask routes; hidden UI controls are not the security boundary.
- Auth pages are available at `/auth`, `/register/citizen`, `/login/citizen`, `/login/officer`, and `/login/admin`. A small cookie-session API is available at `/api/auth/*`; fetch a CSRF token from `/api/auth/csrf` and send it as `X-CSRF-Token` on state-changing API requests. This is session authentication, not JWT.

## 6. What is included

- Dashboard summary cards, a village comparison bar chart, a project-status chart, recent projects, and a village search.
- Village directory, search, and detail pages. System Administrators manage village records; officers can update statistics only for their assigned village.
- Project listing and search/status filters. System Administrators manage all projects; officers can create and update projects only in their assigned village.
- Analytics charts that update when the indicator selector changes.
- A printable village summary report. Choose **Print / Save as PDF** and select **Save as PDF** in the browser's print dialog.
- Server-side validation, parameterized SQLite queries, password hashing, and form security tokens.
- A responsive green dashboard with image-backed village cards, a local illustration fallback, reduced-motion-aware animations, mobile navigation, and form submission feedback.
- A Smart Village E-Education section with searchable/filterable services and links to external education providers; dates and eligibility are not invented or copied as live data.
- Citizen complaint submission with account-owned tracking, administrator/officer review subject to village assignment, officer assignment, status audit history, filters, and category/status charts.
- Responsive GIS village and facility map using Leaflet and OpenStreetMap; map markers are shown only for coordinates explicitly verified by an administrator.
- Administrator-managed facility records linked to existing village records, without duplicating village tables.

Chart.js is loaded from jsDelivr, and the sample photos are loaded from Unsplash. If the browser is offline, the pages and database continue to work; charts will not render and photos use a local illustration fallback. Education links open external providers in a new tab; those providers manage their own content and availability.

The GIS map loads Leaflet and OpenStreetMap tiles from their public CDNs and needs an internet connection. No paid map API key is required. The starter village records intentionally contain no coordinates: add only locations verified from a reliable source. Complaint photos are limited to 5 MB and stored under `uploads/complaints/`; access is restricted to system administrators and officers assigned to the complaint's village. Complaint tracking requires the citizen account that submitted it; public ID guessing does not expose complaint details.

Schema additions are applied safely when the app starts. Existing village, project, and password-hash data are retained. The update adds nullable verified village coordinates, facilities, complaints, status history, user email/profile/role/approval fields, and account-owned complaint links. Legacy administrator accounts are deactivated for bootstrap because their credentials were documented publicly.

## 7. Run and test the modules

No extra Python packages are required:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. Register a citizen at **Sign in → Create account**, then sign in to submit a report and view its status history in **My dashboard**. Sign in as the System Administrator to search complaints, create an officer, and approve the officer account.

Open **GIS Village Map** to filter the existing sample villages and facilities. Starter villages are fictional and do not have verified coordinates, so their entries appear in the village list without false map pins. As an administrator, add a facility or edit a village and enter coordinates only after verifying them from a trusted source; tick the verification checkbox to allow the marker to appear. No real coordinates are included as sample data.

Example manual complaint (fictional; submit after signing in as a citizen):

- Citizen name: Demo Citizen
- Village: Greenfield
- Category: Drinking Water
- Title: Water tap needs repair
- Description: The public water tap near the community hall is not working.
- Location: Near the community hall
- Mobile number and photo: leave blank for a privacy-safe basic test

Quick checklist:

1. Register a citizen with matching passwords; confirm a duplicate email is rejected and the account role is `citizen`.
2. Sign in as the citizen; submit a complaint and confirm only that account can see its history.
3. Sign in as System Administrator; create an officer assigned to Greenfield and confirm the officer cannot sign in before approval.
4. Approve and activate the officer; verify the assigned village dashboard, project/report filters, and village complaint management.
5. While signed in as the officer, change a URL to another village/complaint/project ID; confirm the server denies access.
6. Confirm the citizen cannot open officer or administrator pages, and that login endpoints reject repeated failed attempts.
7. Verify admin-only officer creation/assignment/deactivation, CSRF checks, and logout/session invalidation.
8. Open the GIS map; confirm villages without verified coordinates stay in the list without markers. Add verified coordinates only when checked against a reliable source.
9. Check existing public dashboard, Education, village, project, charts, and reports pages.

## 8. Resetting the sample database

The database is deliberately persistent. Schema migrations retain existing records. Do not delete `database.db` to troubleshoot authentication. On a new database, bootstrap a System Administrator using the private environment variables above.

## Project structure

```text
Smartvillage/
├── app.py
├── database.db                 # created automatically when app.py runs
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── villages.html
│   ├── village_details.html
│   ├── projects.html
│   ├── analytics.html
│   ├── reports.html
│   ├── education.html
│   ├── education_service.html
│   ├── login.html
│   ├── auth_landing.html
│   ├── citizen_register.html
│   ├── role_login.html
│   ├── citizen_dashboard.html
│   ├── citizen_profile.html
│   ├── officer_dashboard.html
│   ├── officer_complaints.html
│   ├── officer_projects.html
│   ├── admin_officers.html
│   ├── officer_form.html
│   ├── admin.html
│   ├── admin_complaints.html
│   ├── admin_complaint_details.html
│   ├── complaint_form.html
│   ├── track_complaint.html
│   ├── gis_map.html
│   ├── facility_form.html
│   ├── village_form.html
│   ├── project_form.html
│   └── error.html
└── static/
    ├── css/style.css
    ├── css/auth.css
    ├── css/education.css
    ├── css/modules.css
    ├── js/dashboard.js
    ├── js/auth.js
    ├── js/education.js
    ├── js/complaints.js
    ├── js/gis_map.js
    └── images/
        ├── education-fallback.svg
        └── village-fallback.svg
```
