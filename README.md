# A.R.I.S.E — Automated Resilient Intelligent Student Attendance Ecosystem

A.R.I.S.E is a simple, reliable attendance server built with Flask and SQLite that integrates with ESP32 fingerprint scanners for biometric attendance. It provides admin, teacher and student web interfaces, supports session management, offline device queueing, and session report exports.

---

## 🔍 Overview

A.R.I.S.E is designed to make classroom attendance fast and verifiable. Teachers can start and manage sessions, students can check their attendance, and administrative users can manage semesters, courses, teachers and students. An ESP32-based Smart Scanner communicates with this server to mark attendance via scanned fingerprints.

## ✨ Key Features

- Admin panel for managing semesters, teachers, students, courses and enrollments
- Teacher dashboard to start/end/extend sessions, manually mark attendance and export session reports to Excel
- Student portal to view personal attendance and course history
- ESP32 Smart Scanner firmware (offline queue + heartbeat + server sync)
- JWT-based authentication for API endpoints
- Exports to XLSX using openpyxl

---

## 📁 Repository structure (important files)

- `server.py` — Flask backend and API routes
- `database_setup.py` — Creates the SQLite schema and a default admin for first-time setup
- `attendance.db` — (created at runtime by `database_setup.py`)
- `templates/` — HTML templates for admin, teacher and student pages
- `static/js/` & `static/css/` — Frontend assets and client-side logic
- `FirmwareCodeOfEsp32/` — ESP32 fingerprint scanner firmware (Arduino/PlatformIO sketch)

---

## ⚙️ Quick start (Windows, cmd.exe)S

1. Clone the repo and change into the project folder
<br>

2. activate a virtual environment using your terminal:
  <code>.\venv\Scripts\activate</code>
<br>
3. (Optional )Install dependencies (example):
	<code>pip install flask PyJWT apscheduler openpyxl</code>
<br>
4. Initialize the database (creates tables and a default admin):
<code>python database_setup.py</code>
	Default admin credentials created by this script:
	Username: `admin`
	Password: `admin`
  <br>

5. Run the server:

	python server.py

	The server listens by default on http://0.0.0.0:5000/. Open `/admin` to access the admin interface.

---

## 🔌 ESP32 Smart Scanner

The firmware is in `FirmwareCodeOfEsp32/sketch_oct8a/`. You can upload it using Arduino IDE or PlatformIO. The firmware uses the fingerprint sensor to obtain a class roll ID and POSTs the attendance to the server. It also supports device heartbeat and offline queueing when the network is unavailable.

Tips:

- Configure Wi‑Fi and server address on the device before use
- Ensure the scanner's libraries (`Adafruit_Fingerprint`, `ArduinoJson`, etc.) are installed

---

## 🧾 API (selected endpoints)

The server exposes REST endpoints for the admin, teacher, student and device interactions. Examples:

- `POST /api/admin/login` — Admin login (returns JWT)
- `POST /api/teacher/start-session` — Start a new session for a course
- `GET /api/session-status` — Device checks if a session is active
- `POST /api/mark-attendance-by-roll-id` — Mark a roll ID as present

Example curl (mark attendance):

```
curl -X POST -H "Content-Type: application/json" \
  -d '{"class_roll_id": 123}' \
  http://<server>:5000/api/mark-attendance-by-roll-id
```

See `server.py` for the full list of routes and behaviors.

---

## ✅ Good practices

- Move secrets (like `SECRET_KEY`) to environment variables for production
- Add a `requirements.txt` to freeze dependencies
- Use a proper WSGI server (Gunicorn/uWSGI) and HTTPS in production
- Add tests and a basic CI pipeline for stability

---

## 🛠 Troubleshooting

- "Server not reachable": Ensure `server.py` is running and the port is open
- "Invalid credentials": If the DB was recreated, default admin is `admin/admin` only if `database_setup.py` ran
- Duplicate or 'Not enrolled' responses: verify enrollments and that devices are sending the correct class roll ID

---

