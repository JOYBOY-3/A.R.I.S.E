<p align="center">
  <img src="https://img.shields.io/badge/Flask-3.1-blue?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/Python-3.10+-green?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/SQLite-3-003B57?logo=sqlite" alt="SQLite">
  <img src="https://img.shields.io/badge/ESP32-IoT-red?logo=espressif" alt="ESP32">
  <img src="https://img.shields.io/badge/Chart.js-4.x-FF6384?logo=chartdotjs" alt="Chart.js">
  <img src="https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render" alt="Render">
</p>

# A.R.I.S.E. — Automated Resilient Intelligent Student Attendance Ecosystem

> A full-stack, hybrid (offline + online), biometric-enabled attendance management system built for educational institutions — runs from a USB pendrive locally and syncs to the cloud.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Architecture](#-architecture)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Database Schema](#-database-schema)
- [Screenshots](#-screenshots)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [Deployment (Render Cloud)](#-deployment-render-cloud)
- [Cloud Sync Engine](#-cloud-sync-engine)
- [API Reference](#-api-reference)
- [Online Class Attendance](#-online-class-attendance)
- [ESP32 Smart Scanner](#-esp32-smart-scanner)
- [Admin Analytics Dashboard](#-admin-analytics-dashboard)
- [Project Structure](#-project-structure)
- [Security](#-security)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## 🔍 Overview

**A.R.I.S.E.** is designed for institutions that need a portable, reliable attendance system. The core server runs from a **USB pendrive** on any computer in the classroom — no internet required for daily use. When internet is available, it automatically **syncs to a cloud replica** on Render.com, enabling:

- **Offline classes** → Biometric (ESP32 fingerprint) or manual attendance via the local server
- **Online classes** → OTP-based attendance via the cloud server with a shareable link
- **Both records** are merged on the cloud with zero data loss

### Who uses it?

| Role | What they do |
|------|-------------|
| **Admin** | Manages semesters, teachers, students, courses, enrollments. Views analytics dashboard |
| **Teacher** | Starts sessions, monitors attendance in real-time, exports reports to Excel |
| **Student** | Views personal attendance, course history, streak analytics, and leaderboard |
| **ESP32 Scanner** | Marks biometric attendance via fingerprint scanning during offline sessions |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        A.R.I.S.E. Architecture                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   LOCAL (USB Pendrive)                CLOUD (Render.com)            │
│   ┌──────────────────┐               ┌──────────────────┐          │
│   │  Flask Server     │──── sync ────▶│  Flask Server     │         │
│   │  SQLite DB        │   (auto 5m)   │  SQLite DB        │         │
│   │  Port 5000        │               │  Port 443 (HTTPS) │         │
│   └──────┬───────────┘               └──────┬───────────┘          │
│          │                                   │                      │
│   ┌──────┴───────────┐               ┌──────┴───────────┐          │
│   │ ESP32 Scanner     │               │ Online Attendance │         │
│   │ (Fingerprint)     │               │ (OTP via browser) │         │
│   └──────────────────┘               └──────────────────┘          │
│                                                                     │
│   ┌──────────────────┐                                              │
│   │ Admin / Teacher / │   ← All web UIs work on both               │
│   │ Student Portals   │     local and cloud servers                 │
│   └──────────────────┘                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Sync Strategy: Smart Merge

The sync engine ensures **no data loss** between local and cloud:

1. **Local → Cloud push**: Local DB is the master for admin data (students, courses, etc.)
2. **Online records preserved**: Before replacing the cloud DB, all online session records are extracted, the DB is replaced, then online records are re-inserted with remapped IDs
3. **Result**: Cloud always has **both** online + offline attendance records

---

## ✨ Key Features

### 🎓 Admin Panel
- Full CRUD management for **semesters, teachers, students, courses**
- **Course enrollment** manager with drag-and-drop-style student assignment
- **Enrollment roster** view by semester
- **Batch configuration** (batch name, system settings)
- **Analytics dashboard** with 4 sub-tabs:
  - **Overview** — 8 KPI cards + course-wise summary table
  - **Course Analytics** — Per-student attendance breakdown with status badges
  - **Student Lookup** — Cross-course attendance for any student
  - **Trends** — Chart.js charts: daily, day-of-week, online vs offline, course comparison
- **Cloud sync** controls (manual push, status check)

### 👨‍🏫 Teacher Dashboard
- **Start/end/extend** attendance sessions for any assigned course
- **Real-time attendance monitoring** — see who's present live
- **Manual override** — mark individual students present/absent with reason
- **Emergency bulk mark** — mark all enrolled students present at once
- **Session history** with full session detail view
- **Excel export** — download per-session attendance reports (.xlsx)
- **Course analytics** — attendance trends and statistics per course
- **Online class mode** — start online sessions with OTP-based verification (cloud only)
- **Device status** monitoring for connected ESP32 scanners

### 👩‍🎓 Student Portal
- **Personal dashboard** with overall attendance percentage
- **Per-course breakdown** with detailed session-by-session history
- **Critical alerts** when attendance drops below threshold
- **Attendance streaks** and leaderboard
- **Semester filter** to view historical data
- **Visual analytics** with attendance trends

### 🌐 Online Class Attendance
- Teacher starts online session on cloud server → gets a shareable link
- Students open link in browser → enter roll number + rotating OTP
- **OTP refreshes every 30 seconds** preventing screenshot sharing
- Teacher can also **manually override** online attendance
- Available **only on cloud server** — local server redirects to cloud

### 📡 ESP32 Smart Scanner
- Fingerprint-based biometric attendance marking
- **Offline queue** — stores marks locally when server is unreachable
- **Auto-flush** — sends queued records when connection restores
- **Heartbeat** — periodic health check with the server
- **Session-aware** — only marks during active sessions

### 🔄 Cloud Sync
- **Automatic sync** every 5 minutes (configurable)
- **Smart merge** — preserves online records, syncs offline records
- **Full binary snapshot** via SQLite backup API for consistency
- **API key** authentication between local and cloud
- **Status monitoring** via `/api/sync/status`

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, Flask 3.1, Gunicorn (production) |
| **Database** | SQLite 3 (portable, zero-config) |
| **Authentication** | JWT (PyJWT), bcrypt password hashing |
| **Security** | Flask-Limiter (rate limiting), Flask-CORS |
| **Frontend** | Vanilla HTML/CSS/JS (no frameworks — fast loading) |
| **Charts** | Chart.js 4.x (admin analytics + student analytics) |
| **Excel Export** | openpyxl |
| **Scheduling** | APScheduler (session auto-expiry, sync) |
| **IoT** | ESP32 + Adafruit Fingerprint sensor |
| **Config** | python-dotenv (.env files) |
| **Cloud** | Render.com (free tier compatible) |

---

## 🗄 Database Schema

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│   admins     │    │  semesters   │    │   teachers   │
│─────────────│    │─────────────│    │──────────────│
│ id (PK)      │    │ id (PK)      │    │ id (PK)      │
│ username     │    │ semester_name│    │ teacher_name │
│ password     │    └──────┬──────┘    │ pin          │
└─────────────┘           │            └──────┬───────┘
                          │                   │
                   ┌──────┴───────────────────┴──────┐
                   │           courses                │
                   │─────────────────────────────────│
                   │ id (PK)                          │
                   │ semester_id (FK → semesters)     │
                   │ teacher_id (FK → teachers)       │
                   │ course_name, course_code          │
                   │ default_duration_minutes          │
                   └──────┬───────────────────┬──────┘
                          │                   │
              ┌───────────┴──┐         ┌──────┴──────────┐
              │  enrollments │         │    sessions      │
              │──────────────│         │─────────────────│
              │ student_id   │         │ id (PK)          │
              │ course_id    │         │ course_id (FK)   │
              │ class_roll_id│         │ start_time       │
              │ (PK: s_id,  │         │ end_time         │
              │  c_id)       │         │ is_active        │
              └──────┬───────┘         │ session_type     │
                     │                 │ topic, otp_seed  │
              ┌──────┴───────┐         │ session_token    │
              │   students   │         └──────┬───────────┘
              │──────────────│                │
              │ id (PK)      │    ┌───────────┴────────────┐
              │ student_name │    │  attendance_records     │
              │ univ_roll_no │    │────────────────────────│
              │ enrollment_no│    │ id (PK)                 │
              │ password     │    │ session_id (FK)         │
              │ email1,email2│    │ student_id (FK)         │
              └──────────────┘    │ timestamp               │
                                  │ override_method         │
              ┌──────────────┐    │ manual_reason           │
              │system_settings│   └─────────────────────────┘
              │──────────────│
              │ key (PK)     │
              │ value        │
              └──────────────┘
```

**9 tables total**: `admins`, `semesters`, `teachers`, `students`, `courses`, `enrollments`, `sessions`, `attendance_records`, `system_settings`

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/JOYBOY-3/A.R.I.S.E.git
cd A.R.I.S.E

# 2. Create and activate virtual environment
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your settings (SECRET_KEY is auto-generated on first run)

# 5. Initialize the database
python database_setup.py
```

### Running the Server

```bash
# Development
python server.py

# Production (with Gunicorn)
gunicorn wsgi:app --bind 0.0.0.0:5000
```

The server starts at `http://localhost:5000/`

### Default Credentials

| Role | Login Page | Username/ID | Password/PIN |
|------|-----------|-------------|-------------|
| Admin | `/admin-login` | `admin` | `admin` |
| Teacher | `/` (main page) | Course code dropdown | Teacher PIN |
| Student | `/student` | University Roll No. | Student password |

> ⚠️ **Change default credentials immediately after first login!**

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# --- Security ---
SECRET_KEY=auto_generate_on_first_run    # Auto-generates on first launch

# --- Server ---
FLASK_ENV=development                     # development | production
HOST=0.0.0.0
PORT=5000

# --- Database ---
DATABASE_PATH=attendance.db

# --- Admin ---
ADMIN_DEFAULT_PASSWORD=admin              # Only used during database_setup.py

# --- Cloud Sync ---
CLOUD_SERVER_URL=https://your-app.onrender.com
SYNC_API_KEY=your-secret-sync-key
SYNC_INTERVAL_SECONDS=300                 # Auto-sync every 5 minutes (0=manual)

# --- Cloud Detection (auto-set by Render) ---
# IS_CLOUD_SERVER=true                    # Set on cloud, not on local
# RENDER=true                             # Auto-detected on Render.com
```

---

## ☁️ Deployment (Render Cloud)

### Quick Deploy to Render

1. Push code to GitHub
2. Create a new **Web Service** on [Render.com](https://render.com)
3. Connect your GitHub repo
4. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app` (or use the Procfile)
   - **Environment**: Python 3

5. Set environment variables on Render dashboard:

| Variable | Value |
|----------|-------|
| `SECRET_KEY` | (long random string) |
| `FLASK_ENV` | `production` |
| `SYNC_API_KEY` | (same key as local server) |
| `IS_CLOUD_SERVER` | `true` |

6. On your **local server's** `.env`, set:
```env
CLOUD_SERVER_URL=https://your-app.onrender.com
SYNC_API_KEY=same-key-as-cloud
```

### Files for Deployment

| File | Purpose |
|------|---------|
| `Procfile` | Tells Render how to start the app |
| `wsgi.py` | WSGI entry point for Gunicorn |
| `render.yaml` | Render infrastructure-as-code config |
| `requirements.txt` | Python dependencies |

---

## 🔄 Cloud Sync Engine

The sync engine (`sync_engine.py`) handles bidirectional data consistency:

### How It Works

```
LOCAL (USB)                              CLOUD (Render)
┌─────────────────┐                     ┌──────────────────────┐
│ Offline classes  │                     │ 1. Extract online    │
│ only in local DB │──── push ──────────▶│    records from DB   │
│                  │    (full binary)     │                      │
│ Master data:     │                     │ 2. Replace DB with   │
│ students,courses │                     │    local snapshot     │
│ teachers, etc.   │                     │                      │
└─────────────────┘                     │ 3. Re-insert online  │
                                        │    records (remap IDs)│
                                        │                      │
                                        │ Result: BOTH online  │
                                        │ + offline records ✅  │
                                        └──────────────────────┘
```

### Key Features

- **SQLite Backup API** for consistent snapshots (no corruption risk)
- **Smart merge** — online sessions are preserved through extract→replace→re-insert
- **ID remapping** — re-inserted sessions get new auto-increment IDs, attendance FK updated
- **Deduplication** — checks `(course_id, start_time, session_type)` before inserting
- **Auto-sync** every 300 seconds (configurable)
- **API key** authentication on both ends

### Sync API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/sync/receive` | POST | Cloud receives DB snapshot from local |
| `/api/sync/push` | POST | Local triggers manual push to cloud |
| `/api/sync/status` | GET | Check sync status (node type, DB size, cloud reachability) |

---

## 📡 API Reference

### Health & Sync

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/health` | — | Health check |
| GET | `/api/sync/status` | — | Sync engine status |
| POST | `/api/sync/push` | JWT | Trigger manual sync push |
| POST | `/api/sync/receive` | API Key | Receive DB snapshot |

### Admin APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/login` | Admin login (returns JWT) |
| GET/POST | `/api/admin/config` | Get/set batch name and system config |
| GET/POST | `/api/admin/semesters` | List/create semesters |
| PUT/DELETE | `/api/admin/semesters/:id` | Update/delete semester |
| GET/POST | `/api/admin/teachers` | List/create teachers |
| PUT/DELETE | `/api/admin/teachers/:id` | Update/delete teacher |
| GET/POST | `/api/admin/students` | List/create students |
| PUT/DELETE | `/api/admin/students/:id` | Update/delete student |
| GET/POST | `/api/admin/courses` | List/create courses |
| GET | `/api/admin/courses-view` | Courses with teacher/semester names |
| GET/PUT/DELETE | `/api/admin/courses/:id` | Get/update/delete course |
| GET/POST | `/api/admin/enrollments/:course_id` | View/save course enrollments |
| GET | `/api/admin/enrollment-roster/:semester_id` | Full enrollment roster |

### Admin Analytics APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/analytics/overview` | KPIs, course summary, at-risk count |
| GET | `/api/admin/analytics/course/:id` | Per-student attendance for a course |
| GET | `/api/admin/analytics/student/:id` | Cross-course attendance for a student |
| GET | `/api/admin/analytics/trends` | Daily, weekly, online/offline trends |

### Teacher APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/teacher/login` | Teacher login with PIN |
| GET | `/api/teacher/course-codes` | List of available course codes |
| POST | `/api/teacher/start-session` | Start offline attendance session |
| POST | `/api/teacher/start-online-session` | Start online session (cloud only) |
| POST | `/api/teacher/manual-override` | Mark/unmark individual student |
| POST | `/api/teacher/emergency-bulk-mark` | Mark all students present |
| POST | `/api/teacher/session/:id/end` | End active session |
| POST | `/api/teacher/session/:id/extend` | Extend session duration |
| GET | `/api/teacher/session/:id/status` | Get session status |
| GET | `/api/teacher/session/:id/online-status` | Online session real-time status |
| GET | `/api/teacher/report/:id` | Session attendance report |
| GET | `/api/teacher/report/export/:id` | Download Excel report |
| GET | `/api/teacher/analytics/:course_id` | Course analytics |
| GET | `/api/teacher/history/:course_id` | Session history for course |
| GET | `/api/teacher/session-detail/:id` | Detailed session view |
| POST | `/api/teacher/update-attendance` | Update attendance records |
| GET | `/api/teacher/validate-session/:course_id` | Check for active sessions |
| GET | `/api/teacher/device-status` | ESP32 device status |

### Student APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/student/login` | Student login |
| GET | `/api/student/dashboard` | Personal attendance dashboard |
| GET | `/api/student/semesters` | Available semesters |
| GET | `/api/student/course/:course_id` | Per-course attendance detail |
| GET | `/api/student/analytics` | Personal analytics |
| GET | `/api/student/critical-alerts` | Low attendance alerts |
| GET | `/api/student/leaderboard` | Attendance leaderboard |

### Online Attendance APIs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/online/:token` | Online attendance page for students |
| GET | `/api/online/session/:token/info` | Session info for online page |
| POST | `/api/online/mark-attendance` | Mark attendance via OTP |
| GET | `/api/online/session/:token/otp` | Get current OTP (teacher only) |

### Device APIs (ESP32)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/session-status` | Check if any session is active |
| POST | `/api/mark-attendance-by-roll-id` | Mark attendance by class roll ID |
| POST | `/api/bulk-mark-attendance` | Bulk mark from device queue |
| POST | `/api/device/heartbeat` | Device health heartbeat |

---

## 🌐 Online Class Attendance

Online attendance is available **only on the cloud server**. Here's the flow:

```
Teacher (Cloud)                    Student (Any Browser)
┌──────────────┐                  ┌──────────────────────┐
│ Start Online  │                  │ Open shared link     │
│ Session       │──── share URL ──▶│ /online/<token>      │
│               │                  │                      │
│ See OTP on    │                  │ Enter roll number    │
│ dashboard     │                  │ Enter OTP            │
│ (refreshes    │                  │ (30-sec rotation)    │
│  every 30s)   │                  │                      │
│               │                  │ ✅ Marked Present    │
│ Manual override│                 └──────────────────────┘
│ available     │
└──────────────┘
```

### Security Features
- **Token-based session URLs** — unique per session
- **Rotating OTP** — changes every 30 seconds, prevents screenshot sharing
- **One mark per student** — duplicate submissions are rejected
- **Manual override** — teacher can mark/unmark any student

---

## 📡 ESP32 Smart Scanner

Located in `FirmwareCodeOfEsp32/sketch_oct8a/`.

### Setup

1. Install [Arduino IDE](https://www.arduino.cc/en/software) or PlatformIO
2. Install required libraries:
   - `Adafruit Fingerprint Sensor Library`
   - `ArduinoJson`
   - `WiFi` (built-in for ESP32)
3. Configure Wi-Fi SSID/password and server IP in the firmware
4. Upload to ESP32

### How It Works

1. Teacher starts a session on the server
2. ESP32 detects active session via `/api/session-status`
3. Student places finger on scanner
4. ESP32 reads fingerprint → maps to class roll ID
5. POSTs to `/api/mark-attendance-by-roll-id`
6. If server is unreachable → queues locally
7. On reconnection → flushes queue via `/api/bulk-mark-attendance`
8. Periodic heartbeat to `/api/device/heartbeat`

---

## 📊 Admin Analytics Dashboard

The admin analytics section provides batch coordinators with deep insights:

### Overview Tab
- **8 KPI cards**: Total Students, Courses, Sessions, Overall Attendance %, At-Risk Students, Online Sessions, This Week Activity, Avg per Session
- **Course-wise summary table** with color-coded attendance percentages

### Course Analytics Tab
- Select any course → see **every student's attendance** with status badges (🟢 Safe, 🟡 Warning, 🔴 Critical)
- Per-student present count, total sessions, percentage
- Session trend chart (Chart.js line chart)

### Student Lookup Tab
- Search any student → see their attendance **across all courses**
- Recent absences list
- Overall attendance badge

### Trends Tab (Chart.js Visualizations)
- **Daily Attendance** — bar chart, last 30 days
- **Day-of-Week Pattern** — which days have highest attendance
- **Online vs Offline** — doughnut chart showing session type split
- **Course Comparison** — bar chart comparing sessions and attendance across courses

---

## 📁 Project Structure

```
A.R.I.S.E/
├── server.py                  # Main Flask application (all routes + logic)
├── config.py                  # Configuration classes + .env loader
├── database_setup.py          # Database schema creation script
├── sync_engine.py             # Local ↔ Cloud sync with smart merge
├── analytics.py               # Analytics computation module
├── wsgi.py                    # WSGI entry point for Gunicorn
├── backup_db.py               # Database backup utility
├── migrate_passwords.py       # Password migration script (plaintext → bcrypt)
├── attendance.db              # SQLite database (created at runtime)
│
├── templates/
│   ├── admin-login.html       # Admin login page
│   ├── admin.html             # Admin panel (5 tabs: Settings, Manage, View, Tools, Analytics)
│   ├── teacher.html           # Teacher dashboard
│   ├── student.html           # Student portal
│   └── online_attendance.html # Online attendance marking page
│
├── static/
│   ├── css/
│   │   ├── base.css           # Shared styles, CSS variables, dark mode
│   │   ├── admin.css          # Admin panel + analytics styles
│   │   ├── teacher.css        # Teacher dashboard styles
│   │   ├── student.css        # Student portal styles
│   │   ├── online.css         # Online attendance page styles
│   │   └── modal.css          # Custom modal dialog styles
│   │
│   ├── js/
│   │   ├── admin.js           # Admin panel logic (CRUD, tabs, enrollment)
│   │   ├── admin-analytics.js # Analytics dashboard (Chart.js, KPIs, tables)
│   │   ├── teacher.js         # Teacher dashboard logic
│   │   ├── student.js         # Student portal logic
│   │   ├── online.js          # Online attendance logic (OTP, marking)
│   │   └── modal.js           # Custom modal component
│   │
│   └── manifest.json          # PWA manifest
│
├── FirmwareCodeOfEsp32/       # ESP32 fingerprint scanner firmware
│   └── sketch_oct8a/
│
├── .env                       # Environment variables (not in git)
├── .env.example               # Environment template
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Python dependencies (pinned versions)
├── Procfile                   # Render/Heroku start command
├── render.yaml                # Render infrastructure config
├── DEPLOYMENT.md              # Deployment guide
└── README.md                  # This file
```

---

## 🔒 Security

| Feature | Implementation |
|---------|---------------|
| **Password hashing** | bcrypt (adaptive cost factor) |
| **Authentication** | JWT tokens with expiration |
| **Rate limiting** | Flask-Limiter (5/min login, 100/min API) |
| **CORS** | Flask-CORS with configurable origins |
| **API key sync** | Shared secret between local and cloud for sync |
| **Input validation** | Server-side validation on all endpoints |
| **SQL injection** | Parameterized queries throughout |
| **Session tokens** | Cryptographically secure random tokens |
| **OTP rotation** | 30-second TOTP-style codes for online attendance |
| **Auto-expiry** | Sessions auto-expire after configured duration |

---

## 🛠 Troubleshooting

| Problem | Solution |
|---------|----------|
| "Server not reachable" | Ensure `server.py` is running, port 5000 is open |
| "Invalid credentials" | Default admin is `admin/admin` after `database_setup.py` |
| "Not enrolled" responses | Verify enrollments in Admin → Manage → Enrollments |
| Sync fails | Check `CLOUD_SERVER_URL` and `SYNC_API_KEY` match on both servers |
| Online attendance unavailable | Only works on cloud server (`IS_CLOUD_SERVER=true`) |
| ESP32 can't connect | Verify Wi-Fi config and server IP in firmware |
| Charts not loading | Clear browser cache or hard refresh (Ctrl+Shift+R) |
| Database locked | Stop all server processes, then restart |

### Logs

Server logs are written to `arise_server.log` and stdout. Check logs for detailed error messages:

```bash
# View last 50 log lines
tail -50 arise_server.log

# Windows
Get-Content arise_server.log -Tail 50
```

---

## 📄 License

This project is developed for educational purposes.

---

<p align="center">
  <b>Built with ❤️ for classrooms that deserve better attendance systems.</b>
</p>
