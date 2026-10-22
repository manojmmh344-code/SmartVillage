# Smart Village Informatics and Development Dashboard

A beginner-friendly Flask, SQLite, HTML, CSS, JavaScript, and Chart.js college project. It keeps fictional village and development-project records in a local SQLite database and displays them in a responsive dashboard.

> **Important:** All starter villages, populations, facilities, budgets, dates, and projects are fictional sample data. This project does not access live government systems and must not be used as an official source.

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

## 4. Start the application

```powershell
python app.py
```

Open <http://127.0.0.1:5000> in your browser. The SQLite file `database.db` is created automatically the first time the application runs. It is kept between restarts, so edits remain saved.

## 5. Demo administrator account

- Username: `admin`
- Password: `admin123`

Sign in using **Administrator login** to open the administration panel and add, edit, or delete village and project records. Change the demo password and configure a strong secret before any shared or public deployment. For example, set an environment secret in PowerShell before starting:

```powershell
$env:SMART_VILLAGE_SECRET = "replace-this-with-a-long-random-secret"
python app.py
```

The password is stored as a Werkzeug password hash, not plain text. This login is only a learning prototype: before real-world use it needs stronger account management, password reset and policy controls, HTTPS, secure deployment settings, and a security review.

## 6. What is included

- Dashboard summary cards, a village comparison bar chart, a project-status chart, recent projects, and a village search.
- Village directory, search, detail pages, and administrator-only create, edit, and delete actions.
- Project listing, search/status filters, and administrator-only create, edit, and delete actions.
- Analytics charts that update when the indicator selector changes.
- A printable village summary report. Choose **Print / Save as PDF** and select **Save as PDF** in the browser's print dialog.
- Server-side validation, parameterized SQLite queries, password hashing, and form security tokens.

Chart.js is loaded from jsDelivr. If the browser is offline, the pages and database continue to work, but charts will not render.

## 7. Resetting the sample database

The database is deliberately persistent. To start over, stop the application and delete only the generated `database.db` file from this project folder, then run `python app.py` again. The fictional starter records and demo administrator account will be created again.

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
│   ├── login.html
│   ├── admin.html
│   ├── village_form.html
│   ├── project_form.html
│   └── error.html
└── static/
    ├── css/style.css
    └── js/dashboard.js
```
