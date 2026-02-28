# =================================================================
#   A.R.I.S.E. Server — Production Build
# =================================================================



from flask import Flask, jsonify, request, render_template
import sqlite3
import datetime
import jwt
import hashlib
import bcrypt
import html as html_module
from functools import wraps

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import io
from flask import send_file

import logging
from logging.handlers import RotatingFileHandler
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import analytics
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS


import io
import sys
import os
# Fix console encoding for Windows to support emoji/unicode
if sys.platform == "win32":
    # For Windows console - use UTF-8
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    # Reconfigure stderr/stdout to use UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')


class UTF8StreamHandler(logging.StreamHandler):
    """Custom handler that forces UTF-8 encoding for emoji support"""
    def __init__(self):
        super().__init__()
        
    def emit(self, record):
        try:
            msg = self.format(record)
            # Force UTF-8 encoding
            if sys.platform == "win32":
                stream = sys.stderr
                stream.write(msg.encode('utf-8', errors='replace').decode('utf-8'))
            else:
                self.stream.write(msg)
            self.stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)




# Load production configuration
from config import (
    Config,
    MINIMUM_ATTENDANCE_PERCENTAGE,
    ATTENDANCE_WARNING_THRESHOLD,
    ENABLE_ATTENDANCE_ANALYTICS,
    ANALYTICS_LAST_DAYS,
    ANALYTICS_TREND_DAYS
)


# ------------------- Optional For Logger ----------------------
from werkzeug.serving import WSGIRequestHandler
import time

class TimedRequestHandler(WSGIRequestHandler):
    """Custom request handler that only logs slow requests"""
    def log_request(self, code='-', size='-'):
        # Only log requests that took > 1 second or had errors
        if hasattr(self, '_start_time'):
            duration = time.time() - self._start_time
            if duration > 1.0 or int(code) >= 400:
                self.log('info', f'"{self.requestline}" {code} {size} ({duration:.2f}s)')


# ----------------------------------------------------------
# 
# 
#     

# --- Configure logging with rotation ---
log_file_handler = RotatingFileHandler(
    'arise_server.log',
    maxBytes=10 * 1024 * 1024,  # 10 MB per file
    backupCount=5,              # Keep 5 backup files
    encoding='utf-8'
)
log_file_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file_handler.setFormatter(log_formatter)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        log_file_handler,
        UTF8StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Reduce werkzeug (Flask web server) logging - only show warnings and errors
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Reduce APScheduler logging - only show warnings and errors
logging.getLogger('apscheduler').setLevel(logging.WARNING)
logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)



# --- App Initialization ---
app = Flask(__name__)
# Load SECRET_KEY from environment-based config (no more hardcoded secrets!)
app.config['SECRET_KEY'] = Config.SECRET_KEY
app.config['DEBUG'] = Config.DEBUG

# --- CORS: Allow configurable cross-origin requests ---
CORS(app, resources={r"/api/*": {"origins": "*"}})

# --- Rate Limiting: Protect against brute-force attacks ---
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[Config.RATE_LIMIT_API],
    storage_uri="memory://"
)

# --- Security Headers Middleware ---
@app.after_request
def add_security_headers(response):
    """Add security headers to every response for production safety."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Only add HSTS in production
    if not Config.DEBUG:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# --- Input Sanitization Helper ---
def sanitize_input(value):
    """Sanitize user input to prevent XSS attacks."""
    if value is None:
        return None
    if isinstance(value, str):
        return html_module.escape(value.strip())
    return value

# --- Password Hashing Helpers (bcrypt) ---
def hash_password(password):
    """Hash a password using bcrypt (production-grade)."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """
    Verify a password against a hash.
    Supports both bcrypt (new) and SHA-256 (legacy) for migration period.
    """
    try:
        # Try bcrypt first (new format starts with $2b$)
        if hashed.startswith('$2b$') or hashed.startswith('$2a$'):
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        else:
            # Legacy SHA-256 fallback for existing passwords
            sha256_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            return sha256_hash == hashed
    except Exception:
        return False

# --- Request/Response Logging Middleware ---
@app.before_request
def log_request_info():
    """Log every incoming request with method, path, and client IP."""
    # Skip logging for high-frequency polling endpoints to reduce noise
    skip_paths = ['/api/teacher/device-status', '/api/device/heartbeat', '/api/device/session-status']
    if request.path in skip_paths:
        return
    request._start_time = time.time()
    logger.info(f"[REQUEST] {request.method} {request.path} - Client: {request.remote_addr}")

@app.after_request
def log_response_info(response):
    """Log response status and time taken for every request."""
    skip_paths = ['/api/teacher/device-status', '/api/device/heartbeat', '/api/device/session-status']
    if request.path in skip_paths:
        return response
    duration = 0
    if hasattr(request, '_start_time'):
        duration = (time.time() - request._start_time) * 1000  # ms
    # Only log non-200 responses or slow requests (>500ms) to reduce noise
    if response.status_code != 200 or duration > 500:
        logger.info(f"[RESPONSE] {request.method} {request.path} - Status: {response.status_code} - {duration:.0f}ms")
    return response

# --- Database & Token Helper Functions ---

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    # check_same_thread=False is needed because Flask can handle requests in different threads.
    db_path = Config.DATABASE_PATH
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # This makes the database return rows that can be accessed by column name.
    conn.row_factory = sqlite3.Row
    # Enable foreign key support
    conn.execute("PRAGMA foreign_keys = ON")
    return conn




# This is a "decorator" that we can add to our routes to protect them.
# It checks for a valid JSON Web Token (JWT) in the request's Authorization header.
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            # The token is expected to be in the format "Bearer <token>"
            token = request.headers['Authorization'].split(" ")[1]
        
        if not token:
            return jsonify({'message': 'Authorization Token is missing!'}), 401
        
        try:
            # Decode the token using our secret key to verify its authenticity
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            # The decoded data (e.g., admin_id or student_id) is passed to the route
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        
        return f(data, *args, **kwargs)
    return decorated


# --- Input Validation Helper ---
def validate_required_fields(data, required_fields):
    """
    Validates that request data contains all required fields and they're not empty.
    
    Args:
        data: The request.get_json() dictionary
        required_fields: List of field names that must exist
        
    Returns:
        (is_valid, error_message) tuple
        - is_valid: True if all validation passes, False otherwise
        - error_message: None if valid, descriptive error string if invalid
    """
    if not data:
        return False, "No data provided in request body"
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: '{field}'"
        
        # Convert to string and check if empty after stripping whitespace
        if not str(data[field]).strip():
            return False, f"Field '{field}' cannot be empty"
    
    return True, None





# =================================================================
#   HTML Page Serving Routes
# =================================================================
# These functions simply return the HTML files for our interfaces.

@app.route('/')
def teacher_page_redirect():
    # The main page will be the Teacher Login
    return render_template('teacher.html') # Points to the prototype for now

@app.route('/admin-login')
def admin_login_page():
    return render_template('admin-login.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html') # The JS on this page will handle token security

@app.route('/student')
def student_page():
    return render_template('student.html') # Points to the prototype for now

# --- Health Check Endpoint (for monitoring and cloud deployment) ---
@app.route('/api/health', methods=['GET'])
@limiter.exempt
def health_check():
    """
    Health check endpoint for monitoring and cloud deployment.
    Returns server status, database connectivity, and version info.
    """
    status = {
        "status": "healthy",
        "version": "2.0.0-production",
        "environment": "production" if not Config.DEBUG else "development",
        "database": "unknown"
    }
    
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        status["database"] = "connected"
    except Exception as e:
        status["status"] = "degraded"
        status["database"] = f"error: {str(e)}"
        logger.error(f"Health check - Database error: {e}")
    
    http_code = 200 if status["status"] == "healthy" else 503
    return jsonify(status), http_code



# =================================================================
#   SYNC API — Cloud/Local Database Synchronization
# =================================================================

from sync_engine import SyncEngine

# Initialize sync engine
sync = SyncEngine(
    db_path=Config.DATABASE_PATH,
    cloud_url=Config.CLOUD_SERVER_URL,
    api_key=Config.SYNC_API_KEY,
    is_cloud=Config.IS_CLOUD_SERVER
)

def require_sync_api_key(f):
    """Decorator to require sync API key authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Sync-API-Key', '')
        if api_key != Config.SYNC_API_KEY:
            logger.warning(f"[SYNC] Unauthorized sync attempt from {request.remote_addr}")
            return jsonify({"status": "error", "message": "Invalid sync API key"}), 403
        return f(*args, **kwargs)
    return decorated


@app.route('/api/sync/receive', methods=['POST'])
@limiter.exempt
@require_sync_api_key
def sync_receive():
    """
    Receive a full database snapshot from the local server.
    Protected by API key authentication.
    """
    
    try:
        data = request.get_json()
        if not data or 'db_data' not in data:
            return jsonify({"status": "error", "message": "No database data received"}), 400
        
        import base64
        db_binary = base64.b64decode(data['db_data'])
        
        logger.info(f"[SYNC] Receiving database snapshot: {len(db_binary)} bytes from {request.remote_addr}")
        
        success = sync.import_database_binary(db_binary)
        
        if success:
            logger.info(f"[SYNC] Database snapshot imported successfully")
            return jsonify({
                "status": "success",
                "message": f"Database imported ({len(db_binary)} bytes)",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            })
        else:
            return jsonify({"status": "error", "message": "Failed to import database"}), 500
            
    except Exception as e:
        logger.error(f"[SYNC] Receive failed: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/sync/push', methods=['POST'])
@token_required
def sync_push(user_data):
    """
    Trigger a sync push from local to cloud.
    Called by admin from the LOCAL server.
    """
    if Config.IS_CLOUD_SERVER:
        return jsonify({"status": "error", "message": "Cannot push from cloud server"}), 400
    
    logger.info(f"[SYNC] Manual sync push triggered by admin")
    result = sync.push_to_cloud()
    
    status_code = 200 if result.get('status') == 'success' else 500
    if result.get('status') == 'offline':
        status_code = 503
    
    return jsonify(result), status_code


@app.route('/api/sync/status', methods=['GET'])
@limiter.exempt
def sync_status():
    """Get current sync status information."""
    return jsonify(sync.get_sync_status())


# =================================================================
#   ADMIN API ENDPOINTS (Part 1)
# =================================================================

@app.route('/api/admin/login', methods=['POST'])
@limiter.limit(Config.RATE_LIMIT_LOGIN)
def admin_login():
    """Handles the administrator's login request."""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        logger.warning(f"Admin login failed - Missing username or password")
        return jsonify({"message": "Username and password are required"}), 400

    username = sanitize_input(data['username'])
    logger.info(f"Admin login attempt - Username: {username}")
    
    conn = get_db_connection()
    admin = conn.execute("SELECT id, password FROM admins WHERE username = ?", 
                           (username,)).fetchone()
    conn.close()
    
    if admin and verify_password(data['password'], admin['password']):
        # If login is successful, create a token that expires in 8 hours
        token = jwt.encode({
            'admin_id': admin['id'], 
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        logger.info(f"Admin login successful - Username: {username}, AdminID: {admin['id']}")
        return jsonify({'token': token})
    
    logger.warning(f"Admin login failed - Invalid credentials for username: {username}")
    return jsonify({"message": "Invalid credentials"}), 401

# --- System Configuration API ---
@app.route('/api/admin/config', methods=['GET', 'POST'])
@token_required
def manage_config(user_data):
    conn = get_db_connection()
    if request.method == 'GET':
        row = conn.execute("SELECT value FROM system_settings WHERE key = 'batch_name'").fetchone()
        batch_name = row['value'] if row else "My Classroom Pod"
        conn.close()
        return jsonify({"batch_name": batch_name})
    
    if request.method == 'POST':
        data = request.get_json()
        new_name = data.get('batch_name', '').strip()
        if not new_name:
            return jsonify({"error": "Batch name cannot be empty"}), 400
        
        conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('batch_name', ?)", (new_name,))
        conn.commit()
        conn.close()
        logger.info(f"System config updated - batch_name: '{new_name}'")
        return jsonify({"message": "System configuration updated."})

# --- Semester Management API (Full CRUD) ---
@app.route('/api/admin/semesters', methods=['GET', 'POST'])
@token_required
def manage_semesters(user_data):
    conn = get_db_connection()
    if request.method == 'GET':
        semesters_cursor = conn.execute("SELECT * FROM semesters ORDER BY id DESC").fetchall()
        semesters = [dict(row) for row in semesters_cursor]
        conn.close()
        return jsonify(semesters)
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Validate input
        valid, error = validate_required_fields(data, ['semester_name'])
        if not valid:
            logger.warning(f"Semester creation failed - {error}")
            return jsonify({"error": error}), 400
        
        try:
            conn.execute("INSERT INTO semesters (semester_name) VALUES (?)",
                         (data['semester_name'],))
            conn.commit()
            logger.info(f"Semester created - Name: {data['semester_name']}")
        except sqlite3.IntegrityError as e:
            logger.error(f"Semester creation failed - Duplicate name: {data['semester_name']}")
            conn.close()
            return jsonify({"error": "Semester name already exists"}), 409
        
        conn.close()
        return jsonify({"status": "success", "message": "Semester added."}), 201

@app.route('/api/admin/semesters/<int:id>', methods=['PUT', 'DELETE'])
@token_required
def manage_single_semester(user_data, id):
    conn = get_db_connection()
    if request.method == 'PUT':
        data = request.get_json()
        conn.execute("UPDATE semesters SET semester_name = ? WHERE id = ?", (data['semester_name'], id))
        conn.commit()
        logger.info(f"Semester updated - ID: {id}, Name: {data['semester_name']}")
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM semesters WHERE id = ?", (id,))
        conn.commit()
        logger.info(f"Semester deleted - ID: {id}")
    conn.close()
    return jsonify({"message": "Operation successful."})

# --- Teacher Management API (Full CRUD) ---
@app.route('/api/admin/teachers', methods=['GET', 'POST'])
@token_required
def manage_teachers(user_data):
    conn = get_db_connection()
    if request.method == 'GET':
        teachers_cursor = conn.execute("SELECT * FROM teachers ORDER BY id DESC").fetchall()
        teachers = [dict(row) for row in teachers_cursor]
        conn.close()
        return jsonify(teachers)
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Validate input
        valid, error = validate_required_fields(data, ['teacher_name', 'pin'])
        if not valid:
            logger.warning(f"Teacher creation failed - {error}")
            return jsonify({"error": error}), 400
        
        conn.execute("INSERT INTO teachers (teacher_name, pin) VALUES (?, ?)",
                     (sanitize_input(data['teacher_name']), hash_password(data['pin'])))
        conn.commit()
        conn.close()
        logger.info(f"Teacher created - Name: {data['teacher_name']}")
        return jsonify({"status": "success", "message": "Teacher added."}), 201

@app.route('/api/admin/teachers/<int:id>', methods=['PUT', 'DELETE'])
@token_required
def manage_single_teacher(user_data, id):
    conn = get_db_connection()
    if request.method == 'PUT':
        data = request.get_json()
        if 'pin' in data and data['pin']: # Only update PIN if provided
             conn.execute("UPDATE teachers SET teacher_name = ?, pin = ? WHERE id = ?", (sanitize_input(data['teacher_name']), hash_password(data['pin']), id))
        else:
             conn.execute("UPDATE teachers SET teacher_name = ? WHERE id = ?", (sanitize_input(data['teacher_name']), id))
        conn.commit()
        logger.info(f"Teacher updated - ID: {id}, Name: {data['teacher_name']}")
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM teachers WHERE id = ?", (id,))
        conn.commit()
        logger.info(f"Teacher deleted - ID: {id}")
    conn.close()
    return jsonify({"message": "Operation successful."})

# --- Student Management API (Full CRUD) ---
@app.route('/api/admin/students', methods=['GET', 'POST'])
@token_required
def manage_students(user_data):
    conn = get_db_connection()
    if request.method == 'GET':
        students_cursor = conn.execute("SELECT * FROM students ORDER BY student_name").fetchall()
        students = [dict(row) for row in students_cursor]
        conn.close()
        return jsonify(students)
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Validate input
        valid, error = validate_required_fields(data, [
            'student_name',
            'university_roll_no',
            'enrollment_no',
            'email1',
            'password'
        ])
        if not valid:
            logger.warning(f"Student creation failed - {error}")
            return jsonify({"error": error}), 400
        
        hashed_password = hash_password(data['password'])
        
        try:
            conn.execute("""INSERT INTO students 
                (student_name, university_roll_no, enrollment_no, email1, email2, password) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (sanitize_input(data['student_name']), sanitize_input(data['university_roll_no']), 
                 sanitize_input(data['enrollment_no']), sanitize_input(data['email1']), 
                 sanitize_input(data.get('email2', '')), hashed_password))
            conn.commit()
            logger.info(f"Student created - Roll: {data['university_roll_no']}")
        except sqlite3.IntegrityError:
            logger.error(f"Student creation failed - Duplicate roll/enrollment number")
            conn.close()
            return jsonify({"error": "Student with that University Roll No or Enrollment No already exists"}), 409
        
        conn.close()
        return jsonify({"status": "success", "message": "Student added."}), 201

@app.route('/api/admin/students/<int:id>', methods=['PUT', 'DELETE'])
@token_required
def manage_single_student(user_data, id):
    conn = get_db_connection()
    if request.method == 'PUT':
        data = request.get_json()
        # Check if a new password was provided
        if 'password' in data and data['password']:
            hashed_password = hash_password(data['password'])
            conn.execute("""UPDATE students SET student_name = ?, university_roll_no = ?, 
                            enrollment_no = ?, email1 = ?, email2 = ?, password = ? WHERE id = ?""",
                         (data['student_name'], data['university_roll_no'], data['enrollment_no'], data['email1'], data['email2'], hashed_password, id))
        else: # Update without changing the password
            conn.execute("""UPDATE students SET student_name = ?, university_roll_no = ?, 
                            enrollment_no = ?, email1 = ?, email2 = ? WHERE id = ?""",
                         (data['student_name'], data['university_roll_no'], data['enrollment_no'], data['email1'], data['email2'], id))
        conn.commit()
        logger.info(f"Student updated - ID: {id}, Roll: {data['university_roll_no']}")
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM students WHERE id = ?", (id,))
        conn.commit()
        logger.info(f"Student deleted - ID: {id}")
    conn.close()
    return jsonify({"message": "Operation successful."})

# END OF PART 1




# START OF PART 2

# =================================================================
#   ADMIN API ENDPOINTS (Part 2 - Advanced)
# =================================================================

# --- Course Management API (Full CRUD) ---
@app.route('/api/admin/courses', methods=['GET', 'POST'])
@token_required
def manage_courses(user_data):
    conn = get_db_connection()
    if request.method == 'GET':
        courses_cursor = conn.execute("SELECT * FROM courses ORDER BY course_name").fetchall()
        courses = [dict(row) for row in courses_cursor]
        conn.close()
        return jsonify(courses)
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Validate input
        valid, error = validate_required_fields(data, [
            'course_name',
            'course_code',
            'default_duration_minutes',
            'semester_id',
            'teacher_id'
        ])
        if not valid:
            logger.warning(f"Course creation failed - {error}")
            return jsonify({"error": error}), 400
        
        try:
            conn.execute("""INSERT INTO courses 
                (course_name, course_code, default_duration_minutes, semester_id, teacher_id)
                VALUES (?, ?, ?, ?, ?)""",
                (data['course_name'], data['course_code'], 
                 data['default_duration_minutes'],
                 data['semester_id'], data['teacher_id']))
            conn.commit()
            logger.info(f"Course created - Name: {data['course_name']}, CourseCode: {data['course_code']}")
        except sqlite3.IntegrityError:
            logger.error(f"Course creation failed - Duplicate course_code: {data['course_code']}")
            conn.close()
            return jsonify({"error": "CourseCode already exists"}), 409
        
        conn.close()
        return jsonify({"status": "success", "message": "Course added."}), 201

# This is a special "view" endpoint that joins tables to get human-readable names
# for the main display table in the UI.
@app.route('/api/admin/courses-view', methods=['GET'])
@token_required
def get_courses_view(user_data):
    conn = get_db_connection()
    query = """
        SELECT c.id, c.course_name, c.course_code, s.semester_name, t.teacher_name 
        FROM courses c
        LEFT JOIN semesters s ON c.semester_id = s.id
        LEFT JOIN teachers t ON c.teacher_id = t.id
        ORDER BY c.course_name
    """
    courses_cursor = conn.execute(query).fetchall()
    courses = [dict(row) for row in courses_cursor]
    conn.close()
    return jsonify(courses)

@app.route('/api/admin/courses/<int:id>', methods=['GET', 'PUT', 'DELETE'])
@token_required
def manage_single_course(user_data, id):
    conn = get_db_connection()
    if request.method == 'GET':
        course = conn.execute("SELECT * FROM courses WHERE id = ?", (id,)).fetchone()
        conn.close()
        if course is None:
            return jsonify({"message": "Course not found"}), 404
        return jsonify(dict(course))

    if request.method == 'PUT':
        data = request.get_json()
        conn.execute("""UPDATE courses SET course_name = ?, course_code = ?, default_duration_minutes = ?, 
                        semester_id = ?, teacher_id = ? WHERE id = ?""",
                     (data['course_name'], data['course_code'], data['default_duration_minutes'], data['semester_id'], data['teacher_id'], id))
        conn.commit()
        logger.info(f"Course updated - ID: {id}, Code: {data['course_code']}")
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM courses WHERE id = ?", (id,))
        conn.commit()
        logger.info(f"Course deleted - ID: {id}")
    conn.close()
    return jsonify({"message": "Operation successful."})

# --- Course Enrollment API ---
@app.route('/api/admin/enrollments/<int:course_id>', methods=['GET', 'POST'])
@token_required
def manage_enrollments(user_data, course_id):
    conn = get_db_connection()
    if request.method == 'GET':
        enrolled_cursor = conn.execute("""
            SELECT s.id as student_id, s.student_name, s.university_roll_no, e.class_roll_id
            FROM students s JOIN enrollments e ON s.id = e.student_id
            WHERE e.course_id = ? """, (course_id,)).fetchall()
        enrolled = [dict(row) for row in enrolled_cursor]
        
        available_cursor = conn.execute("""
            SELECT id, student_name, university_roll_no FROM students
            WHERE id NOT IN (SELECT student_id FROM enrollments WHERE course_id = ?)
        """, (course_id,)).fetchall()
        available = [dict(row) for row in available_cursor]
        
        conn.close()
        return jsonify({"enrolled": enrolled, "available": available})

    if request.method == 'POST':
        enrollment_data = request.get_json()
        conn.execute('BEGIN TRANSACTION')
        try:
            conn.execute("DELETE FROM enrollments WHERE course_id = ?", (course_id,))
            for student in enrollment_data:
                conn.execute("INSERT INTO enrollments (student_id, course_id, class_roll_id) VALUES (?, ?, ?)",
                             (student['student_id'], course_id, student['class_roll_id']))
            conn.commit()
            logger.info(f"Enrollments updated - CourseID: {course_id}, Students enrolled: {len(enrollment_data)}")
        except Exception as e:
            conn.rollback()
            logger.error(f"Enrollment update failed - CourseID: {course_id}, Error: {e}")
            conn.close()
            return jsonify({"status": "error", "message": f"Database error: {e}"}), 500
        conn.close()
        return jsonify({"status": "success", "message": "Enrollments updated successfully."})

# --- Enrollment Roster API (The Brilliant Feature) ---
@app.route('/api/admin/enrollment-roster/<int:semester_id>', methods=['GET'])
@token_required
def get_enrollment_roster(user_data, semester_id):
    conn = get_db_connection()
    # This is a complex query that aggregates data for the roster view.
    # It finds all students enrolled in any course within the selected semester.
    # GROUP_CONCAT is a powerful SQLite function that joins multiple course codes into a single string.
    query = """
        SELECT
            s.student_name,
            s.university_roll_no,
            MIN(e.class_roll_id) as primary_class_roll_id,
            GROUP_CONCAT(c.course_code) as enrolled_courses
        FROM students s
        JOIN enrollments e ON s.id = e.student_id
        JOIN courses c ON e.course_id = c.id
        WHERE c.semester_id = ?
        GROUP BY s.id, s.student_name, s.university_roll_no
        ORDER BY primary_class_roll_id
    """
    roster_cursor = conn.execute(query, (semester_id,)).fetchall()
    roster = [dict(row) for row in roster_cursor]
    conn.close()
    return jsonify(roster)


# =================================================================
#   ADMIN ANALYTICS API ENDPOINTS
# =================================================================

@app.route('/api/admin/analytics/overview', methods=['GET'])
@token_required
def admin_analytics_overview(user_data):
    """Batch-wide analytics overview with KPIs."""
    conn = get_db_connection()
    
    total_students = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    total_courses = conn.execute("SELECT COUNT(*) as c FROM courses").fetchone()['c']
    total_sessions = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()['c']
    total_attendance = conn.execute("SELECT COUNT(*) as c FROM attendance_records").fetchone()['c']
    
    # Online vs offline sessions
    online_sessions = conn.execute(
        "SELECT COUNT(*) as c FROM sessions WHERE session_type = 'online'").fetchone()['c']
    offline_sessions = total_sessions - online_sessions
    
    # Sessions this week and month
    sessions_this_week = conn.execute("""
        SELECT COUNT(*) as c FROM sessions 
        WHERE start_time >= date('now', '-7 days')
    """).fetchone()['c']
    
    sessions_this_month = conn.execute("""
        SELECT COUNT(*) as c FROM sessions 
        WHERE start_time >= date('now', 'start of month')
    """).fetchone()['c']
    
    # Average attendance per session
    avg_attendance = conn.execute("""
        SELECT AVG(cnt) as avg_count FROM (
            SELECT session_id, COUNT(*) as cnt FROM attendance_records GROUP BY session_id
        )
    """).fetchone()['avg_count'] or 0
    
    # Overall attendance rate: total_marks / (total_sessions * avg_enrolled_per_course)
    total_possible = conn.execute("""
        SELECT SUM(enrolled) as total FROM (
            SELECT s.id, 
                   (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = s.course_id) as enrolled
            FROM sessions s
        )
    """).fetchone()['total'] or 1
    overall_rate = round((total_attendance / total_possible) * 100, 1) if total_possible > 0 else 0
    
    # At-risk student count (below 75% in any course)
    at_risk_query = conn.execute("""
        SELECT COUNT(DISTINCT e.student_id) as c
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE (
            SELECT COUNT(*) FROM attendance_records ar 
            JOIN sessions s ON ar.session_id = s.id 
            WHERE ar.student_id = e.student_id AND s.course_id = e.course_id
        ) < 0.75 * (
            SELECT COUNT(*) FROM sessions s WHERE s.course_id = e.course_id
        )
        AND (SELECT COUNT(*) FROM sessions s WHERE s.course_id = e.course_id) > 0
    """).fetchone()['c']
    
    # Course-wise summary
    course_summary = conn.execute("""
        SELECT c.id, c.course_name, c.course_code,
               t.teacher_name,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) as enrolled_count,
               (SELECT COUNT(*) FROM sessions s WHERE s.course_id = c.id) as session_count,
               (SELECT COUNT(*) FROM attendance_records ar 
                JOIN sessions s ON ar.session_id = s.id 
                WHERE s.course_id = c.id) as total_marks
        FROM courses c
        LEFT JOIN teachers t ON c.teacher_id = t.id
        ORDER BY c.course_name
    """).fetchall()
    
    course_data = []
    for row in course_summary:
        r = dict(row)
        possible = r['enrolled_count'] * r['session_count']
        r['attendance_rate'] = round((r['total_marks'] / possible) * 100, 1) if possible > 0 else 0
        course_data.append(r)
    
    conn.close()
    
    return jsonify({
        "total_students": total_students,
        "total_courses": total_courses,
        "total_sessions": total_sessions,
        "total_attendance_marks": total_attendance,
        "online_sessions": online_sessions,
        "offline_sessions": offline_sessions,
        "sessions_this_week": sessions_this_week,
        "sessions_this_month": sessions_this_month,
        "avg_attendance_per_session": round(avg_attendance, 1),
        "overall_attendance_rate": overall_rate,
        "at_risk_count": at_risk_query,
        "course_summary": course_data
    })


@app.route('/api/admin/analytics/course/<int:course_id>', methods=['GET'])
@token_required
def admin_analytics_course(user_data, course_id):
    """Deep analytics for a specific course — per-student breakdown."""
    conn = get_db_connection()
    
    course = conn.execute("""
        SELECT c.*, t.teacher_name, sem.semester_name
        FROM courses c
        LEFT JOIN teachers t ON c.teacher_id = t.id
        LEFT JOIN semesters sem ON c.semester_id = sem.id
        WHERE c.id = ?
    """, (course_id,)).fetchone()
    
    if not course:
        conn.close()
        return jsonify({"error": "Course not found"}), 404
    
    total_sessions = conn.execute(
        "SELECT COUNT(*) as c FROM sessions WHERE course_id = ?", (course_id,)).fetchone()['c']
    
    # Per-student attendance
    students = conn.execute("""
        SELECT s.id as student_id, s.student_name, s.university_roll_no, 
               e.class_roll_id,
               (SELECT COUNT(*) FROM attendance_records ar 
                JOIN sessions ses ON ar.session_id = ses.id 
                WHERE ar.student_id = s.id AND ses.course_id = ?) as present_count
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        WHERE e.course_id = ?
        ORDER BY e.class_roll_id
    """, (course_id, course_id)).fetchall()
    
    student_data = []
    at_risk = 0
    for row in students:
        r = dict(row)
        r['total_sessions'] = total_sessions
        r['percentage'] = round((r['present_count'] / total_sessions) * 100, 1) if total_sessions > 0 else 0
        if r['percentage'] >= 75:
            r['status'] = 'safe'
        elif r['percentage'] >= 60:
            r['status'] = 'warning'
            at_risk += 1
        else:
            r['status'] = 'critical'
            at_risk += 1
        student_data.append(r)
    
    # Session-wise attendance trend
    trend = conn.execute("""
        SELECT s.id, s.start_time, s.topic, s.session_type,
               (SELECT COUNT(*) FROM attendance_records ar WHERE ar.session_id = s.id) as present_count,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = s.course_id) as total_students
        FROM sessions s
        WHERE s.course_id = ?
        ORDER BY s.start_time
    """, (course_id,)).fetchall()
    
    conn.close()
    
    return jsonify({
        "course": {
            "id": course['id'],
            "course_name": course['course_name'],
            "course_code": course['course_code'],
            "teacher_name": course['teacher_name'],
            "semester_name": course['semester_name']
        },
        "total_sessions": total_sessions,
        "enrolled_count": len(student_data),
        "at_risk_count": at_risk,
        "students": student_data,
        "trend": [dict(r) for r in trend]
    })


@app.route('/api/admin/analytics/student/<int:student_id>', methods=['GET'])
@token_required
def admin_analytics_student(user_data, student_id):
    """Individual student analytics across all courses."""
    conn = get_db_connection()
    
    student = conn.execute(
        "SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    
    if not student:
        conn.close()
        return jsonify({"error": "Student not found"}), 404
    
    # Per-course attendance
    courses = conn.execute("""
        SELECT c.id as course_id, c.course_name, c.course_code, e.class_roll_id,
               (SELECT COUNT(*) FROM sessions s WHERE s.course_id = c.id) as total_sessions,
               (SELECT COUNT(*) FROM attendance_records ar 
                JOIN sessions s ON ar.session_id = s.id 
                WHERE ar.student_id = ? AND s.course_id = c.id) as present_count
        FROM enrollments e
        JOIN courses c ON e.course_id = c.id
        WHERE e.student_id = ?
        ORDER BY c.course_name
    """, (student_id, student_id)).fetchall()
    
    course_data = []
    total_present = 0
    total_possible = 0
    for row in courses:
        r = dict(row)
        r['percentage'] = round((r['present_count'] / r['total_sessions']) * 100, 1) if r['total_sessions'] > 0 else 0
        if r['percentage'] >= 75:
            r['status'] = 'safe'
        elif r['percentage'] >= 60:
            r['status'] = 'warning'
        else:
            r['status'] = 'critical'
        total_present += r['present_count']
        total_possible += r['total_sessions']
        course_data.append(r)
    
    overall_pct = round((total_present / total_possible) * 100, 1) if total_possible > 0 else 0
    
    # Absent sessions (last 10)
    absent_sessions = conn.execute("""
        SELECT s.id, s.start_time, c.course_name, c.course_code
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        JOIN enrollments e ON e.course_id = c.id AND e.student_id = ?
        WHERE s.id NOT IN (
            SELECT ar.session_id FROM attendance_records ar WHERE ar.student_id = ?
        )
        ORDER BY s.start_time DESC
        LIMIT 20
    """, (student_id, student_id)).fetchall()
    
    conn.close()
    
    return jsonify({
        "student": {
            "id": student['id'],
            "student_name": student['student_name'],
            "university_roll_no": student['university_roll_no'],
            "enrollment_no": student['enrollment_no']
        },
        "overall_percentage": overall_pct,
        "overall_status": 'safe' if overall_pct >= 75 else ('warning' if overall_pct >= 60 else 'critical'),
        "total_present": total_present,
        "total_possible": total_possible,
        "courses": course_data,
        "recent_absences": [dict(r) for r in absent_sessions]
    })


@app.route('/api/admin/analytics/trends', methods=['GET'])
@token_required
def admin_analytics_trends(user_data):
    """Time-series analytics: daily attendance, day-of-week, online vs offline."""
    conn = get_db_connection()
    
    # Daily attendance counts (last 30 days)
    daily = conn.execute("""
        SELECT DATE(s.start_time) as date,
               COUNT(DISTINCT s.id) as session_count,
               COUNT(ar.id) as attendance_count,
               SUM(CASE WHEN s.session_type = 'online' THEN 1 ELSE 0 END) as online_marks,
               SUM(CASE WHEN s.session_type != 'online' THEN 1 ELSE 0 END) as offline_marks
        FROM sessions s
        LEFT JOIN attendance_records ar ON ar.session_id = s.id
        WHERE s.start_time >= date('now', '-30 days')
        GROUP BY DATE(s.start_time)
        ORDER BY date
    """).fetchall()
    
    # Day-of-week pattern
    dow = conn.execute("""
        SELECT 
            CASE CAST(strftime('%w', s.start_time) AS INTEGER)
                WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue'
                WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat'
            END as day_name,
            CAST(strftime('%w', s.start_time) AS INTEGER) as day_num,
            COUNT(DISTINCT s.id) as session_count,
            AVG(sub.cnt) as avg_attendance
        FROM sessions s
        LEFT JOIN (
            SELECT session_id, COUNT(*) as cnt FROM attendance_records GROUP BY session_id
        ) sub ON sub.session_id = s.id
        GROUP BY day_num
        ORDER BY day_num
    """).fetchall()
    
    # Online vs Offline totals
    type_split = conn.execute("""
        SELECT 
            s.session_type,
            COUNT(DISTINCT s.id) as session_count,
            COUNT(ar.id) as attendance_count
        FROM sessions s
        LEFT JOIN attendance_records ar ON ar.session_id = s.id
        GROUP BY s.session_type
    """).fetchall()
    
    # Course-wise session count for bar chart
    course_sessions = conn.execute("""
        SELECT c.course_code,
               COUNT(DISTINCT s.id) as session_count,
               COUNT(ar.id) as total_marks,
               (SELECT COUNT(*) FROM enrollments e WHERE e.course_id = c.id) as enrolled
        FROM courses c
        LEFT JOIN sessions s ON s.course_id = c.id
        LEFT JOIN attendance_records ar ON ar.session_id = s.id
        GROUP BY c.id
        ORDER BY c.course_code
    """).fetchall()
    
    conn.close()
    
    return jsonify({
        "daily": [dict(r) for r in daily],
        "day_of_week": [dict(r) for r in dow],
        "session_type_split": [dict(r) for r in type_split],
        "course_sessions": [dict(r) for r in course_sessions]
    })









# =================================================================
#   TEACHER API ENDPOINTS (Fully Functional)
# =================================================================

#This cod eis fo rgetting the course code and sending it to teacher.js login part to show COURSECODE FIELD in dropdown in the login page of teacher interface 
@app.route('/api/teacher/course-codes', methods=['GET'])
def get_course_codes():
    """Returns all course codes with names for the teacher login dropdown."""
    conn = get_db_connection()
    courses = conn.execute("""
        SELECT course_code, course_name 
        FROM courses 
        ORDER BY course_code
    """).fetchall()
    result = [{"code": row['course_code'], "name": row['course_name']} for row in courses]
    conn.close()
    return jsonify(result)


# Teacher Login API 
@app.route('/api/teacher/login', methods=['POST'])
def teacher_login():
    """
    Handles the teacher's initial login.
    Verifies the course_code and PIN.
    Returns the course name and ID for the setup screen.
    """
    data = request.get_json()
    course_code = data.get('course_code')
    pin = data.get('pin')

    logger.info(f"Teacher login attempt - CourseCode: {course_code}")  # ADDED THIS FOR LOGGING

    conn = get_db_connection()
    course = conn.execute(
        "SELECT id, course_name, teacher_id, default_duration_minutes FROM courses WHERE course_code = ?", 
        (course_code,)
    ).fetchone()
    
    if not course:
        logger.warning(f"Login failed - Invalid course_code: {course_code}")  # ADDED THIS FOR LOGGING
        conn.close()
        return jsonify({"status": "error", "message": "Invalid Course Code"}), 404
        
    teacher = conn.execute("SELECT pin FROM teachers WHERE id = ?", (course['teacher_id'],)).fetchone()
    
    if not teacher or not verify_password(pin, teacher['pin']):
        logger.warning(f"Login failed - Invalid PIN for course_code: {course_code}")  # ADDED THIS FOR LOGGING
        conn.close()
        return jsonify({"status": "error", "message": "Invalid PIN"}), 401
    
    conn.close()
    logger.info(f"Teacher login successful - Course: {course['course_name']}")  # ADDED THIS FOR LOGGING
    return jsonify({
        "status": "success", 
        "course_name": course['course_name'], 
        "course_id": course['id'], 
        "default_duration": course['default_duration_minutes']
    })

@app.route('/api/teacher/start-session', methods=['POST'])
def teacher_start_session():
    """
    Starts a new session after teacher confirms setup.
    Session will auto-close at: start_time + duration_minutes + 5 minutes grace period
    """
    data = request.get_json()
    
    # Validate input
    valid, error = validate_required_fields(data, ['course_id', 'start_datetime', 'duration_minutes', 'session_type'])
    if not valid:
        logger.warning(f"Session start failed - {error}")
        return jsonify({"error": error}), 400
    
    conn = get_db_connection()
    
    # Deactivate any other active sessions for safety
    conn.execute("UPDATE sessions SET is_active = 0, end_time = ? WHERE is_active = 1",
                 (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    
    # CRITICAL FIX: Use current local time, not ISO string from frontend
    start_time = datetime.datetime.now()  # Use server's current time
    duration_minutes = int(data['duration_minutes'])
    grace_period_minutes = 5
    
    # Calculate end time
    end_time = start_time + datetime.timedelta(minutes=duration_minutes + grace_period_minutes)
    
    topic = data.get('topic') # Get the topic from request
    
    logger.info(f"Creating session - Duration: {duration_minutes}min, Grace: {grace_period_minutes}min, "
                f"Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"Scheduled end: {end_time.strftime('%Y-%m-%d %H:%M:%S')}, Topic: {topic}")
    
    # Create new session
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO sessions 
           (course_id, start_time, end_time, is_active, session_type, topic) 
           VALUES (?, ?, ?, 1, ?, ?)""",
        (data['course_id'], 
         start_time.strftime('%Y-%m-%d %H:%M:%S'),
         end_time.strftime('%Y-%m-%d %H:%M:%S'),
         data['session_type'],
         topic)
    )
    session_id = cursor.lastrowid
    conn.commit()
    
    logger.info(f"Session started - ID: {session_id}, Course: {data['course_id']}, "
                f"Duration: {duration_minutes}min (+{grace_period_minutes}min grace)")
    
    # Get enrolled students
    students_cursor = conn.execute("""
        SELECT e.class_roll_id, s.id, s.student_name, s.university_roll_no
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        WHERE e.course_id = ?
        ORDER BY e.class_roll_id
    """, (data['course_id'],)).fetchall()
    
    students = [dict(row) for row in students_cursor]
    conn.close()
    
    return jsonify({
        "status": "success",
        "message": "Session Started",
        "students": students,
        "session_id": session_id,
        "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),  # Send as string
        "duration_minutes": duration_minutes
    })


# =================================================================
#   ONLINE CLASS ATTENDANCE SYSTEM
# =================================================================

import secrets
import hmac
import hashlib
import math

def generate_session_token():
    """Generate a unique, URL-safe token for online session links."""
    return secrets.token_urlsafe(16)

def generate_otp(seed, interval=30):
    """
    Generate a time-based OTP that rotates every `interval` seconds.
    Uses HMAC-SHA256 with the seed and current time window.
    """
    time_window = int(datetime.datetime.now().timestamp()) // interval
    message = f"{seed}:{time_window}".encode('utf-8')
    digest = hmac.new(seed.encode('utf-8'), message, hashlib.sha256).hexdigest()
    # Take first 6 digits
    otp_num = int(digest[:8], 16) % 1000000
    return f"{otp_num:06d}"

def get_otp_time_remaining(interval=30):
    """Get seconds remaining until OTP rotates."""
    now = int(datetime.datetime.now().timestamp())
    return interval - (now % interval)


@app.route('/api/teacher/start-online-session', methods=['POST'])
def start_online_session():
    """Start an online class session. ONLY available on cloud server (Render)."""
    # Only allow on cloud server
    is_cloud = os.environ.get('IS_CLOUD_SERVER', 'false').lower() == 'true'
    if not is_cloud:
        return jsonify({
            "error": "Online class attendance is only available on the cloud server.",
            "hint": "Please access A.R.I.S.E. via the Render cloud URL to use this feature."
        }), 403
    
    data = request.get_json()
    if not data or 'course_id' not in data:
        return jsonify({"error": "course_id is required"}), 400
    
    duration_minutes = int(data.get('duration_minutes', 30))
    topic = data.get('topic', '')
    
    # Generate unique session token and OTP seed
    session_token = secrets.token_urlsafe(16)
    otp_seed = secrets.token_hex(32)
    
    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(minutes=duration_minutes)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Migrate: add session_token and otp_seed columns if they don't exist
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN session_token TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN otp_seed TEXT")
    except Exception:
        pass
    
    # Deactivate any other active sessions
    conn.execute("UPDATE sessions SET is_active = 0, end_time = ? WHERE is_active = 1",
                 (datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    
    cursor.execute(
        """INSERT INTO sessions 
           (course_id, start_time, end_time, is_active, session_type, topic, session_token, otp_seed) 
           VALUES (?, ?, ?, 1, 'online', ?, ?, ?)""",
        (data['course_id'], 
         start_time.strftime('%Y-%m-%d %H:%M:%S'),
         end_time.strftime('%Y-%m-%d %H:%M:%S'),
         topic, session_token, otp_seed)
    )
    session_id = cursor.lastrowid
    conn.commit()
    
    # Get course info
    course = conn.execute("SELECT course_name, course_code FROM courses WHERE id = ?", 
                          (data['course_id'],)).fetchone()
    
    # Get enrolled students count
    student_count = conn.execute("SELECT COUNT(*) as c FROM enrollments WHERE course_id = ?",
                                 (data['course_id'],)).fetchone()['c']
    
    conn.close()
    
    current_otp = generate_otp(otp_seed)
    
    # Build the shareable URL — always use cloud server URL
    cloud_url = os.environ.get('CLOUD_SERVER_URL', request.host_url.rstrip('/'))
    session_url = f"{cloud_url}/online/{session_token}"
    
    logger.info(f"[ONLINE] Session started - ID: {session_id}, Token: {session_token}, "
                f"Course: {course['course_name']}, Duration: {duration_minutes}min")
    
    return jsonify({
        "status": "success",
        "session_id": session_id,
        "session_token": session_token,
        "session_url": session_url,
        "current_otp": current_otp,
        "otp_time_remaining": get_otp_time_remaining(),
        "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
        "duration_minutes": duration_minutes,
        "course_name": course['course_name'] if course else '',
        "course_code": course['course_code'] if course else '',
        "total_students": student_count
    })


@app.route('/online/<token>')
def online_attendance_page(token):
    """Serve the student online attendance page."""
    return render_template('online_attendance.html', token=token)


@app.route('/api/online/session/<token>/info', methods=['GET'])
def online_session_info(token):
    """Get session info for the student attendance page."""
    conn = get_db_connection()
    session = conn.execute("""
        SELECT s.id, s.course_id, s.start_time, s.end_time, s.is_active, s.topic,
               c.course_name, c.course_code, t.teacher_name
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        LEFT JOIN teachers t ON c.teacher_id = t.id
        WHERE s.session_token = ?
    """, (token,)).fetchone()
    
    if not session:
        conn.close()
        return jsonify({"error": "Session not found"}), 404
    
    if not session['is_active']:
        conn.close()
        return jsonify({"error": "Session has ended", "expired": True}), 410
    
    # Count already marked
    marked_count = conn.execute(
        "SELECT COUNT(*) as c FROM attendance_records WHERE session_id = ?",
        (session['id'],)).fetchone()['c']
    
    total_students = conn.execute(
        "SELECT COUNT(*) as c FROM enrollments WHERE course_id = ?",
        (session['course_id'],)).fetchone()['c']
    
    conn.close()
    
    # Calculate time remaining
    end_time = datetime.datetime.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S')
    now = datetime.datetime.now()
    remaining_seconds = max(0, int((end_time - now).total_seconds()))
    
    return jsonify({
        "course_name": session['course_name'],
        "course_code": session['course_code'],
        "teacher_name": session['teacher_name'] or 'Unknown',
        "topic": session['topic'] or '',
        "time_remaining_seconds": remaining_seconds,
        "marked_count": marked_count,
        "total_students": total_students,
        "is_active": True
    })


@app.route('/api/online/mark-attendance', methods=['POST'])
@limiter.limit("5 per minute")
def online_mark_attendance():
    """
    Student marks attendance for an online session using roll number + OTP.
    Anti-cheating: validates OTP, checks enrollment, prevents duplicates.
    """
    data = request.get_json()
    
    valid, error = validate_required_fields(data, ['token', 'university_roll_no', 'otp'])
    if not valid:
        return jsonify({"status": "error", "message": error}), 400
    
    token = data['token']
    roll_no = sanitize_input(data['university_roll_no'].strip().upper())
    submitted_otp = data['otp'].strip()
    
    conn = get_db_connection()
    
    # Find active session
    session = conn.execute(
        "SELECT id, course_id, otp_seed, end_time, is_active FROM sessions WHERE session_token = ?",
        (token,)).fetchone()
    
    if not session:
        conn.close()
        logger.warning(f"[ONLINE] Attendance failed - Invalid token: {token}")
        return jsonify({"status": "error", "message": "Invalid session link"}), 404
    
    if not session['is_active']:
        conn.close()
        return jsonify({"status": "error", "message": "Session has ended"}), 410
    
    # Check time window
    end_time = datetime.datetime.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S')
    if datetime.datetime.now() > end_time:
        conn.close()
        return jsonify({"status": "error", "message": "Session has expired"}), 410
    
    # Validate OTP — check current and previous window (grace period)
    current_otp = generate_otp(session['otp_seed'])
    # Also accept OTP from previous 30-second window (for students typing during transition)
    time_window_prev = (int(datetime.datetime.now().timestamp()) // 30) - 1
    prev_message = f"{session['otp_seed']}:{time_window_prev}".encode('utf-8')
    prev_digest = hmac.new(session['otp_seed'].encode('utf-8'), prev_message, hashlib.sha256).hexdigest()
    prev_otp = f"{int(prev_digest[:8], 16) % 1000000:06d}"
    
    if submitted_otp != current_otp and submitted_otp != prev_otp:
        conn.close()
        logger.warning(f"[ONLINE] Wrong OTP - Roll: {roll_no}, Submitted: {submitted_otp}")
        return jsonify({"status": "error", "message": "Invalid OTP code. Check the code displayed by your teacher."}), 403
    
    # Find student by university roll number
    student = conn.execute(
        "SELECT id, student_name FROM students WHERE UPPER(university_roll_no) = ?",
        (roll_no,)).fetchone()
    
    if not student:
        conn.close()
        logger.warning(f"[ONLINE] Student not found - Roll: {roll_no}")
        return jsonify({"status": "error", "message": "Student not found. Check your roll number."}), 404
    
    # Check enrollment
    enrollment = conn.execute(
        "SELECT class_roll_id FROM enrollments WHERE course_id = ? AND student_id = ?",
        (session['course_id'], student['id'])).fetchone()
    
    if not enrollment:
        conn.close()
        logger.warning(f"[ONLINE] Not enrolled - Roll: {roll_no}, Course: {session['course_id']}")
        return jsonify({"status": "error", "message": "You are not enrolled in this course."}), 403
    
    # Check duplicate
    existing = conn.execute(
        "SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?",
        (session['id'], student['id'])).fetchone()
    
    if existing:
        conn.close()
        return jsonify({"status": "duplicate", "message": "Attendance already marked!", 
                        "student_name": student['student_name']})
    
    # Mark attendance
    conn.execute(
        "INSERT INTO attendance_records (session_id, student_id, override_method) VALUES (?, ?, ?)",
        (session['id'], student['id'], 'online_otp'))
    conn.commit()
    
    logger.info(f"[ONLINE] Attendance marked - {student['student_name']} (Roll: {roll_no})")
    conn.close()
    
    return jsonify({
        "status": "success", 
        "message": "Attendance marked successfully!",
        "student_name": student['student_name']
    })


@app.route('/api/online/session/<token>/otp', methods=['GET'])
def get_current_otp(token):
    """Get the current OTP for a session (teacher use)."""
    conn = get_db_connection()
    session = conn.execute(
        "SELECT otp_seed, is_active FROM sessions WHERE session_token = ?",
        (token,)).fetchone()
    conn.close()
    
    if not session:
        return jsonify({"error": "Session not found"}), 404
    if not session['is_active']:
        return jsonify({"error": "Session ended"}), 410
    
    return jsonify({
        "otp": generate_otp(session['otp_seed']),
        "time_remaining": get_otp_time_remaining()
    })


@app.route('/api/teacher/session/<int:session_id>/online-status', methods=['GET'])
def online_session_status(session_id):
    """Get live attendance status for teacher's online session dashboard."""
    conn = get_db_connection()
    
    session = conn.execute(
        "SELECT id, course_id, is_active, session_token, otp_seed, end_time FROM sessions WHERE id = ?",
        (session_id,)).fetchone()
    
    if not session:
        conn.close()
        return jsonify({"error": "Session not found"}), 404
    
    # Get marked students
    marked = conn.execute("""
        SELECT s.student_name, s.university_roll_no, e.class_roll_id,
               ar.timestamp as marked_at
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.id
        LEFT JOIN enrollments e ON e.student_id = s.id AND e.course_id = ?
        WHERE ar.session_id = ?
        ORDER BY ar.timestamp DESC
    """, (session['course_id'], session_id)).fetchall()
    
    total = conn.execute(
        "SELECT COUNT(*) as c FROM enrollments WHERE course_id = ?",
        (session['course_id'],)).fetchone()['c']
    
    # Get all enrolled students for unmarked list
    all_students = conn.execute("""
        SELECT e.class_roll_id, s.student_name, s.university_roll_no
        FROM enrollments e
        JOIN students s ON e.student_id = s.id
        WHERE e.course_id = ?
        ORDER BY e.class_roll_id
    """, (session['course_id'],)).fetchall()
    
    conn.close()
    
    current_otp = generate_otp(session['otp_seed']) if session['is_active'] else None
    
    return jsonify({
        "is_active": bool(session['is_active']),
        "marked_count": len(marked),
        "total_students": total,
        "current_otp": current_otp,
        "otp_time_remaining": get_otp_time_remaining() if session['is_active'] else 0,
        "marked_students": [dict(s) for s in marked],
        "all_students": [dict(s) for s in all_students],
        "session_token": session['session_token']
    })

@app.route('/api/teacher/manual-override', methods=['POST'])
def manual_override():
    """Handles the teacher's request to manually mark a student present."""
    try:
        data = request.get_json()
        
        # Validate required fields first
        if not data:
            logger.error("Manual override failed - No data received")
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        session_id = data.get('session_id')
        univ_roll_no = data.get('univ_roll_no')
        reason = data.get('reason')
        
        # Check all required fields exist
        if not session_id:
            logger.error("Manual override failed - Missing session_id")
            return jsonify({"status": "error", "message": "Session ID required"}), 400
        
        if not univ_roll_no:
            logger.error("Manual override failed - Missing university roll number")
            return jsonify({"status": "error", "message": "University roll number required"}), 400
        
        if not reason or not reason.strip():
            logger.error("Manual override failed - Missing or empty reason")
            return jsonify({"status": "error", "message": "Reason is required"}), 400
        
        # Log the attempt
        logger.info(f"Manual override attempt - Session: {session_id}, "
                    f"Student: {univ_roll_no}, Reason: '{reason}'")
        
        conn = get_db_connection()
        
        # Ensure the session is still active
        session = conn.execute(
            "SELECT id, course_id FROM sessions WHERE id = ? AND is_active = 1",
            (session_id,)
        ).fetchone()
        
        if not session:
            logger.warning(f"Manual override failed - Session {session_id} not active")
            conn.close()
            return jsonify({"status": "error", "message": "Session is not active or has ended"}), 400
        
        # Find the student
        student = conn.execute(
            "SELECT id, student_name FROM students WHERE university_roll_no = ?",
            (univ_roll_no,)
        ).fetchone()
        
        if not student:
            logger.error(f"Manual override failed - Student not found: {univ_roll_no}")
            conn.close()
            return jsonify({"status": "error", "message": "Student not found"}), 404
        
        # Check if already marked
        existing = conn.execute(
            "SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?",
            (session['id'], student['id'])
        ).fetchone()
        
        if existing:
            logger.warning(f"Manual override rejected - Student {univ_roll_no} already marked")
            conn.close()
            return jsonify({"status": "error", "message": "Student already marked present"}), 400
        
        # Insert attendance record
        conn.execute(
            """INSERT INTO attendance_records 
               (session_id, student_id, override_method, manual_reason) 
               VALUES (?, ?, 'teacher_manual', ?)""",
            (session['id'], student['id'], reason)
        )
        conn.commit()

        conn.close()
        
        # Log success
        logger.info(f"Manual override SUCCESS - Student: {student['student_name']} ({univ_roll_no}), "
                    f"Session: {session['id']}, Course: {session['course_id']}, Reason: '{reason}'")
        
        return jsonify({"status": "success", "message": "Attendance marked manually"})
    
    except Exception as e:
        # Catch any unexpected errors and log them
        logger.error(f"Manual override EXCEPTION: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error occurred"}), 500


@app.route('/api/teacher/emergency-bulk-mark', methods=['POST'])
def emergency_bulk_mark():
    """
    Emergency Mode: Bulk mark multiple students as Present or Absent.
    Each student in the array has their own status.
    Used when the Smart Scanner device fails.
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
        
        session_id = data.get('session_id')
        students = data.get('students', [])
        reason = data.get('reason', 'Emergency Mode')
        
        if not session_id:
            return jsonify({"status": "error", "message": "Session ID required"}), 400
        
        if not students or len(students) == 0:
            return jsonify({"status": "error", "message": "No students selected"}), 400
        
        logger.info(f"Emergency bulk mark - Session: {session_id}, Students: {len(students)}")
        
        conn = get_db_connection()
        
        # Verify session is active
        session = conn.execute(
            "SELECT id, course_id FROM sessions WHERE id = ? AND is_active = 1",
            (session_id,)
        ).fetchone()
        
        if not session:
            conn.close()
            return jsonify({"status": "error", "message": "Session is not active"}), 400
        
        present_count = 0
        absent_count = 0
        skipped_count = 0
        
        for student_data in students:
            # Handle both formats: simple roll string or {roll, status} object
            if isinstance(student_data, dict):
                univ_roll_no = student_data.get('roll')
                status = student_data.get('status', 'present')
            else:
                univ_roll_no = student_data
                status = 'present'
            
            # Find the student
            student = conn.execute(
                "SELECT id, student_name FROM students WHERE university_roll_no = ?",
                (univ_roll_no,)
            ).fetchone()
            
            if not student:
                skipped_count += 1
                continue
            
            # Check if already marked
            existing = conn.execute(
                "SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?",
                (session['id'], student['id'])
            ).fetchone()
            
            if existing:
                skipped_count += 1
                continue
            
            if status == 'present':
                # Insert attendance record for present
                conn.execute(
                    """INSERT INTO attendance_records 
                       (session_id, student_id, override_method, manual_reason) 
                       VALUES (?, ?, 'emergency_mode', ?)""",
                    (session['id'], student['id'], reason)
                )
                present_count += 1
            else:
                # Insert attendance record for absent (with special override method)
                conn.execute(
                    """INSERT INTO attendance_records 
                       (session_id, student_id, override_method, manual_reason) 
                       VALUES (?, ?, 'emergency_mode_absent', ?)""",
                    (session['id'], student['id'], reason + ' - Marked Absent')
                )
                absent_count += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Emergency bulk mark SUCCESS - "
                    f"Present: {present_count}, Absent: {absent_count}, Skipped: {skipped_count}")
        
        return jsonify({
            "status": "success",
            "message": f"Marked {present_count} present, {absent_count} absent",
            "present_count": present_count,
            "absent_count": absent_count,
            "skipped_count": skipped_count
        })
        
    except Exception as e:
        logger.error(f"Emergency bulk mark EXCEPTION: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error occurred"}), 500



# =================================================================
#   TEACHER API ENDPOINTS (Session Management)
# =================================================================

@app.route('/api/teacher/session/<int:session_id>/end', methods=['POST'])
def end_session(session_id):
    """
    Ends the currently active session.
    Critical: This must run BEFORE closing the session.
    """
    conn = get_db_connection()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # STEP 1: Get session details BEFORE closing it
        session = conn.execute(
            "SELECT id, course_id, start_time FROM sessions WHERE id = ?",
            (session_id,)
        ).fetchone()
        
        if not session:
            logger.warning(f"End session failed - Session {session_id} not found")
            conn.close()
            return jsonify({"status": "error", "message": "Session not found"}), 404
        
        course_id = session['course_id']
        
        # STEP 2: Get ALL enrolled students in this course
        enrolled_students = conn.execute("""
            SELECT s.id, s.student_name 
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            WHERE e.course_id = ?
        """, (course_id,)).fetchall()
        
        logger.info(f"End session {session_id}: Found {len(enrolled_students)} enrolled students")
        
        # STEP 3: Get students who ATTENDED this session
        attended = conn.execute("""
            SELECT DISTINCT student_id 
            FROM attendance_records 
            WHERE session_id = ?
        """, (session_id,)).fetchall()
        
        attended_ids = set(row['student_id'] for row in attended)
        logger.info(f"End session {session_id}: {len(attended_ids)} students marked present")
        
        # STEP 4: Count absent students
        absent_count = 0
        for student in enrolled_students:
            student_id = student['id']
            student_name = student['student_name']
            
            # Check if this student was ABSENT (NOT in attended_ids)
            if student_id not in attended_ids:
                logger.info(f"  Absent: {student_name}")
                absent_count += 1
        
        # STEP 5: NOW close the session in database
        conn.execute(
            "UPDATE sessions SET is_active = 0, end_time = ? WHERE id = ?",
            (now, session_id)
        )
        conn.commit()
        
        logger.info(f"Session ended - ID: {session_id}, Absent count: {absent_count}")
        
        conn.close()
        return jsonify({
            "status": "success", 
            "message": f"Session ended. {absent_count} students marked absent."
        })
    
    except Exception as e:
        logger.error(f"Error ending session {session_id}: {e}", exc_info=True)
        conn.close()
        return jsonify({"status": "error", "message": "Server error"}), 500


@app.route('/api/teacher/session/<int:session_id>/extend', methods=['POST'])
def extend_session(session_id):
    """
    Extends session by 10 minutes.
    Returns new end time for frontend countdown timer update.
    """
    conn = get_db_connection()
    
    session = conn.execute(
        "SELECT id, course_id, end_time, is_active FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    
    if not session:
        conn.close()
        logger.warning(f"Extend failed - Session {session_id} not found")
        return jsonify({"status": "error", "message": "Session not found"}), 404
    
    if not session['is_active']:
        conn.close()
        logger.warning(f"Extend failed - Session {session_id} already ended")
        return jsonify({"status": "error", "message": "Session has already ended"}), 400
    
    # Parse the stored end_time string
    current_end_time_str = session['end_time']
    
    try:
        if '.' in current_end_time_str:
            current_end_time = datetime.datetime.strptime(current_end_time_str, '%Y-%m-%d %H:%M:%S.%f')
        else:
            current_end_time = datetime.datetime.strptime(current_end_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        conn.close()
        logger.error(f"Could not parse end_time '{current_end_time_str}': {e}")
        return jsonify({"status": "error", "message": "Invalid time format"}), 500
    
    extension_minutes = 10
    new_end_time = current_end_time + datetime.timedelta(minutes=extension_minutes)
    new_end_time_str = new_end_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # CRITICAL: Update database with new end time
    conn.execute("UPDATE sessions SET end_time = ? WHERE id = ?",
                (new_end_time_str, session_id))
    conn.commit()
    
    logger.info(f"Session extended - ID: {session_id}, Course: {session['course_id']}, "
                f"Extension: +{extension_minutes}min, "
                f"Old end: {current_end_time_str}, "
                f"New end: {new_end_time_str}")
    
    conn.close()
    
    return jsonify({
        "status": "success",
        "new_end_time": new_end_time_str,
        "message": f"Session extended by {extension_minutes} minutes"
    })

@app.route('/api/teacher/session/<int:session_id>/check-expire', methods=['POST'])
def check_and_expire_session(session_id):
    """
    Checks if session should be expired based on current time vs end_time.
    Called by frontend when countdown reaches 0:00.
    Immediately expires the session if time has passed.
    """
    conn = get_db_connection()
    now = datetime.datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    session = conn.execute(
        "SELECT id, course_id, end_time, is_active FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    
    if not session:
        conn.close()
        return jsonify({"status": "not_found", "expired": False}), 404
    
    if not session['is_active']:
        conn.close()
        return jsonify({"status": "already_ended", "expired": True}), 200
    
    # Parse end_time
    end_time_str = session['end_time']
    try:
        if '.' in end_time_str:
            end_time = datetime.datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S.%f')
        else:
            end_time = datetime.datetime.strptime(end_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        conn.close()
        return jsonify({"status": "error", "expired": False}), 500
    
    # Check if current time has passed end time
    if now >= end_time:
        # Time to expire this session!
        conn.execute("UPDATE sessions SET is_active = 0 WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
        
        logger.warning(f"Session force-expired by countdown check - ID: {session_id}, "
                      f"End time was: {end_time_str}, Current time: {now_str}")
        
        return jsonify({"status": "expired", "expired": True}), 200
    else:
        # Not yet time to expire
        conn.close()
        seconds_remaining = (end_time - now).total_seconds()
        return jsonify({
            "status": "active", 
            "expired": False, 
            "seconds_remaining": int(seconds_remaining)
        }), 200

@app.route('/api/teacher/session/<int:session_id>/status', methods=['GET'])
def get_live_session_status(session_id):
    """
    Provides a real-time status update for the live dashboard.
    Returns the list of students who have been marked present.
    ALSO returns whether session is still active (critical for auto-expire detection).
    """
    conn = get_db_connection()
    
    # Check if session is still active
    session = conn.execute(
        "SELECT is_active FROM sessions WHERE id = ?",
        (session_id,)
    ).fetchone()
    
    if not session:
        conn.close()
        return jsonify({"session_active": False, "marked_students": [], "absent_students": []}), 404
    
    is_active = bool(session['is_active'])
    
    # Get marked students (present - NOT marked as absent)
    present_cursor = conn.execute("""
        SELECT s.university_roll_no
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.id
        WHERE ar.session_id = ? AND (ar.override_method IS NULL OR ar.override_method != 'emergency_mode_absent')
    """, (session_id,)).fetchall()
    
    # Get absent students (marked as absent via emergency mode)
    absent_cursor = conn.execute("""
        SELECT s.university_roll_no
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.id
        WHERE ar.session_id = ? AND ar.override_method = 'emergency_mode_absent'
    """, (session_id,)).fetchall()
    
    marked_students = [row['university_roll_no'] for row in present_cursor]
    absent_students = [row['university_roll_no'] for row in absent_cursor]
    conn.close()
    
    return jsonify({
        "session_active": is_active,  # CRITICAL: Frontend needs this
        "marked_students": marked_students,
        "absent_students": absent_students
    })

@app.route('/api/teacher/report/<int:session_id>', methods=['GET'])
def get_session_report(session_id):
    """
    Generates the complete, final attendance report matrix for a given session's course.
    """
    conn = get_db_connection()
    
    # First, get the course ID from the session ID
    course = conn.execute("SELECT course_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not course:
        logger.warning(f"Report generation failed - Session {session_id} not found")
        conn.close()
        return jsonify({"error": "Session not found"}), 404
    course_id = course['course_id']
    logger.info(f"Generating attendance report - SessionID: {session_id}, CourseID: {course_id}")

    # Get all students enrolled in this course
    students_cursor = conn.execute("""
        SELECT s.id, s.student_name, s.university_roll_no, s.enrollment_no, e.class_roll_id
        FROM students s
        JOIN enrollments e ON s.id = e.student_id
        WHERE e.course_id = ? ORDER BY e.class_roll_id
    """, (course_id,)).fetchall()
    students = [dict(row) for row in students_cursor]

    # Get all sessions for this course, up to and including the current one
    sessions_cursor = conn.execute("""
        SELECT id, start_time FROM sessions 
        WHERE course_id = ?
        ORDER BY start_time
    """, (course_id,)).fetchall()
    sessions = [dict(row) for row in sessions_cursor]

    # Get all attendance records for these sessions
    session_ids = [s['id'] for s in sessions]
    if not session_ids:
        # Handle case with no sessions
        return jsonify({"students": students, "sessions": sessions, "records": {}})

    placeholders = ','.join('?' for _ in session_ids)
    # Get present records (NOT emergency_mode_absent)
    present_cursor = conn.execute(f"""
        SELECT session_id, student_id FROM attendance_records
        WHERE session_id IN ({placeholders})
        AND (override_method IS NULL OR override_method != 'emergency_mode_absent')
    """, session_ids).fetchall()
    
    # Get absent records (emergency_mode_absent only)
    absent_cursor = conn.execute(f"""
        SELECT session_id, student_id FROM attendance_records
        WHERE session_id IN ({placeholders})
        AND override_method = 'emergency_mode_absent'
    """, session_ids).fetchall()
    
    # Create fast lookup sets for presence/absence check: (session_id, student_id)
    present_set = set((rec['session_id'], rec['student_id']) for rec in present_cursor)
    absent_set = set((rec['session_id'], rec['student_id']) for rec in absent_cursor)
    
    conn.close()

    # Structure the data for the frontend
    report_data = {
        "students": students,
        "sessions": sessions,
        "present_set": list(present_set),  # Convert set to list for JSON
        "absent_set": list(absent_set)     # Absent students marked via emergency mode
    }
    
    logger.info(f"Report generated - SessionID: {session_id}, Students: {len(students)}, "
                f"Sessions: {len(sessions)}, Present records: {len(present_set)}, Absent records: {len(absent_set)}")
    
    return jsonify(report_data)


# =================================================================
#   TEACHER API ENDPOINTS (Export In Excel)
# =================================================================

@app.route('/api/teacher/report/export/<int:session_id>')
def export_session_report(session_id):
    """
    Generates a .xlsx Excel file of the attendance report and sends it for download.
    """
    # This logic re-uses the get_session_report logic, but formats it into an Excel sheet
    # (For brevity, the data fetching is duplicated. In a large app, this would be refactored)
    conn = get_db_connection()
    course = conn.execute("SELECT c.course_name FROM sessions s JOIN courses c ON s.course_id = c.id WHERE s.id = ?", (session_id,)).fetchone()
    course_id = conn.execute("SELECT course_id FROM sessions WHERE id = ?", (session_id,)).fetchone()['course_id']
    logger.info(f"Excel export started - SessionID: {session_id}, CourseID: {course_id}")
    students = [dict(row) for row in conn.execute("SELECT s.id, s.student_name, s.university_roll_no, s.enrollment_no, e.class_roll_id FROM students s JOIN enrollments e ON s.id = e.student_id WHERE e.course_id = ? ORDER BY e.class_roll_id", (course_id,)).fetchall()]
    sessions = [dict(row) for row in conn.execute(
        "SELECT id, start_time FROM sessions WHERE course_id = ? ORDER BY start_time",
        (course_id,)
    ).fetchall()]
    session_ids = [s['id'] for s in sessions]
    present_set = set()
    absent_set = set()
    if session_ids:
        placeholders = ','.join('?' for _ in session_ids)
        # Get present records (NOT emergency_mode_absent)
        present_cursor = conn.execute(f"""
            SELECT session_id, student_id FROM attendance_records 
            WHERE session_id IN ({placeholders})
            AND (override_method IS NULL OR override_method != 'emergency_mode_absent')
        """, session_ids).fetchall()
        present_set = set((rec['session_id'], rec['student_id']) for rec in present_cursor)
        
        # Get absent records (emergency_mode_absent only)
        absent_cursor = conn.execute(f"""
            SELECT session_id, student_id FROM attendance_records 
            WHERE session_id IN ({placeholders})
            AND override_method = 'emergency_mode_absent'
        """, session_ids).fetchall()
        absent_set = set((rec['session_id'], rec['student_id']) for rec in absent_cursor)
    conn.close()

    # --- Create Excel Workbook in Memory ---
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Report"

    # Header Row
    headers = ["Class Roll ID", "Student Name", "University Roll No."] + [
        datetime.datetime.fromisoformat(s['start_time']).strftime('%d-%b-%Y %H:%M') for s in sessions
    ]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    # Data Rows
    for student in students:
        row_data = [student['class_roll_id'], student['student_name'], student['university_roll_no']]
        for session in sessions:
            if (session['id'], student['id']) in present_set:
                row_data.append("P")
            else:
                row_data.append("A")
        ws.append(row_data)

    # Save to an in-memory stream
    in_memory_file = io.BytesIO()
    wb.save(in_memory_file)
    in_memory_file.seek(0) # Move cursor to the beginning of the stream

    logger.info(f"Excel export complete - SessionID: {session_id}, "
                f"Students: {len(students)}, Sessions: {len(sessions)}")
    
    return send_file(
        in_memory_file,
        as_attachment=True,
        download_name=f"Attendance_Report_{course['course_name']}_{datetime.date.today()}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# =================================================================
#   TEACHER API ENDPOINTS (Dashboard Analytics & History)
# =================================================================

@app.route('/api/teacher/analytics/<int:course_id>', methods=['GET'])
def get_teacher_analytics(course_id):
    """
    Returns comprehensive analytics for the teacher dashboard.
    Includes: avg attendance, at-risk students, trend graph (base64).
    """
    try:
        conn = get_db_connection()
        logger.info(f"Loading teacher analytics - CourseID: {course_id}")
        
        # Get all sessions for this course
        sessions_cursor = conn.execute("""
            SELECT id, start_time, topic 
            FROM sessions 
            WHERE course_id = ? 
            ORDER BY start_time
        """, (course_id,)).fetchall()
        sessions = [dict(row) for row in sessions_cursor]
        
        if not sessions:
            conn.close()
            return jsonify({
                "total_sessions": 0,
                "avg_attendance_percent": 0,
                "at_risk_students": [],
                "trend_graph_base64": None,
                "message": "No sessions found for this course"
            })
        
        # Get total enrolled students
        enrolled_count = conn.execute("""
            SELECT COUNT(*) as count FROM enrollments WHERE course_id = ?
        """, (course_id,)).fetchone()['count']
        
        if enrolled_count == 0:
            conn.close()
            return jsonify({
                "total_sessions": len(sessions),
                "avg_attendance_percent": 0,
                "at_risk_students": [],
                "trend_graph_base64": None,
                "message": "No students enrolled in this course"
            })
        
        session_ids = [s['id'] for s in sessions]
        placeholders = ','.join('?' for _ in session_ids)
        
        # Get all attendance records for these sessions (exclude emergency_mode_absent)
        records = conn.execute(f"""
            SELECT session_id, student_id 
            FROM attendance_records 
            WHERE session_id IN ({placeholders})
            AND (override_method IS NULL OR override_method != 'emergency_mode_absent')
        """, session_ids).fetchall()
        
        # Create attendance lookup
        attendance_by_session = {}
        attendance_by_student = {}
        
        for rec in records:
            # Count per session
            sid = rec['session_id']
            if sid not in attendance_by_session:
                attendance_by_session[sid] = 0
            attendance_by_session[sid] += 1
            
            # Count per student
            stud_id = rec['student_id']
            if stud_id not in attendance_by_student:
                attendance_by_student[stud_id] = 0
            attendance_by_student[stud_id] += 1
        
        # Calculate average attendance percentage
        total_possible = len(sessions) * enrolled_count
        total_present = sum(attendance_by_session.values())
        avg_percent = (total_present / total_possible * 100) if total_possible > 0 else 0
        
        # Prepare session data for trend graph
        sessions_data = []
        for session in sessions:
            sessions_data.append({
                'date': session['start_time'],
                'present_count': attendance_by_session.get(session['id'], 0),
                'total_students': enrolled_count,
                'topic': session.get('topic', '')
            })
        
        # Generate trend graph
        trend_graph = analytics.generate_attendance_trend_graph(sessions_data)
        
        # Get all enrolled students for at-risk calculation
        students_cursor = conn.execute("""
            SELECT s.id as student_id, s.student_name, s.university_roll_no, e.class_roll_id
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            WHERE e.course_id = ?
        """, (course_id,)).fetchall()
        
        students_data = []
        for student in students_cursor:
            students_data.append({
                'student_id': student['student_id'],
                'student_name': student['student_name'],
                'university_roll_no': student['university_roll_no'],
                'class_roll_id': student['class_roll_id'],
                'present_count': attendance_by_student.get(student['student_id'], 0),
                'total_sessions': len(sessions)
            })
        
        # Get at-risk students
        at_risk = analytics.get_at_risk_students(students_data)
        
        conn.close()
        
        return jsonify({
            "total_sessions": len(sessions),
            "enrolled_count": enrolled_count,
            "avg_attendance_percent": round(avg_percent, 1),
            "at_risk_students": at_risk,
            "trend_graph_base64": trend_graph
        })
        
    except Exception as e:
        logger.error(f"Error in teacher analytics for CourseID {course_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to load analytics"}), 500


@app.route('/api/teacher/history/<int:course_id>', methods=['GET'])
def get_teacher_history(course_id):
    """
    Returns list of past sessions for the course.
    Includes present count and total students for each session.
    """
    try:
        conn = get_db_connection()
        logger.info(f"Loading teacher history - CourseID: {course_id}")
        
        # Get enrolled student count
        enrolled_count = conn.execute("""
            SELECT COUNT(*) as count FROM enrollments WHERE course_id = ?
        """, (course_id,)).fetchone()['count']
        
        # Get all sessions for this course (most recent first)
        sessions_cursor = conn.execute("""
            SELECT id, start_time, end_time, session_type, topic, is_active
            FROM sessions 
            WHERE course_id = ?
            ORDER BY start_time DESC
        """, (course_id,)).fetchall()
        
        sessions = []
        for session in sessions_cursor:
            # Get attendance count for this session (exclude emergency_mode_absent)
            present_count = conn.execute("""
                SELECT COUNT(*) as count 
                FROM attendance_records 
                WHERE session_id = ?
                AND (override_method IS NULL OR override_method != 'emergency_mode_absent')
            """, (session['id'],)).fetchone()['count']
            
            # Parse date nicely
            try:
                start_dt = datetime.datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S')
                date_display = start_dt.strftime('%d %b %Y')
                time_display = start_dt.strftime('%I:%M %p')
            except:
                date_display = session['start_time'][:10] if session['start_time'] else 'Unknown'
                time_display = ''
            
            sessions.append({
                'id': session['id'],
                'date': date_display,
                'time': time_display,
                'start_time': session['start_time'],
                'end_time': session['end_time'],
                'session_type': session['session_type'],
                'topic': session['topic'] or 'No topic',
                'is_active': session['is_active'],
                'present_count': present_count,
                'total_students': enrolled_count,
                'attendance_percent': round((present_count / enrolled_count * 100), 1) if enrolled_count > 0 else 0
            })
        
        conn.close()
        
        return jsonify({
            "sessions": sessions,
            "total_count": len(sessions)
        })
        
    except Exception as e:
        logger.error(f"Error loading teacher history for CourseID {course_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to load history"}), 500


@app.route('/api/teacher/session-detail/<int:session_id>', methods=['GET'])
def get_session_detail(session_id):
    """
    Returns detailed attendance record for a specific session.
    Shows all students with their attendance status.
    """
    try:
        conn = get_db_connection()
        logger.info(f"Loading session detail - SessionID: {session_id}")
        
        # Get session info
        session = conn.execute("""
            SELECT s.id, s.course_id, s.start_time, s.topic, s.session_type, s.is_active
            FROM sessions s
            WHERE s.id = ?
        """, (session_id,)).fetchone()
        
        if not session:
            conn.close()
            return jsonify({"error": "Session not found"}), 404
        
        # Get all enrolled students
        students_cursor = conn.execute("""
            SELECT s.id as student_id, s.student_name, s.university_roll_no, e.class_roll_id
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            WHERE e.course_id = ?
            ORDER BY e.class_roll_id
        """, (session['course_id'],)).fetchall()
        
        # Get attendance records for this session
        records = conn.execute("""
            SELECT student_id, override_method, manual_reason, timestamp
            FROM attendance_records
            WHERE session_id = ?
        """, (session_id,)).fetchall()
        
        # Create attendance lookup
        attendance_map = {rec['student_id']: dict(rec) for rec in records}
        
        # Build student list with status
        present_students = []
        absent_students = []
        
        for student in students_cursor:
            student_data = {
                'student_id': student['student_id'],
                'student_name': student['student_name'],
                'university_roll_no': student['university_roll_no'],
                'class_roll_id': student['class_roll_id']
            }
            
            if student['student_id'] in attendance_map:
                record = attendance_map[student['student_id']]
                method = record.get('override_method', 'fingerprint')
                
                # Check if student was marked as absent via emergency mode
                if method == 'emergency_mode_absent':
                    student_data['status'] = 'absent'
                    student_data['method'] = method
                    student_data['reason'] = record.get('manual_reason', '')
                    student_data['is_marked_absent'] = True  # Explicitly marked absent
                    absent_students.append(student_data)
                else:
                    student_data['status'] = 'present'
                    student_data['method'] = method
                    student_data['reason'] = record.get('manual_reason', '')
                    present_students.append(student_data)
            else:
                student_data['status'] = 'absent'
                student_data['is_marked_absent'] = False  # Unmarked (didn't show up)
                absent_students.append(student_data)
        
        conn.close()
        
        return jsonify({
            "session_id": session['id'],
            "start_time": session['start_time'],
            "topic": session['topic'] or 'No topic',
            "session_type": session['session_type'],
            "is_active": session['is_active'],
            "present_students": present_students,
            "absent_students": absent_students,
            "present_count": len(present_students),
            "absent_count": len(absent_students),
            "total_students": len(present_students) + len(absent_students)
        })
        logger.info(f"Session detail loaded - SessionID: {session_id}, "
                    f"Present: {len(present_students)}, Absent: {len(absent_students)}")
        
    except Exception as e:
        logger.error(f"Error loading session detail: {e}", exc_info=True)
        return jsonify({"error": "Failed to load session details"}), 500


@app.route('/api/teacher/update-attendance', methods=['POST'])
def update_attendance_retroactive():
    """
    Retroactively update attendance for a past session.
    Allows marking absent students as present or removing attendance.
    Requires a reason for audit trail.
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        valid, error = validate_required_fields(data, ['session_id', 'student_id', 'action', 'manual_reason'])
        if not valid:
            logger.warning(f"Update attendance failed - {error}")
            return jsonify({"error": error}), 400
        
        session_id = data['session_id']
        student_id = data['student_id']
        action = data['action']  # 'mark_present' or 'mark_absent'
        reason = data['manual_reason'].strip()
        
        if not reason:
            return jsonify({"error": "Reason is required for retroactive changes"}), 400
        
        if action not in ['mark_present', 'mark_absent']:
            return jsonify({"error": "Invalid action. Use 'mark_present' or 'mark_absent'"}), 400
        
        conn = get_db_connection()
        
        # Verify session exists
        session = conn.execute("SELECT id, course_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not session:
            conn.close()
            return jsonify({"error": "Session not found"}), 404
        
        # Verify student is enrolled in this course
        enrollment = conn.execute("""
            SELECT 1 FROM enrollments WHERE student_id = ? AND course_id = ?
        """, (student_id, session['course_id'])).fetchone()
        if not enrollment:
            conn.close()
            return jsonify({"error": "Student not enrolled in this course"}), 400
        
        if action == 'mark_present':
            # Check if already marked present
            existing = conn.execute("""
                SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?
            """, (session_id, student_id)).fetchone()
            
            if existing:
                conn.close()
                return jsonify({"error": "Student is already marked present"}), 400
            
            # Insert attendance record with retroactive flag
            conn.execute("""
                INSERT INTO attendance_records 
                (session_id, student_id, override_method, manual_reason)
                VALUES (?, ?, 'retroactive_manual', ?)
            """, (session_id, student_id, reason))
            conn.commit()
            
            logger.info(f"Retroactive attendance - MARKED PRESENT - Session: {session_id}, "
                        f"Student: {student_id}, Reason: '{reason}'")
            
            conn.close()
            return jsonify({
                "status": "success",
                "message": "Student marked present"
            })
            
        elif action == 'mark_absent':
            # Check if attendance record exists
            existing = conn.execute("""
                SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?
            """, (session_id, student_id)).fetchone()
            
            if not existing:
                conn.close()
                return jsonify({"error": "Student is not marked present for this session"}), 400
            
            # Delete the attendance record
            conn.execute("""
                DELETE FROM attendance_records WHERE session_id = ? AND student_id = ?
            """, (session_id, student_id))
            conn.commit()
            
            logger.info(f"Retroactive attendance - MARKED ABSENT - Session: {session_id}, "
                        f"Student: {student_id}, Reason: '{reason}'")
            
            conn.close()
            return jsonify({
                "status": "success",
                "message": "Attendance record removed"
            })
            
    except Exception as e:
        logger.error(f"Error updating attendance: {e}", exc_info=True)
        return jsonify({"error": "Failed to update attendance"}), 500


@app.route('/api/teacher/validate-session/<int:course_id>', methods=['GET'])
def validate_teacher_session(course_id):
    """
    Validates if a course exists and checks for any active session.
    Used by SPA to restore session after page refresh.
    Also returns enrolled students if there's an active session.
    """
    try:
        conn = get_db_connection()
        
        # Check if course exists
        course = conn.execute("""
            SELECT c.id, c.course_name, c.course_code, c.default_duration_minutes, t.teacher_name
            FROM courses c
            JOIN teachers t ON c.teacher_id = t.id
            WHERE c.id = ?
        """, (course_id,)).fetchone()
        
        if not course:
            logger.warning(f"Session validation failed - CourseID {course_id} not found")
            conn.close()
            return jsonify({"valid": False, "message": "Course not found"}), 404
        
        # Check for active session
        active_session = conn.execute("""
            SELECT id, start_time, end_time, topic, session_type
            FROM sessions
            WHERE course_id = ? AND is_active = 1
        """, (course_id,)).fetchone()
        
        result = {
            "valid": True,
            "course": {
                "id": course['id'],
                "course_name": course['course_name'],
                "course_code": course['course_code'],
                "default_duration": course['default_duration_minutes'],
                "teacher_name": course['teacher_name']
            },
            "has_active_session": active_session is not None
        }
        
        if active_session:
            result["active_session"] = {
                "id": active_session['id'],
                "start_time": active_session['start_time'],
                "end_time": active_session['end_time'],
                "topic": active_session['topic'],
                "session_type": active_session['session_type']
            }
            
            # Also fetch enrolled students for session restore
            students_cursor = conn.execute("""
                SELECT s.id, s.student_name, s.university_roll_no, e.class_roll_id
                FROM students s
                JOIN enrollments e ON s.id = e.student_id
                WHERE e.course_id = ?
                ORDER BY e.class_roll_id
            """, (course_id,)).fetchall()
            
            result["students"] = [
                {
                    "id": row['id'],
                    "student_name": row['student_name'],
                    "university_roll_no": row['university_roll_no'],
                    "class_roll_id": row['class_roll_id']
                }
                for row in students_cursor
            ]
        
        conn.close()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error validating session: {e}", exc_info=True)
        return jsonify({"valid": False, "error": "Validation failed"}), 500


# END OF PART 2








# START OF PART 3








# =================================================================
#   STUDENT API ENDPOINTS
# =================================================================
# In our Admin-first build, these will be simple placeholders.

@app.route('/api/student/login', methods=['POST'])
@limiter.limit(Config.RATE_LIMIT_LOGIN)
def student_login():
    data = request.get_json()
    univ_roll_no = sanitize_input(data.get('university_roll_no')); password = data.get('password')
    logger.info(f"Student login attempt - Roll: {univ_roll_no}")
    conn = get_db_connection()
    student = conn.execute("SELECT id, student_name, password FROM students WHERE university_roll_no = ?", (univ_roll_no,)).fetchone()
    conn.close()
    if student and verify_password(password, student['password']):
        token = jwt.encode({'student_id': student['id'], 'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)}, app.config['SECRET_KEY'], algorithm="HS256")
        logger.info(f"Student login successful - Roll: {univ_roll_no}, Name: {student['student_name']}")
        return jsonify({'token': token, 'student_name': student['student_name']})
    logger.warning(f"Student login failed - Invalid credentials for roll: {univ_roll_no}")
    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/api/student/semesters', methods=['GET'])
@token_required
def get_student_semesters(user_data):
    """
    Returns ALL semesters and courses available in the system.
    This enables the 'Batch Leaderboard' functionality, allowing students
    to view rankings for semesters/courses they might not be enrolled in.
    """
    conn = get_db_connection()
    
    # 1. Get ALL Semesters (ordered by ID or name)
    semesters_cursor = conn.execute("SELECT id, semester_name FROM semesters ORDER BY id").fetchall()
    semesters = [dict(row) for row in semesters_cursor]
    
    # 2. Get ALL Courses for each semester
    for semester in semesters:
        courses_cursor = conn.execute("""
            SELECT id, course_name, course_code
            FROM courses 
            WHERE semester_id = ?
            ORDER BY course_name
        """, (semester['id'],)).fetchall()
        
        semester['courses'] = [dict(row) for row in courses_cursor]
    
    conn.close()
    return jsonify(semesters)

@app.route('/api/student/dashboard', methods=['GET'])
@token_required
def get_student_dashboard(user_data):
    student_id = user_data['student_id']
    semester_id = request.args.get('semester_id', type=int)  # Optional query parameter
    
    conn = get_db_connection()
    
    # Get student name
    student = conn.execute("SELECT student_name FROM students WHERE id = ?", (student_id,)).fetchone()
    student_name = student['student_name'] if student else 'Student'
    
    # Base query for courses
    if semester_id:
        # Filter by specific semester
        courses_cursor = conn.execute("""
            SELECT c.id as course_id, c.course_name, s.semester_name
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN semesters s ON c.semester_id = s.id
            WHERE e.student_id = ? AND c.semester_id = ?
        """, (student_id, semester_id)).fetchall()
    else:
        # Get all courses (default behavior)
        courses_cursor = conn.execute("""
            SELECT c.id as course_id, c.course_name, s.semester_name
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN semesters s ON c.semester_id = s.id
            WHERE e.student_id = ?
        """, (student_id,)).fetchall()
    
    courses_data = []
    total_present_overall = 0
    total_sessions_overall = 0
    semester_name = None

    for course in courses_cursor:
        if semester_name is None and course['semester_name']:
            semester_name = course['semester_name']
            
        sessions_cursor = conn.execute("SELECT id FROM sessions WHERE course_id = ?", (course['course_id'],)).fetchall()
        session_ids = [s['id'] for s in sessions_cursor]
        total_sessions = len(session_ids)
        
        if total_sessions > 0:
            present_cursor = conn.execute(f"SELECT COUNT(id) as present_count FROM attendance_records WHERE student_id = ? AND session_id IN ({','.join(['?']*len(session_ids))})", [student_id] + session_ids)
            present_count = present_cursor.fetchone()['present_count']
        else:
            present_count = 0
        
        percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0
        total_present_overall += present_count
        total_sessions_overall += total_sessions
        
        # Use analytics module for comprehensive status and improvement plan
        analytics_data = analytics.calculate_status_and_improvement(
            present_count, 
            total_sessions, 
            target_percent=MINIMUM_ATTENDANCE_PERCENTAGE,
            critical_percent=ATTENDANCE_WARNING_THRESHOLD
        )
        
        # Determine warning status based on threshold
        if percentage >= MINIMUM_ATTENDANCE_PERCENTAGE:
            warning_status = 'good'
        elif percentage >= ATTENDANCE_WARNING_THRESHOLD:
            warning_status = 'warning'
        else:
            warning_status = 'critical'
        
        courses_data.append({
            "course_id": course['course_id'], 
            "course_name": course['course_name'], 
            "semester_name": course['semester_name'],
            "percentage": analytics_data['current_percent'], 
            "present_count": present_count, 
            "absent_count": total_sessions - present_count, 
            "total_sessions": total_sessions,
            "warning_status": warning_status,
            "analytics": analytics_data
        })
        
    conn.close()
    overall_percentage = (total_present_overall / total_sessions_overall * 100) if total_sessions_overall > 0 else 0
    
    return jsonify({
        "student_name": student_name,
        "overall_percentage": round(overall_percentage),
        "semester_id": semester_id,
        "semester_name": semester_name,
        "is_filtered": semester_id is not None,
        "courses": courses_data,
        "min_attendance_requirement": MINIMUM_ATTENDANCE_PERCENTAGE
    })

@app.route('/api/student/critical-alerts', methods=['GET'])
@token_required
def get_critical_alerts(user_data):
    """
    Get attendance alerts for student.
    Returns two categories:
    1. Critical alerts: attendance < 60% (ATTENDANCE_WARNING_THRESHOLD)
    2. Warning alerts: attendance 60-75% with classes needed to reach 75%
    """
    import math
    
    student_id = user_data['student_id']
    
    conn = get_db_connection()
    
    # Get all enrolled courses
    courses_cursor = conn.execute("""
        SELECT c.id as course_id, c.course_name
        FROM courses c
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ?
    """, (student_id,)).fetchall()
    
    critical_alerts = []  # < 60%
    warning_alerts = []   # 60% - 75%
    
    for course in courses_cursor:
        course_id = course['course_id']
        
        # Get all sessions for this course
        sessions_cursor = conn.execute("SELECT id FROM sessions WHERE course_id = ?", (course_id,)).fetchall()
        session_ids = [s['id'] for s in sessions_cursor]
        total_sessions = len(session_ids)
        
        if total_sessions > 0:
            present_cursor = conn.execute(
                f"SELECT COUNT(id) as present_count FROM attendance_records WHERE student_id = ? AND session_id IN ({','.join(['?']*len(session_ids))})",
                [student_id] + session_ids
            )
            present_count = present_cursor.fetchone()['present_count']
            
            percentage = (present_count / total_sessions * 100)
            
            # Categorize alerts
            if percentage < ATTENDANCE_WARNING_THRESHOLD:  # < 60%
                critical_alerts.append({
                    "course_id": course_id,
                    "course_name": course['course_name'],
                    "attendance_percentage": round(percentage, 1),
                    "present_count": present_count,
                    "total_sessions": total_sessions,
                    "status": "critical"
                })
            elif percentage < MINIMUM_ATTENDANCE_PERCENTAGE:  # 60% - 75%
                # Calculate how many more classes needed to reach 75%
                classes_needed_for_75 = math.ceil((0.75 * total_sessions) - present_count)
                
                warning_alerts.append({
                    "course_id": course_id,
                    "course_name": course['course_name'],
                    "attendance_percentage": round(percentage, 1),
                    "present_count": present_count,
                    "total_sessions": total_sessions,
                    "classes_needed": max(0, classes_needed_for_75),
                    "status": "warning"
                })
        else:
            present_count = 0
            # Skip alerts if there are no sessions
            continue
    
    conn.close()
    
    return jsonify({
        "critical_alerts": critical_alerts,
        "warning_alerts": warning_alerts,
        "critical_count": len(critical_alerts),
        "warning_count": len(warning_alerts),
        "total_alert_count": len(critical_alerts) + len(warning_alerts),
        "critical_threshold": ATTENDANCE_WARNING_THRESHOLD,
        "minimum_threshold": MINIMUM_ATTENDANCE_PERCENTAGE
    }), 200

@app.route('/api/student/analytics', methods=['GET'])
@token_required
def get_student_analytics(user_data):
    """Returns detailed attendance analytics including trends and warnings."""
    if not ENABLE_ATTENDANCE_ANALYTICS:
        return jsonify({"error": "Analytics feature is disabled"}), 403
    
    student_id = user_data['student_id']
    semester_id = request.args.get('semester_id', type=int)
    
    conn = get_db_connection()
    
    # Get courses for the student (with optional semester filter)
    if semester_id:
        courses_cursor = conn.execute("""
            SELECT c.id as course_id, c.course_name, s.semester_name
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN semesters s ON c.semester_id = s.id
            WHERE e.student_id = ? AND c.semester_id = ?
        """, (student_id, semester_id)).fetchall()
    else:
        courses_cursor = conn.execute("""
            SELECT c.id as course_id, c.course_name, s.semester_name
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN semesters s ON c.semester_id = s.id
            WHERE e.student_id = ?
        """, (student_id,)).fetchall()
    
    analytics_data = {}
    
    for course in courses_cursor:
        course_id = course['course_id']
        course_name = course['course_name']
        semester_name = course['semester_name'] if course['semester_name'] else 'Other'
        
        # Get all sessions for this course ordered by start_time (newest first)
        sessions = conn.execute("""
            SELECT id, start_time
            FROM sessions
            WHERE course_id = ?
            ORDER BY start_time DESC
        """, (course_id,)).fetchall()
        
        # Calculate last 7 sessions average (last 7 actual sessions conducted)
        last_7_sessions = sessions[:ANALYTICS_LAST_DAYS]
        if last_7_sessions:
            last_7_session_ids = [s['id'] for s in last_7_sessions]
            last_7_present = conn.execute(f"""
                SELECT COUNT(*) as count FROM attendance_records
                WHERE student_id = ? AND session_id IN ({','.join(['?']*len(last_7_session_ids))})
            """, [student_id] + last_7_session_ids).fetchone()['count']
            last_7_days_avg = (last_7_present / len(last_7_sessions) * 100) if last_7_sessions else 0
        else:
            last_7_days_avg = 0
        
        # Calculate last 30 sessions average (last 30 actual sessions conducted)
        last_30_sessions = sessions[:ANALYTICS_TREND_DAYS]
        if last_30_sessions:
            last_30_session_ids = [s['id'] for s in last_30_sessions]
            last_30_present = conn.execute(f"""
                SELECT COUNT(*) as count FROM attendance_records
                WHERE student_id = ? AND session_id IN ({','.join(['?']*len(last_30_session_ids))})
            """, [student_id] + last_30_session_ids).fetchone()['count']
            last_30_days_avg = (last_30_present / len(last_30_sessions) * 100) if last_30_sessions else 0
        else:
            last_30_days_avg = 0
        
        # Calculate overall semester average
        total_present = 0
        if sessions:
            session_ids = [s['id'] for s in sessions]
            total_present = conn.execute(f"""
                SELECT COUNT(*) as count FROM attendance_records
                WHERE student_id = ? AND session_id IN ({','.join(['?']*len(session_ids))})
            """, [student_id] + session_ids).fetchone()['count']
            semester_total = (total_present / len(sessions) * 100) if sessions else 0
        else:
            semester_total = 0
        
        # Determine trend direction
        if last_7_days_avg > last_30_days_avg:
            trend_direction = 'up'
        elif last_7_days_avg < last_30_days_avg:
            trend_direction = 'down'
        else:
            trend_direction = 'stable'
        
        # Determine status
        if last_7_days_avg >= MINIMUM_ATTENDANCE_PERCENTAGE:
            status = 'good'
        elif last_7_days_avg >= ATTENDANCE_WARNING_THRESHOLD:
            status = 'warning'
        else:
            status = 'critical'
        
        # Get breakdown for the last 7 sessions (for charting)
        daily_breakdown = []
        # Reverse to get chronological order (oldest to newest of the last 7 sessions)
        last_7_sessions_chrono = list(reversed(last_7_sessions))
        for session in last_7_sessions_chrono:
            session_id = session['id']
            session_date = session['start_time'].split()[0]  # Extract date from datetime
            
            # Check if student was present in this session
            present = conn.execute("""
                SELECT COUNT(*) as count FROM attendance_records
                WHERE student_id = ? AND session_id = ?
            """, (student_id, session_id)).fetchone()['count']
            
            session_percentage = 100 if present > 0 else 0
            
            daily_breakdown.append({
                'date': session_date,
                'percentage': session_percentage,
                'session_id': session_id
            })
        
        # Get detailed status from analytics module
        status_data = analytics.calculate_status_and_improvement(
            total_present, 
            len(sessions),
            target_percent=MINIMUM_ATTENDANCE_PERCENTAGE,
            critical_percent=ATTENDANCE_WARNING_THRESHOLD
        )

        analytics_data[str(course_id)] = {
            'course_name': course_name,
            'semester_name': semester_name,
            'last_7_days_avg': round(last_7_days_avg, 1),
            'last_30_days_avg': round(last_30_days_avg, 1),
            'semester_total': round(semester_total, 1),
            'trend_direction': trend_direction,
            'status': status_data['status'].lower(),
            'improvement_plan': status_data,
            'daily_breakdown': daily_breakdown,
            'total_sessions': len(sessions)
        }
    
    conn.close()
    
    return jsonify({
        'analytics': analytics_data,
        'min_attendance_requirement': MINIMUM_ATTENDANCE_PERCENTAGE,
        'warning_threshold': ATTENDANCE_WARNING_THRESHOLD
    })

@app.route('/api/student/course/<int:course_id>', methods=['GET'])
@token_required
def get_course_details(user_data, course_id):
    student_id = user_data['student_id']
    conn = get_db_connection()
    course = conn.execute("SELECT course_name FROM courses WHERE id = ?", (course_id,)).fetchone()
    sessions = conn.execute("SELECT id, start_time, end_time FROM sessions WHERE course_id = ? ORDER BY start_time DESC", (course_id,)).fetchall()
    
    attendance_log = []
    present_count = 0
    for session in sessions:
        record = conn.execute("SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?", (session['id'], student_id)).fetchone()
        status = "Present" if record else "Absent"
        if record: present_count += 1
        attendance_log.append({"date": session['start_time'], "end_time": session['end_time'], "status": status})

    total_sessions = len(sessions)
    percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0
    conn.close()
    
    return jsonify({
        "course_name": course['course_name'], "present_count": present_count, "absent_count": total_sessions - present_count,
        "total_sessions": total_sessions, "percentage": round(percentage), "log": attendance_log
    })













# =================================================================
#   DEVICE API ENDPOINTS (For Live Status)
# =================================================================

# We will use a simple global variable to store the last heartbeat
# In a real multi-device system, this would be a dictionary or a database table
# =================================================================
#   DEVICE API ENDPOINTS (Enhanced with Timestamp Validation)
# =================================================================

# Global variable to store last heartbeat
last_device_heartbeat = {}

@app.route('/api/device/heartbeat', methods=['POST'])
def device_heartbeat():
    """
    Receives a status update from the Smart Scanner device.
    ✅ NEW: Adds server-side timestamp for freshness validation
    """
    global last_device_heartbeat
    data = request.get_json()
    
    # ✅ NEW: Add server timestamp when heartbeat is received
    data['server_timestamp'] = datetime.datetime.now().isoformat()
    
    last_device_heartbeat = data
    
    logger.info(f"Device heartbeat - Battery: {data.get('battery')}%, "
                f"Queue: {data.get('queue_count')}, Sync: {data.get('sync_count')}, "
                f"MAC: {data.get('mac_address')}")
    
    return jsonify({"status": "ok"})


@app.route('/api/teacher/device-status', methods=['GET'])
def get_device_status():
    """
    Provides the last known device status to the Teacher Dashboard.
    ✅ NEW: Validates timestamp freshness before returning data
    """
    global last_device_heartbeat
    
    # Check if we have any heartbeat data at all
    if not last_device_heartbeat or 'server_timestamp' not in last_device_heartbeat:
        return jsonify({
            "status": "offline",
            "message": "No heartbeat data available",
            "mac_address": None,
            "wifi_strength": None,
            "battery": None,
            "queue_count": None,
            "sync_count": None
        })
    
    # ✅ NEW: Check if heartbeat is fresh (within last 15 seconds)
    try:
        last_timestamp = datetime.datetime.fromisoformat(last_device_heartbeat['server_timestamp'])
        current_time = datetime.datetime.now()
        time_diff = (current_time - last_timestamp).total_seconds()
        
        # If heartbeat is older than 15 seconds, device is considered offline
        if time_diff > 15:
            logger.warning(f"Device heartbeat stale - Last seen {time_diff:.1f} seconds ago")
            return jsonify({
                "status": "offline",
                "message": f"Last heartbeat {int(time_diff)} seconds ago",
                "mac_address": last_device_heartbeat.get('mac_address'),
                "wifi_strength": None,
                "battery": last_device_heartbeat.get('battery'),  # Show last known battery
                "queue_count": last_device_heartbeat.get('queue_count'),
                "sync_count": last_device_heartbeat.get('sync_count'),
                "last_seen": int(time_diff)
            })
        
        # ✅ Heartbeat is fresh - device is online
        return jsonify({
            "status": "online",
            "mac_address": last_device_heartbeat.get('mac_address'),
            "wifi_strength": last_device_heartbeat.get('wifi_strength'),
            "battery": last_device_heartbeat.get('battery'),
            "queue_count": last_device_heartbeat.get('queue_count'),
            "sync_count": last_device_heartbeat.get('sync_count'),
            "last_seen": int(time_diff)
        })
        
    except Exception as e:
        logger.error(f"Error validating device status: {e}")
        return jsonify({
            "status": "error",
            "message": "Error checking device status"
        })


# =================================================================
#   DEVICE API ENDPOINTS (Fully Functional)
# =================================================================

# This endpoint is polled by the ESP32 device to know if it should
# be in 'ATTENDANCE_MODE' or 'AWAITING_SESSION' mode.
@app.route('/api/session-status', methods=['GET'])
def get_session_status():
    """Checks for an active session and returns its status and name."""
    conn = get_db_connection()
    # Find the most recent active session
    session_data = conn.execute("""
        SELECT s.id, c.course_code 
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        WHERE s.is_active = 1 
        ORDER BY s.start_time DESC 
        LIMIT 1
    """).fetchone()
    conn.close()

    if session_data:
        # If a session is active, send back its status and the course_code for display
        return jsonify({
            "isSessionActive": True,
            "sessionName": session_data['course_code']
        })
    else:
        # If no session is active, tell the device to remain idle
        return jsonify({
            "isSessionActive": False,
            "sessionName": ""
        })

# This is the main endpoint for the Smart Scanner to record attendance.
@app.route('/api/mark-attendance-by-roll-id', methods=['POST'])
def mark_attendance_by_roll_id():
    # [Keep all existing validation code...]
    data = request.get_json()
    class_roll_id = data.get('class_roll_id')
    logger.info(f"Attendance attempt - Roll ID: {class_roll_id}")
    
    conn = get_db_connection()
    active_session = conn.execute("SELECT id, course_id FROM sessions WHERE is_active = 1").fetchone()
    
    if not active_session:
        logger.warning(f"Attendance failed - No active session")
        conn.close()
        return jsonify({"status": "error", "message": "No Active Session"}), 400

    enrollment = conn.execute(
        "SELECT student_id FROM enrollments WHERE course_id = ? AND class_roll_id = ?",
        (active_session['course_id'], class_roll_id)
    ).fetchone()
    
    if not enrollment:
        logger.warning(f"Attendance failed - Roll ID {class_roll_id} not enrolled")
        conn.close()
        return jsonify({"status": "not_enrolled", "message": "Not Enrolled"})

    student_id = enrollment['student_id']

    existing_record = conn.execute(
        "SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?",
        (active_session['id'], student_id)
    ).fetchone()

    if existing_record:
        logger.info(f"Attendance duplicate - Roll ID {class_roll_id}")
        conn.close()
        return jsonify({"status": "duplicate", "message": "Already Marked"})
    
    # ✅ INSERT ATTENDANCE RECORD
    conn.execute(
        "INSERT INTO attendance_records (session_id, student_id, override_method) VALUES (?, ?, ?)",
        (active_session['id'], student_id, 'biometric')
    )
    conn.commit()
    
    conn.close()
    logger.info(f"Attendance marked - Roll ID {class_roll_id}")
    
    return jsonify({"status": "success", "message": "Marked"})

    


@app.route('/api/bulk-mark-attendance', methods=['POST'])
def bulk_mark_attendance():
    """
    ✅ NEW: Bulk attendance marking endpoint for queue sync
    
    Accepts an array of roll IDs and processes them all at once.
    Much faster than sequential processing.
    
    Request format:
    {
      "roll_ids": [42, 71, 15, 88, 102]
    }
    
    Response format:
    {
      "success_count": 4,
      "failed": [88],
      "details": {
        "42": "success",
        "71": "success", 
        "15": "success",
        "88": "not_enrolled",
        "102": "success"
      }
    }
    """
    try:
        data = request.get_json()
        roll_ids = data.get('roll_ids', [])
        
        if not roll_ids or not isinstance(roll_ids, list):
            logger.warning("Bulk sync failed - Invalid or empty roll_ids")
            return jsonify({"error": "No roll IDs provided or invalid format"}), 400
        
        logger.info(f"[BULK SYNC] Processing {len(roll_ids)} roll IDs: {roll_ids}")
        
        conn = get_db_connection()
        
        # Find active session
        active_session = conn.execute(
            "SELECT id, course_id FROM sessions WHERE is_active = 1"
        ).fetchone()
        
        if not active_session:
            conn.close()
            logger.warning("Bulk sync failed - No active session")
            return jsonify({
                "error": "No active session",
                "success_count": 0,
                "failed": roll_ids
            }), 400
        
        session_id = active_session['id']
        course_id = active_session['course_id']
        
        success_count = 0
        failed_ids = []
        details = {}
        
        # Process each roll ID
        for roll_id in roll_ids:
            try:
                # Validate roll_id is an integer
                roll_id = int(roll_id)
                
                # Check enrollment
                enrollment = conn.execute("""
                    SELECT student_id 
                    FROM enrollments 
                    WHERE course_id = ? AND class_roll_id = ?
                """, (course_id, roll_id)).fetchone()
                
                if not enrollment:
                    failed_ids.append(roll_id)
                    details[str(roll_id)] = "not_enrolled"
                    logger.warning(f"  [FAILED] Roll {roll_id} not enrolled in course {course_id}")
                    continue
                
                student_id = enrollment['student_id']
                
                # Check for duplicate
                existing = conn.execute("""
                    SELECT id FROM attendance_records 
                    WHERE session_id = ? AND student_id = ?
                """, (session_id, student_id)).fetchone()
                
                if existing:
                    # Already marked - consider it success (idempotent behavior)
                    success_count += 1
                    details[str(roll_id)] = "already_marked"
                    logger.info(f"  [SKIPPED] Roll {roll_id} already marked - skipping")
                    continue
                
                # Insert attendance record
                conn.execute("""
                    INSERT INTO attendance_records 
                    (session_id, student_id, override_method, timestamp) 
                    VALUES (?, ?, 'biometric_queue', CURRENT_TIMESTAMP)
                """, (session_id, student_id))
                
                # Log success
                logger.info(f"  [SUCCESS] Roll {roll_id} marked")
                
                success_count += 1
                details[str(roll_id)] = "success"
                
            except ValueError:
                failed_ids.append(roll_id)
                details[str(roll_id)] = "invalid_roll_id"
                logger.error(f"  [ERROR] Invalid roll ID format: {roll_id}")
            except Exception as e:
                failed_ids.append(roll_id)
                details[str(roll_id)] = f"error: {str(e)}"
                logger.error(f"  [ERROR] Error processing roll {roll_id}: {e}")
        
        # Commit all changes at once (transaction)
        conn.commit()
        conn.close()
        
        logger.info(f"[BULK SYNC] Complete - {success_count}/{len(roll_ids)} successful")
        if failed_ids:
            logger.warning(f"   Failed IDs: {failed_ids}")
        
        return jsonify({
            "success_count": success_count,
            "failed": failed_ids,
            "details": details
        }), 200
        
    except Exception as e:
        logger.error(f"Bulk sync exception: {e}", exc_info=True)
        return jsonify({
            "error": "Server error during bulk sync",
            "success_count": 0,
            "failed": roll_ids if 'roll_ids' in locals() else []
        }), 500




# --- Automatic Session Timeout ---
def auto_expire_sessions():
    """
    Background task that runs every 5 minutes.
    Closes sessions that have passed their scheduled end_time.
    This is a BACKUP - the frontend now triggers immediate expiry.
    """
    try:
        conn = get_db_connection()
        now = datetime.datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        
        # Find ACTIVE sessions that are past their end_time
        expired_sessions = conn.execute("""
            SELECT id, course_id, start_time, end_time 
            FROM sessions 
            WHERE is_active = 1 
            AND datetime(end_time) < datetime(?)
        """, (now_str,)).fetchall()
        
        if expired_sessions:
            # ONLY log if sessions were actually expired
            for session in expired_sessions:
                logger.warning(f"BACKUP Auto-close: Session {session['id']}, "
                             f"Course {session['course_id']}, "
                             f"End: {session['end_time']}")
            
            conn.execute("""
                UPDATE sessions 
                SET is_active = 0 
                WHERE is_active = 1 
                AND datetime(end_time) < datetime(?)
            """, (now_str,))
            conn.commit()
            
            logger.info(f"Auto-closed {len(expired_sessions)} session(s)")
        
        # REMOVED: "Auto-expire check running" log - too noisy
        conn.close()
    except Exception as e:
        logger.error(f"Error in auto_expire_sessions: {e}", exc_info=True)

# =================================================================
#   SCHEDULED EMAIL TASKS
# =================================================================

# Absent alerts scheduler removed




        

# Daily summaries removed



# Create and configure the background scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=auto_expire_sessions,
    trigger="interval",
    minutes=5,
    id='auto_expire_sessions',
    name='Auto-close expired sessions',
    replace_existing=True
)
# Email jobs removed


scheduler.start()

# Reduce scheduler's own logging verbosity (already configured above)
logger.info("Server started - Auto-expire scheduler active")  # Single startup message

# Ensure scheduler shuts down when app exits
atexit.register(lambda: scheduler.shutdown())




# =================================================================
#   Main Execution Block
# =================================================================# --- Leaderboard Helper Functions ---

def calculate_streaks(conn, student_id, course_id):
    """Calculate current and longest attendance streaks for a student in a course."""
    sessions = conn.execute("""
        SELECT s.id, s.start_time
        FROM sessions s
        WHERE s.course_id = ?
        ORDER BY s.start_time DESC
    """, (course_id,)).fetchall()
    
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    
    for session in sessions:
        record = conn.execute(
            "SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?",
            (session['id'], student_id)
        ).fetchone()
        
        if record:  # Present
            temp_streak += 1
            current_streak = temp_streak
        else:  # Absent
            longest_streak = max(longest_streak, temp_streak)
            temp_streak = 0
            if current_streak > 0:
                break  # Stop counting current streak at first absence
    
    longest_streak = max(longest_streak, temp_streak)
    
    return {
        'current_streak': current_streak,
        'longest_streak': longest_streak
    }

def generate_badges(attendance_pct, current_streak, longest_streak, conn, student_id, course_id):
    """Generate badges based on attendance and streak achievements."""
    badges = []
    
    # FIRST_STEP: First class attended
    first_attendance = conn.execute(
        "SELECT id FROM attendance_records WHERE student_id = ? LIMIT 1",
        (student_id,)
    ).fetchone()
    if first_attendance:
        badges.append({
            'type': 'FIRST_STEP',
            'icon': '🎯',
            'description': 'First class attended'
        })
    
    # CONSISTENT: 5+ current streak
    if current_streak >= 5:
        badges.append({
            'type': 'CONSISTENT',
            'icon': '🔥',
            'description': f'{current_streak} day streak'
        })
    
    # PERFECT_WEEK: 7-day streak
    if current_streak >= 7:
        badges.append({
            'type': 'PERFECT_WEEK',
            'icon': '⭐',
            'description': '7 day perfect streak'
        })
    
    # IRON_STREAK: 15+ day streak
    if longest_streak >= 15:
        badges.append({
            'type': 'IRON_STREAK',
            'icon': '💪',
            'description': '15+ day iron streak'
        })
    
    # PERFECT_MONTH: High attendance (90%+)
    if attendance_pct >= 90:
        badges.append({
            'type': 'PERFECT_MONTH',
            'icon': '👑',
            'description': '90%+ attendance'
        })
    
    return badges

import traceback

@app.route('/api/student/leaderboard', methods=['GET'])
@token_required
def get_leaderboard(user_data):
    """
    Returns attendance leaderboard with rankings, streaks, and gamification elements.
    Query Parameters:
        - course_id (optional): Filter by specific course
        - semester_id (optional): Filter by semester
        - limit (optional, default=50): Number of top students to return
    """
    try:
        student_id = user_data['student_id']
        course_id = request.args.get('course_id', type=int)
        semester_id = request.args.get('semester_id', type=int)
        limit = request.args.get('limit', default=50, type=int)
        logger.info(f"Leaderboard request - StudentID: {student_id}, CourseID: {course_id}, SemesterID: {semester_id}")
        
        conn = get_db_connection()
        
        # Build query to get all enrolled students with attendance data
        if course_id:
            # Get students enrolled in specific course
            students_query = """
                SELECT DISTINCT e.student_id, s.student_name
                FROM enrollments e
                JOIN students s ON e.student_id = s.id
                WHERE e.course_id = ?
            """
            params = [course_id]
            query_type = 'course'
        elif semester_id:
            # Get students in specific semester
            # FIX: Join with courses table since enrollments table doesn't have semester_id
            students_query = """
                SELECT DISTINCT e.student_id, s.student_name
                FROM enrollments e
                JOIN students s ON e.student_id = s.id
                JOIN courses c ON e.course_id = c.id
                WHERE c.semester_id = ?
            """
            params = [semester_id]
            query_type = 'semester'
        else:
            # Get all students (global leaderboard)
            students_query = "SELECT id as student_id, student_name FROM students"
            params = []
            query_type = 'global'
        
        students = conn.execute(students_query, params).fetchall()
        
        # Pre-fetch context data (courses and sessions) to avoid N+1 queries
        target_course_ids = []
        target_session_ids = []
        
        if query_type == 'course':
            target_course_ids = [course_id]
            sessions = conn.execute("SELECT id FROM sessions WHERE course_id = ?", (course_id,)).fetchall()
            target_session_ids = [s['id'] for s in sessions]
            
        elif query_type == 'semester':
            # Get all courses in this semester
            courses_in_semester = conn.execute(
                "SELECT id FROM courses WHERE semester_id = ?",
                (semester_id,)
            ).fetchall()
            target_course_ids = [c['id'] for c in courses_in_semester]
            
            if target_course_ids:
                placeholders = ','.join(['?'] * len(target_course_ids))
                sessions = conn.execute(
                    f"SELECT id FROM sessions WHERE course_id IN ({placeholders})",
                    target_course_ids
                ).fetchall()
                target_session_ids = [s['id'] for s in sessions]
            else:
                target_session_ids = []
                
        else: # global
            sessions = conn.execute("SELECT id FROM sessions").fetchall()
            target_session_ids = [s['id'] for s in sessions]

        leaderboard_data = []
        user_rank_info = None
        user_stats = None
        user_badges = []
        
        # Optimization: If we have no sessions to check against (e.g. empty semester), 
        # we can skip detailed calculation or handle gracefully
        
        for student in students:
            sid = student['student_id']
            
            # Skip students in semester view if there are no courses/sessions
            if query_type == 'semester' and not target_course_ids:
                continue

            total_sessions = len(target_session_ids)
            
            if total_sessions > 0:
                # Chunking session_ids to avoid SQLite limit (999 variables) if necessary
                # But for now assuming session count isn't massive. 
                # If massive, we should change logic to count using JOINs instead of IN clause.
                
                if len(target_session_ids) > 900:
                    # Fallback for large datasets: use a loop or better query
                    # For safety/simplicity in this fix, we'll slice it or just log warning
                    # Better approach:
                    # SELECT COUNT(*) FROM attendance_records WHERE student_id=? AND session_id IN (...)
                    pass 

                present_count = conn.execute(
                    f"SELECT COUNT(id) as count FROM attendance_records WHERE student_id = ? AND session_id IN ({','.join(['?']*len(target_session_ids))})",
                    [sid] + target_session_ids
                ).fetchone()['count']
            else:
                present_count = 0
            
            attendance_pct = (present_count / total_sessions * 100) if total_sessions > 0 else 0
            
            # Calculate streaks
            if query_type == 'course' and course_id:
                streaks = calculate_streaks(conn, sid, course_id)
            elif query_type == 'semester' and target_course_ids:
                # For semester view, use first course's streaks (Legacy logic maintained)
                streaks = calculate_streaks(conn, sid, target_course_ids[0])
            else:
                # For global, use any course
                any_course = conn.execute("SELECT id FROM courses LIMIT 1").fetchone()
                streaks = calculate_streaks(conn, sid, any_course['id']) if any_course else {'current_streak': 0, 'longest_streak': 0}
            
            # Generate badges
            badge_course_id = course_id or (target_course_ids[0] if target_course_ids else 1)
            badges = generate_badges(attendance_pct, streaks['current_streak'], streaks['longest_streak'], conn, sid, badge_course_id)
            
            # Add to leaderboard
            leaderboard_data.append({
                'student_id': sid,
                'student_name': student['student_name'],
                'attendance_percentage': round(attendance_pct, 1),
                'present_count': present_count,
                'total_sessions': total_sessions,
                'current_streak': streaks['current_streak'],
                'longest_streak': streaks['longest_streak'],
                'badges': badges
            })
            
            # Store user's data for later
            if sid == student_id:
                user_stats = {
                    'attendance_percentage': round(attendance_pct, 1),
                    'current_streak': streaks['current_streak'],
                    'longest_streak': streaks['longest_streak'],
                    'present_count': present_count,
                    'total_sessions': total_sessions
                }
                user_badges = badges
        
        # Sort by: attendance % DESC, then streak DESC, then present count DESC
        leaderboard_data.sort(key=lambda x: (-x['attendance_percentage'], -x['current_streak'], -x['present_count']))
        
        # Assign ranks and find user's rank
        for idx, entry in enumerate(leaderboard_data):
            entry['rank'] = idx + 1
            if entry['student_id'] == student_id:
                user_rank_info = {
                    'rank': idx + 1,
                    'position': idx + 1,
                    'percentile': round((idx / len(leaderboard_data) * 100)) if leaderboard_data else 0,
                    'total_students': len(leaderboard_data)
                }
        
        # Trim to limit
        leaderboard_display = leaderboard_data[:limit]
        
        conn.close()
        
        return jsonify({
            'user_rank': user_rank_info or {'rank': 0, 'position': 0, 'percentile': 0, 'total_students': 0},
            'user_stats': user_stats or {'attendance_percentage': 0, 'current_streak': 0, 'longest_streak': 0, 'present_count': 0, 'total_sessions': 0},
            'user_badges': user_badges,
            'leaderboard': leaderboard_display,
            'total_on_leaderboard': len(leaderboard_data),
            'course_id': course_id,
            'semester_id': semester_id
        })
    except Exception as e:
        logger.error(f"Error in get_leaderboard: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'message': 'Internal Server Error', 'error': str(e)}), 500


# =================================================================
#   Server Startup
# =================================================================

if __name__ == '__main__':
    # Start auto-sync if configured (local server only)
    if not Config.IS_CLOUD_SERVER and Config.CLOUD_SERVER_URL and Config.SYNC_INTERVAL_SECONDS > 0:
        sync.start_auto_sync(Config.SYNC_INTERVAL_SECONDS)
        logger.info(f"[SYNC] Auto-sync enabled: every {Config.SYNC_INTERVAL_SECONDS}s to {Config.CLOUD_SERVER_URL}")
    
    # host='0.0.0.0' makes the server accessible from other devices on your network
    app.run(host=Config.HOST, port=Config.PORT, debug=False, use_reloader=False, request_handler=TimedRequestHandler)
