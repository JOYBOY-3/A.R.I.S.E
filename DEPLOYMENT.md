# A.R.I.S.E. — Production Deployment Guide

## Quick Start (5 Minutes)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings (SECRET_KEY auto-generates on first run)
```

### 3. Initialize Database
```bash
python database_setup.py
```

### 4. Migrate Existing Passwords (if upgrading)
```bash
python migrate_passwords.py
```

### 5. Start Server
```bash
# Development
python server.py

# Production (Windows)
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 wsgi:app

# Production (Linux)
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

---

## Security Features

| Feature | Details |
|---------|---------|
| **Password Hashing** | bcrypt (with SHA-256 fallback for legacy) |
| **JWT Authentication** | HS256 with configurable expiry |
| **Rate Limiting** | 5 login attempts/min, 100 API calls/min |
| **CORS** | Configurable allowed origins |
| **Security Headers** | CSP, X-Frame-Options, HSTS, XSS-Protection |
| **Input Sanitization** | HTML escaping on all user inputs |
| **Secret Management** | Environment-based via `.env` |

---

## File Structure
```
A.R.I.S.E/
├── server.py           # Main Flask application
├── config.py           # Configuration management
├── database_setup.py   # Database schema creation
├── migrate_passwords.py # SHA-256 → bcrypt migration
├── backup_db.py        # Database backup utility
├── wsgi.py             # Production WSGI entry point
├── analytics.py        # Attendance analytics engine
├── requirements.txt    # Python dependencies (pinned)
├── .env                # Environment variables (DO NOT COMMIT)
├── .env.example        # Environment template
├── .gitignore          # Git exclusion rules
├── templates/          # HTML templates
├── static/             # CSS, JS, assets
└── backups/            # Database backups (auto-created)
```

---

## Database Backup
```bash
# Create backup
python backup_db.py

# List all backups
python backup_db.py --list
```

Backups are stored in `backups/` with timestamps. Last 10 backups are kept automatically.

---

## Health Check
```bash
curl http://localhost:5000/api/health
# {"status":"healthy","version":"2.0.0-production","environment":"development","database":"connected"}
```

---

## Portable USB Deployment
A.R.I.S.E. is designed to run portably from a USB drive:
1. Copy the entire `A.R.I.S.E/` folder to a USB drive
2. Ensure Python 3.10+ is available on target machines
3. Run `python server.py` from the USB drive
4. Access at `http://localhost:5000`

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | JWT signing key |
| `FLASK_ENV` | `development` | `development` or `production` |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `5000` | Server port |
| `DATABASE_PATH` | `attendance.db` | SQLite database file path |
| `ADMIN_DEFAULT_PASSWORD` | `admin` | Default admin password |

---

## Troubleshooting

**Server won't start:**
- Check `arise_server.log` for errors
- Verify all dependencies: `pip install -r requirements.txt`
- Ensure port 5000 is not in use

**Login fails after upgrade:**
- Run `python migrate_passwords.py` to update password hashes
- SHA-256 passwords still work via fallback mechanism

**Rate limit exceeded:**
- Wait 1 minute between login attempts
- API calls are limited to 100/minute per IP
