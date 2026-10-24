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

- **Public sign-in page:** `/auth` shows Citizen Login/Register and Village Officer Login/registration. Administrator sign-in is not advertised on the public page, and administrator management routes require an authenticated administrator account.
- **Citizen:** Register with a unique email and password, sign in separately, submit complaints, see only complaints owned by their account, and update their own name, mobile number, or password.
- **Village Officer:** `/register/officer` creates an active account only after a configured trusted adapter confirms the official ID, face match, liveness, officer authorization, and authoritative village assignment. The browser's requested village is never used as the account assignment. If no adapter is configured, the page clearly shows **DEMO MODE**, disables registration, and the backend rejects submissions without creating an account or storing ID/selfie files. No provider is configured by default, so real verification is not currently available. Use `SMART_VILLAGE_OFFICER_VERIFICATION_PROVIDER=python_module:function_name` to point the server to a reviewed adapter; configure its credentials and provider endpoints in that adapter using deployment secrets, never source control. Its function must accept `(details, identity_document_bytes, selfie_bytes)` and return a dictionary containing `id_verified`, `face_verified`, `liveness_verified`, and `authorized` set to the real provider's boolean results, plus verified `name`, `email`, `mobile_number`, `officer_identifier`, `state`, `taluk`, and the integer `assigned_village_id` from the authoritative officer registry. The adapter must reject unverifiable or unauthorized identities, use authenticated TLS with explicit bounded connect/read timeouts for every provider request, minimize retention, and raise `app.OfficerVerificationError` with a safe user-facing message when verification fails. Never use test, mock, or hardcoded success results in production. The application compares identity claims against the verified record, checks that the authoritative village exists, hashes the password, and creates the account directly. Successful registration redirects to `/login/officer`; login routes the officer to their assigned village dashboard. Configure and validate actual ID/registry and face/liveness providers before enabling the adapter. Legacy unverified pending requests cannot be activated and can only be deleted by an administrator. Officers sign in using their official email or assigned username. Officer reports at `/reports` and `/api/reports` require an active officer and always use that account's village; citizens and administrators cannot access them. The report includes village indicators, project progress, complaint summaries, facility counts, generation time, filters, and print/PDF support. The administrator can deactivate accounts and securely reset passwords, which revokes active sessions. No demo officer credentials are shipped.
- **System Administrator:** The initial administrator is bootstrapped from private environment variables. Only administrators can create, assign, approve, deactivate, and grant import permission to officer accounts.
- All browser state-changing requests use the existing CSRF-protected Flask session. Login/registration attempts are rate-limited. Sessions are rechecked against the active database account on each request.
- The same role checks are enforced in the Flask routes; hidden UI controls are not the security boundary.
- Auth pages are available at `/auth`, `/register/citizen`, `/login/citizen`, `/register/officer`, `/login/officer`, and `/login/admin`. A small cookie-session API is available at `/api/auth/*`; fetch a CSRF token from `/api/auth/csrf` and send it as `X-CSRF-Token` on state-changing API requests. This is session authentication, not JWT.

## 6. What is included

- Dashboard summary cards, a village comparison bar chart, a project-status chart, recent projects, and a village search.
- Village directory, search, and detail pages. Population and household figures show a status, data year, source, and last-updated date; figures with missing provenance are never presented as official. Existing fictional population values are marked **DEMO DATA**, and household totals remain unavailable until entered. System Administrators manage village records; officers can update statistics only for their assigned village.
- Project listing and search/status filters. System Administrators manage all projects; officers can create and update projects only in their assigned village.
- Analytics charts that update when the indicator selector changes.
- An officer-only, village-scoped report with project and complaint date/status filters, village statistics, facility counts, and print/PDF export. Choose **Print / Save as PDF** and select **Save as PDF** in the browser's print dialog.
- Server-side validation, parameterized SQLite queries, password hashing, and form security tokens.
- A responsive green dashboard with image-backed village cards, a local illustration fallback, reduced-motion-aware animations, mobile navigation, and form submission feedback.
- Officer registration with a fail-closed trusted-verification adapter contract; no ID document or selfie is retained by the application.
- A Smart Village E-Education section with searchable/filterable services and links to external education providers; dates and eligibility are not invented or copied as live data.
- Citizen complaint submission with account-owned tracking, administrator/officer review subject to village assignment, officer assignment, status audit history, filters, and category/status charts.
- Responsive GIS village and facility map using Leaflet and OpenStreetMap; map markers are shown only for coordinates explicitly verified by an administrator.
- Administrator-managed facility records linked to existing village records, without duplicating village tables.
- State, district, and taluk/block fields and officer/admin-only population and household entry. An **Official** status requires a recorded source and year, and the form asks the authorized user to check the citation; it does not independently verify submitted figures.

Chart.js is loaded from jsDelivr, and the sample photos are loaded from Unsplash. If the browser is offline, the pages and database continue to work; charts will not render and photos use a local illustration fallback. Education links open external providers in a new tab; those providers manage their own content and availability.

The GIS map loads Leaflet and OpenStreetMap tiles from their public CDNs and needs an internet connection. No paid map API key is required. The starter village records intentionally contain no coordinates: add only locations verified from a reliable source. Complaint photos are limited to 5 MB and stored under `uploads/complaints/`; access is restricted to system administrators and officers assigned to the complaint's village. Complaint tracking requires the citizen account that submitted it; public ID guessing does not expose complaint details.

Schema additions are applied safely when the app starts. Existing village, project, and password-hash data are retained. The update adds nullable verified village coordinates, facilities, complaints, status history, user email/profile/role/approval fields, officer identifiers with a uniqueness constraint, and account-owned complaint links. Legacy administrator accounts are deactivated for bootstrap because their credentials were documented publicly.

### Population and household data sources

No automatic population or household import is enabled. The official [Census of India Population Finder](https://censusindia.gov.in/census.website/data/population-finder) and [eGramSwaraj](https://egramswaraj.gov.in/) pages could not be reached in the development environment, so no public endpoint or access permission for village-level population/household data could be verified. The Government of India's [Open Government Data API directory](https://www.data.gov.in/apis) states that dataset APIs use an API key or datasets may be downloaded; the directory showed no listed APIs during this implementation. A public Census or eGramSwaraj API must not be assumed from that information.

Until an authorized, documented dataset and access method are configured, an approved Village Officer or System Administrator can record figures in the village edit form with their source and year. Selecting **Official** is an authorized user's declaration that the entry was checked against the cited source; the application does not independently verify the citation or figure. Leave unavailable values blank/unavailable. Starter population values remain explicitly labelled **DEMO DATA** and are not official statistics.

## 7. Run and test the modules

No extra Python packages are required:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. Register a citizen at **Sign in → Create account**, then sign in to submit a complaint and view its status history in **My dashboard**. Officer registration stays disabled in **DEMO MODE** until a reviewed identity-verification adapter is configured. The application does not claim that real verification works without that adapter.

To enable the provider integration after selecting and authorizing suitable ID/department-registry and face/liveness services:

1. Implement and security-review a Python adapter callable with `(details, identity_document_bytes, selfie_bytes)`. It must contact the real providers over authenticated TLS, validate provider responses, enforce officer authorization, and map the verified official record (including its assigned village) to the documented result contract above. Do not return success for test, unavailable, or indeterminate responses.
2. Keep service credentials in deployment secrets/environment variables used only by the adapter. Do not put credentials, service data, or real biometric samples in the repository, logs, or tests. Configure `SMART_VILLAGE_OFFICER_VERIFICATION_PROVIDER` as `python_module:function_name` before starting Flask.
3. Test the provider in its authorized sandbox first: valid and invalid ID, face mismatch, liveness failure, unauthorized identity, unavailable provider, duplicate email/ID, and a returned village assignment different from the browser's requested village. Confirm failures create no account and the successful account logs in only to the provider-assigned village.
4. Obtain appropriate privacy/legal approval for processing identity and biometric data, retention, consent, and incident handling before production use. Verify that the adapter and its providers do not retain images beyond the approved purpose.

Without a configured provider, no ID or selfie file inputs are offered; POST requests also fail closed with HTTP 503 and create no officer account. For demonstrations without real provider integration, use the test suite's test-only provider fixture; do not copy it into a deployment.

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
3. With no provider configured, open officer registration; confirm the three steps appear, the DEMO MODE warning is visible, submission is disabled, and no account is created. Confirm an unconfigured POST also fails closed.
4. Run the automated provider-fixture tests for verification failures, duplicates, successful registration/login, and server-authoritative village assignment. This fixture does not verify real identity.
5. Only after real provider setup, test a valid authorized officer; confirm registration redirects to officer login and subsequent sign-in lands on only the registry-assigned village dashboard, GIS map, analytics, and report.
6. While signed in as an officer, change a URL to another village/complaint/project ID or submit another village's ID in a project form; confirm the server returns HTTP 403 and makes no changes.
7. Confirm the citizen cannot open `/reports`, `/officer/reports`, or `/api/reports`, cannot see the officer Reports navigation item, and that login endpoints reject repeated failed attempts.
8. Verify admin-only officer account management, CSRF checks, and logout/session invalidation.
9. Open the GIS map; confirm villages without verified coordinates stay in the list without markers. Add verified coordinates only when checked against a reliable source.
10. Check existing public dashboard, Education, village, project, and charts. Confirm the Reports page is available only after signing in as an active Village Officer.

The automated tests create three temporary officer accounts with randomly generated test-only passwords in a temporary SQLite database; they do not add sample credentials to `database.db`. Run the authorization and regression checks from the VS Code PowerShell terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python -m unittest -v test_app
```

Then start the application for a manual demonstration:

```powershell
python app.py
```

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
│   ├── officer_register.html
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
