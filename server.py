# =================================================================
#   A.R.I.S.E. Server
# =================================================================



from flask import Flask, jsonify, request, render_template
import sqlite3
import datetime
import jwt
import hashlib
from functools import wraps

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import io
from flask import send_file

import logging
from apscheduler.schedulers.background import BackgroundScheduler
import atexit


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



from email_service import (
    send_instant_present_alert,
    send_absent_alert,
    send_daily_summary
)
from config import (
    ENABLE_INSTANT_ALERTS, 
    ENABLE_ABSENT_ALERTS,
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

# --- Configure logging with filters ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',  # Removed %(name)s for cleaner output
    handlers=[
        logging.FileHandler('arise_server.log'),
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
# IMPORTANT: In a real production app, this should be a long, random, secret key
# stored securely as an environment variable, not in the code.
app.config['SECRET_KEY'] = 'a-very-long-and-super-secret-key-for-sih2025'

# --- Database & Token Helper Functions ---

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    # check_same_thread=False is needed because Flask can handle requests in different threads.
    conn = sqlite3.connect('attendance.db', check_same_thread=False)
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









# =================================================================
#   ADMIN API ENDPOINTS (Part 1)
# =================================================================

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """Handles the administrator's login request."""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "Username and password are required"}), 400

    hashed_password = hashlib.sha256(data['password'].encode('utf-8')).hexdigest()
    conn = get_db_connection()
    admin = conn.execute("SELECT id FROM admins WHERE username = ? AND password = ?", 
                           (data['username'], hashed_password)).fetchone()
    conn.close()
    
    if admin:
        # If login is successful, create a token that expires in 8 hours
        token = jwt.encode({
            'admin_id': admin['id'], 
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({'token': token})
    
    return jsonify({"message": "Invalid credentials"}), 401

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
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM semesters WHERE id = ?", (id,))
        conn.commit()
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
                     (data['teacher_name'], data['pin']))
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
             conn.execute("UPDATE teachers SET teacher_name = ?, pin = ? WHERE id = ?", (data['teacher_name'], data['pin'], id))
        else:
             conn.execute("UPDATE teachers SET teacher_name = ? WHERE id = ?", (data['teacher_name'], id))
        conn.commit()
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM teachers WHERE id = ?", (id,))
        conn.commit()
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
        
        hashed_password = hashlib.sha256(data['password'].encode('utf-8')).hexdigest()
        
        try:
            conn.execute("""INSERT INTO students 
                (student_name, university_roll_no, enrollment_no, email1, email2, password) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (data['student_name'], data['university_roll_no'], 
                 data['enrollment_no'], data['email1'], 
                 data.get('email2', ''), hashed_password))
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
            hashed_password = hashlib.sha256(data['password'].encode('utf-8')).hexdigest()
            conn.execute("""UPDATE students SET student_name = ?, university_roll_no = ?, 
                            enrollment_no = ?, email1 = ?, email2 = ?, password = ? WHERE id = ?""",
                         (data['student_name'], data['university_roll_no'], data['enrollment_no'], data['email1'], data['email2'], hashed_password, id))
        else: # Update without changing the password
            conn.execute("""UPDATE students SET student_name = ?, university_roll_no = ?, 
                            enrollment_no = ?, email1 = ?, email2 = ? WHERE id = ?""",
                         (data['student_name'], data['university_roll_no'], data['enrollment_no'], data['email1'], data['email2'], id))
        conn.commit()
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM students WHERE id = ?", (id,))
        conn.commit()
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
    elif request.method == 'DELETE':
        conn.execute("DELETE FROM courses WHERE id = ?", (id,))
        conn.commit()
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
        except Exception as e:
            conn.rollback()
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
#   TEACHER API ENDPOINTS (Fully Functional)
# =================================================================

#This cod eis fo rgetting the course code and sending it to teacher.js login part to show COURSECODE FIELD in dropdown in the login page of teacher interface 
@app.route('/api/teacher/course-codes', methods=['GET'])
def get_course_codes():
    """Returns all course codes for the teacher login dropdown."""
    conn = get_db_connection()
    course_codes = [row['course_code'] for row in conn.execute("SELECT course_code FROM courses ORDER BY course_code").fetchall()]
    conn.close()
    return jsonify(course_codes)


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
    
    if not teacher or teacher['pin'] != pin:
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
    
    logger.info(f"Creating session - Duration: {duration_minutes}min, Grace: {grace_period_minutes}min, "
                f"Start: {start_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"Scheduled end: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create new session
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO sessions 
           (course_id, start_time, end_time, is_active, session_type) 
           VALUES (?, ?, ?, 1, ?)""",
        (data['course_id'], 
         start_time.strftime('%Y-%m-%d %H:%M:%S'),
         end_time.strftime('%Y-%m-%d %H:%M:%S'),
         data['session_type'])
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


        try:
            student_data = conn.execute(
                "SELECT student_name, email1 FROM students WHERE university_roll_no = ?",
                (univ_roll_no,)
            ).fetchone()
            
            course_data = conn.execute(
                "SELECT c.course_name FROM courses c JOIN sessions s ON c.id = s.course_id WHERE s.id = ?",
                (session_id,)
            ).fetchone()
            
            if student_data and student_data['email1'] and course_data:
                timestamp = datetime.datetime.now().isoformat()
                send_instant_present_alert(
                    student_data['student_name'],
                    student_data['email1'],
                    course_data['course_name'],
                    timestamp
                )
                logger.info(f"📧 Manual override email sent to {student_data['email1']}")
        except Exception as e:
            logger.error(f"📧 Manual override email error: {e}")



        conn.close()
        
        # Log success
        logger.info(f"Manual override SUCCESS - Student: {student['student_name']} ({univ_roll_no}), "
                    f"Session: {session['id']}, Course: {session['course_id']}, Reason: '{reason}'")
        
        return jsonify({"status": "success", "message": "Attendance marked manually"})
    
    except Exception as e:
        # Catch any unexpected errors and log them
        logger.error(f"Manual override EXCEPTION: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error occurred"}), 500
    




# =================================================================
#   TEACHER API ENDPOINTS (Session Management)
# =================================================================

@app.route('/api/teacher/session/<int:session_id>/end', methods=['POST'])
def end_session(session_id):
    """
    Ends the currently active session AND sends absent alerts.
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
        
        # STEP 2: Get course name for email
        course = conn.execute(
            "SELECT course_name FROM courses WHERE id = ?",
            (course_id,)
        ).fetchone()
        
        if not course:
            logger.warning(f"Course {course_id} not found for session {session_id}")
            conn.close()
            return jsonify({"status": "error", "message": "Course not found"}), 404
        
        course_name = course['course_name']
        date_str = datetime.datetime.fromisoformat(session['start_time']).strftime("%d %B %Y")
        
        # STEP 3: Get ALL enrolled students in this course
        enrolled_students = conn.execute("""
            SELECT s.id, s.student_name, s.email1, s.email2 
            FROM students s
            JOIN enrollments e ON s.id = e.student_id
            WHERE e.course_id = ?
        """, (course_id,)).fetchall()
        
        logger.info(f"End session {session_id}: Found {len(enrolled_students)} enrolled students")
        
        # STEP 4: Get students who ATTENDED this session
        attended = conn.execute("""
            SELECT DISTINCT student_id 
            FROM attendance_records 
            WHERE session_id = ?
        """, (session_id,)).fetchall()
        
        attended_ids = set(row['student_id'] for row in attended)
        logger.info(f"End session {session_id}: {len(attended_ids)} students marked present")
        
        # STEP 5: Send absent alerts to students NOT in attended_ids
        absent_count = 0
        for student in enrolled_students:
            student_id = student['id']
            student_name = student['student_name']
            email1 = student['email1']
            email2 = student['email2']
            
            # Check if this student was ABSENT (NOT in attended_ids)
            if student_id not in attended_ids:
                logger.info(f"  Absent: {student_name} - Email: {email1}")
                
                # Send to primary email if exists
                if email1:
                    try:
                        success, error = send_absent_alert(
                            student_name,
                            email1,
                            course_name,
                            date_str
                        )
                        if success:
                            logger.info(f"    SENT to {email1}")
                            absent_count += 1
                        else:
                            logger.warning(f"    FAILED to {email1}: {error}")
                    except Exception as e:
                        logger.error(f"    ERROR sending to {email1}: {e}")
                
                # Send to secondary email if exists
                if email2:
                    try:
                        success, error = send_absent_alert(
                            student_name,
                            email2,
                            course_name,
                            date_str
                        )
                        if success:
                            logger.info(f"    SENT to secondary {email2}")
                    except Exception as e:
                        logger.error(f"    ERROR sending to secondary {email2}: {e}")
        
        # STEP 6: NOW close the session in database
        conn.execute(
            "UPDATE sessions SET is_active = 0, end_time = ? WHERE id = ?",
            (now, session_id)
        )
        conn.commit()
        
        logger.info(f"Session ended - ID: {session_id}, Absent alerts sent: {absent_count}")
        
        conn.close()
        return jsonify({
            "status": "success", 
            "message": f"Session ended. Absent alerts sent to {absent_count} students."
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
        return jsonify({"session_active": False, "marked_students": []}), 404
    
    is_active = bool(session['is_active'])
    
    # Get marked students
    records_cursor = conn.execute("""
        SELECT s.university_roll_no
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.id
        WHERE ar.session_id = ?
    """, (session_id,)).fetchall()
    
    marked_students = [row['university_roll_no'] for row in records_cursor]
    conn.close()
    
    return jsonify({
        "session_active": is_active,  # CRITICAL: Frontend needs this
        "marked_students": marked_students
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
        conn.close()
        return jsonify({"error": "Session not found"}), 404
    course_id = course['course_id']

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
    records_cursor = conn.execute(f"""
        SELECT session_id, student_id FROM attendance_records
        WHERE session_id IN ({placeholders})
    """, session_ids).fetchall()
    
    # Create a fast lookup set for presence check: (session_id, student_id)
    present_set = set((rec['session_id'], rec['student_id']) for rec in records_cursor)
    
    conn.close()

    # Structure the data for the frontend
    report_data = {
        "students": students,
        "sessions": sessions,
        "present_set": list(present_set) # Convert set to list for JSON
    }
    
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
    students = [dict(row) for row in conn.execute("SELECT s.id, s.student_name, s.university_roll_no, s.enrollment_no, e.class_roll_id FROM students s JOIN enrollments e ON s.id = e.student_id WHERE e.course_id = ? ORDER BY e.class_roll_id", (course_id,)).fetchall()]
    sessions = [dict(row) for row in conn.execute(
        "SELECT id, start_time FROM sessions WHERE course_id = ? ORDER BY start_time",
        (course_id,)
    ).fetchall()]
    session_ids = [s['id'] for s in sessions]
    present_set = set()
    if session_ids:
        placeholders = ','.join('?' for _ in session_ids)
        records_cursor = conn.execute(f"SELECT session_id, student_id FROM attendance_records WHERE session_id IN ({placeholders})", session_ids).fetchall()
        present_set = set((rec['session_id'], rec['student_id']) for rec in records_cursor)
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

    return send_file(
        in_memory_file,
        as_attachment=True,
        download_name=f"Attendance_Report_{course['course_name']}_{datetime.date.today()}.xlsx",
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


# END OF PART 2








# START OF PART 3








# =================================================================
#   STUDENT API ENDPOINTS
# =================================================================
# In our Admin-first build, these will be simple placeholders.

@app.route('/api/student/login', methods=['POST'])
def student_login():
    data = request.get_json()
    univ_roll_no = data.get('university_roll_no'); password = data.get('password')
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    conn = get_db_connection()
    student = conn.execute("SELECT id, student_name FROM students WHERE university_roll_no = ? AND password = ?", (univ_roll_no, hashed_password)).fetchone()
    conn.close()
    if student:
        token = jwt.encode({'student_id': student['id'], 'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)}, app.config['SECRET_KEY'], algorithm="HS256")
        return jsonify({'token': token, 'student_name': student['student_name']})
    return jsonify({"message": "Invalid credentials"}), 401

@app.route('/api/student/semesters', methods=['GET'])
@token_required
def get_student_semesters(user_data):
    """Returns all semesters and courses that the student is enrolled in."""
    student_id = user_data['student_id']
    conn = get_db_connection()
    
    # Get semesters
    semesters_cursor = conn.execute("""
        SELECT DISTINCT s.id, s.semester_name
        FROM semesters s
        JOIN courses c ON s.id = c.semester_id
        JOIN enrollments e ON c.id = e.course_id
        WHERE e.student_id = ?
        ORDER BY s.id
    """, (student_id,)).fetchall()
    
    semesters = [dict(row) for row in semesters_cursor]
    
    # For each semester, get the courses
    for semester in semesters:
        courses_cursor = conn.execute("""
            SELECT DISTINCT c.id, c.course_name, c.course_code
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            WHERE c.semester_id = ? AND e.student_id = ?
            ORDER BY c.course_name
        """, (semester['id'], student_id)).fetchall()
        
        semester['courses'] = [dict(row) for row in courses_cursor]
    
    conn.close()
    return jsonify(semesters)

@app.route('/api/student/dashboard', methods=['GET'])
@token_required
def get_student_dashboard(user_data):
    student_id = user_data['student_id']
    semester_id = request.args.get('semester_id', type=int)  # Optional query parameter
    
    conn = get_db_connection()
    
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
            "percentage": round(percentage), 
            "present_count": present_count, 
            "absent_count": total_sessions - present_count, 
            "total_sessions": total_sessions,
            "warning_status": warning_status
        })
        
    conn.close()
    overall_percentage = (total_present_overall / total_sessions_overall * 100) if total_sessions_overall > 0 else 0
    
    return jsonify({
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
        else:
            present_count = 0
        
        percentage = (present_count / total_sessions * 100) if total_sessions > 0 else 0
        
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
            SELECT c.id as course_id, c.course_name
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.student_id = ? AND c.semester_id = ?
        """, (student_id, semester_id)).fetchall()
    else:
        courses_cursor = conn.execute("""
            SELECT c.id as course_id, c.course_name
            FROM courses c
            JOIN enrollments e ON c.id = e.course_id
            WHERE e.student_id = ?
        """, (student_id,)).fetchall()
    
    analytics_data = {}
    
    for course in courses_cursor:
        course_id = course['course_id']
        course_name = course['course_name']
        
        # Get all sessions for this course
        sessions = conn.execute("""
            SELECT id, start_time
            FROM sessions
            WHERE course_id = ?
            ORDER BY start_time
        """, (course_id,)).fetchall()
        
        # Calculate last 7 days average
        seven_days_ago = datetime.datetime.now() - datetime.timedelta(days=ANALYTICS_LAST_DAYS)
        seven_days_ago_str = seven_days_ago.strftime('%Y-%m-%d %H:%M:%S')
        
        recent_sessions = [s for s in sessions if s['start_time'] > seven_days_ago_str]
        if recent_sessions:
            recent_session_ids = [s['id'] for s in recent_sessions]
            recent_present = conn.execute(f"""
                SELECT COUNT(*) as count FROM attendance_records
                WHERE student_id = ? AND session_id IN ({','.join(['?']*len(recent_session_ids))})
            """, [student_id] + recent_session_ids).fetchone()['count']
            last_7_days_avg = (recent_present / len(recent_sessions) * 100) if recent_sessions else 0
        else:
            last_7_days_avg = 0
        
        # Calculate last 30 days average
        thirty_days_ago = datetime.datetime.now() - datetime.timedelta(days=ANALYTICS_TREND_DAYS)
        thirty_days_ago_str = thirty_days_ago.strftime('%Y-%m-%d %H:%M:%S')
        
        thirty_days_sessions = [s for s in sessions if s['start_time'] > thirty_days_ago_str]
        if thirty_days_sessions:
            thirty_session_ids = [s['id'] for s in thirty_days_sessions]
            thirty_present = conn.execute(f"""
                SELECT COUNT(*) as count FROM attendance_records
                WHERE student_id = ? AND session_id IN ({','.join(['?']*len(thirty_session_ids))})
            """, [student_id] + thirty_session_ids).fetchone()['count']
            last_30_days_avg = (thirty_present / len(thirty_days_sessions) * 100) if thirty_days_sessions else 0
        else:
            last_30_days_avg = 0
        
        # Calculate overall semester average
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
        
        # Get daily breakdown for the last 7 days (for charting)
        daily_breakdown = []
        for i in range(ANALYTICS_LAST_DAYS):
            date = (datetime.datetime.now() - datetime.timedelta(days=ANALYTICS_LAST_DAYS - i - 1)).date()
            date_str = date.strftime('%Y-%m-%d')
            
            day_sessions = [s for s in sessions if s['start_time'].startswith(date_str)]
            if day_sessions:
                day_session_ids = [s['id'] for s in day_sessions]
                day_present = conn.execute(f"""
                    SELECT COUNT(*) as count FROM attendance_records
                    WHERE student_id = ? AND session_id IN ({','.join(['?']*len(day_session_ids))})
                """, [student_id] + day_session_ids).fetchone()['count']
                day_percentage = (day_present / len(day_sessions) * 100)
            else:
                day_percentage = None
            
            daily_breakdown.append({
                'date': date_str,
                'percentage': day_percentage
            })
        
        analytics_data[str(course_id)] = {
            'course_name': course_name,
            'last_7_days_avg': round(last_7_days_avg, 1),
            'last_30_days_avg': round(last_30_days_avg, 1),
            'semester_total': round(semester_total, 1),
            'trend_direction': trend_direction,
            'status': status,
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
    
    # Optional: Log heartbeat for debugging
    # logger.debug(f"Heartbeat received - Battery: {data.get('battery')}%, Queue: {data.get('queue_count')}")
    
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
    
    # ✅✅✅ NEW: SEND INSTANT EMAIL ALERT ✅✅✅
    try:
        # Get student details
        student = conn.execute(
            "SELECT student_name, email1 FROM students WHERE id = ?",
            (student_id,)
        ).fetchone()
        
        # Get course name
        course = conn.execute(
            "SELECT course_name FROM courses WHERE id = ?",
            (active_session['course_id'],)
        ).fetchone()
        
        # Send email if parent email exists
        if student and student['email1'] and course:
            timestamp = datetime.datetime.now().isoformat()
            success, error = send_instant_present_alert(
                student['student_name'],
                student['email1'],
                course['course_name'],
                timestamp
            )
            
            if success:
                logger.info(f"Email sent to parent: {student['email1']}")
            else:
                logger.warning(f"Email failed: {error}")
    
    except Exception as e:
        # Don't fail attendance marking if email fails
        logger.error(f"Email alert error: {e}")
    
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
        
        logger.info(f"📦 Bulk sync request - {len(roll_ids)} roll IDs: {roll_ids}")
        
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
                    logger.warning(f"  ❌ Roll {roll_id} not enrolled in course {course_id}")
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
                    logger.info(f"  ⚠️  Roll {roll_id} already marked - skipping")
                    continue
                
                # Insert attendance record
                conn.execute("""
                    INSERT INTO attendance_records 
                    (session_id, student_id, override_method, timestamp) 
                    VALUES (?, ?, 'biometric_queue', CURRENT_TIMESTAMP)
                """, (session_id, student_id))
                
                success_count += 1
                details[str(roll_id)] = "success"
                logger.info(f"  ✅ Roll {roll_id} marked successfully")
                
            except ValueError:
                failed_ids.append(roll_id)
                details[str(roll_id)] = "invalid_roll_id"
                logger.error(f"  ❌ Invalid roll ID format: {roll_id}")
            except Exception as e:
                failed_ids.append(roll_id)
                details[str(roll_id)] = f"error: {str(e)}"
                logger.error(f"  ❌ Error processing roll {roll_id}: {e}")
        
        # Commit all changes at once (transaction)
        conn.commit()
        conn.close()
        
        logger.info(f"📦 Bulk sync complete - {success_count}/{len(roll_ids)} successful")
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

def send_absent_alerts_for_ended_sessions():
    """
    Background check (runs every 10 minutes).
    Now only handles edge cases where alerts weren't sent during end_session.
    """
    try:
        conn = get_db_connection()
        now = datetime.datetime.now()
        
        # Only check sessions that ended 2-5 minutes ago (avoid duplicates)
        five_min_ago = (now - datetime.timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
        two_min_ago = (now - datetime.timedelta(minutes=2)).strftime('%Y-%m-%d %H:%M:%S')
        
        ended_sessions = conn.execute("""
            SELECT id, course_id, end_time 
            FROM sessions 
            WHERE is_active = 0 
            AND end_time IS NOT NULL
            AND datetime(end_time) BETWEEN datetime(?) AND datetime(?)
        """, (five_min_ago, two_min_ago)).fetchall()
        
        if not ended_sessions:
            conn.close()
            return
        
        logger.info(f"Scheduler: Checking {len(ended_sessions)} recently ended sessions for missed alerts")
        
        for session in ended_sessions:
            session_id = session['id']
            course_id = session['course_id']
            
            course = conn.execute(
                "SELECT course_name FROM courses WHERE id = ?",
                (course_id,)
            ).fetchone()
            
            if not course:
                continue
            
            course_name = course['course_name']
            
            enrolled = conn.execute("""
                SELECT s.id, s.student_name, s.email1
                FROM students s 
                JOIN enrollments e ON s.id = e.student_id 
                WHERE e.course_id = ?
            """, (course_id,)).fetchall()
            
            attended = conn.execute("""
                SELECT DISTINCT student_id FROM attendance_records WHERE session_id = ?
            """, (session_id,)).fetchall()
            
            attended_ids = set(row['student_id'] for row in attended)
            
            for student in enrolled:
                if student['id'] not in attended_ids and student['email1']:
                    try:
                        date_str = datetime.datetime.fromisoformat(
                            session['end_time']
                        ).strftime("%d %B %Y")
                        
                        send_absent_alert(
                            student['student_name'],
                            student['email1'],
                            course_name,
                            date_str
                        )
                        logger.info(f"Scheduler: Sent absent alert to {student['student_name']}")
                    except Exception as e:
                        logger.error(f"Scheduler: Error sending alert: {e}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in scheduler absent alerts: {e}")



        

def send_daily_summaries_5pm():
    # Send comprehensive daily summary at 5 PM
    
    try:
        conn = get_db_connection()
        today = datetime.date.today()
        today_str = today.strftime("%d %B %Y")
        
        logger.info("📧 Starting 5 PM daily summary email job")
        
        # Get all students
        students = conn.execute("SELECT id, student_name, email1 FROM students").fetchall()
        
        summary_count = 0
        
        for student in students:
            if not student['email1']:
                continue
            
            # Get today's sessions for this student's courses
            today_sessions = conn.execute(
                "SELECT s.id, c.course_name, s.start_time FROM sessions s JOIN courses c ON s.course_id = c.id JOIN enrollments e ON c.id = e.course_id WHERE e.student_id = ? AND DATE(s.start_time) = ?",
                (student['id'], today)
            ).fetchall()
            
            if not today_sessions:
                continue  # No classes today, skip
            
            # Build course list
            courses_today = []
            present_count = 0
            absent_count = 0
            
            for session in today_sessions:
                # Check if student attended
                attended = conn.execute(
                    "SELECT id FROM attendance_records WHERE session_id = ? AND student_id = ?",
                    (session['id'], student['id'])
                ).fetchone()
                
                status = "Present" if attended else "Absent"
                time_str = datetime.datetime.fromisoformat(session['start_time']).strftime("%I:%M %p")
                
                courses_today.append({
                    'name': session['course_name'],
                    'status': status,
                    'time': time_str
                })
                
                if status == "Present":
                    present_count += 1
                else:
                    absent_count += 1
            
            # Calculate overall attendance percentage
            total_sessions = conn.execute(
                "SELECT COUNT(*) as total FROM sessions s JOIN enrollments e ON s.course_id = e.course_id WHERE e.student_id = ?",
                (student['id'],)
            ).fetchone()
            
            attended_total = conn.execute(
                "SELECT COUNT(*) as attended FROM attendance_records WHERE student_id = ?",
                (student['id'],)
            ).fetchone()
            
            total_classes = total_sessions['total']
            attended_classes = attended_total['attended']
            
            if total_classes > 0:
                overall_percentage = round((attended_classes / total_classes) * 100, 1)
            else:
                overall_percentage = 0.0
            
            # Build summary data
            summary_data = {
                'date': today_str,
                'present_today': present_count,
                'absent_today': absent_count,
                'total_today': len(courses_today),
                'courses_today': courses_today,
                'overall_percentage': overall_percentage,
                'total_classes': total_classes,
                'attended_classes': attended_classes
            }
            
            # Send email
            try:
                success, error = send_daily_summary(
                    student['student_name'],
                    student['email1'],
                    summary_data
                )
                if success:
                    summary_count += 1
            except Exception as e:
                logger.error(f"📧 Daily summary failed for {student['student_name']}: {e}")
        
        conn.close()
        logger.info(f"📧 Sent {summary_count} daily summary emails")
        
    except Exception as e:
        logger.error(f"Error in daily summary scheduler: {e}")


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
# Job 1: Send absent alerts every 10 minutes
scheduler.add_job(
    func=send_absent_alerts_for_ended_sessions,
    trigger="interval",
    minutes=10,
    id='absent_alerts',
    name='Send absent alerts',
    replace_existing=True
)

# Job 2: Send daily summaries at 5:00 PM
scheduler.add_job(
    func=send_daily_summaries_5pm,
    trigger="cron",
    hour=17,
    minute=0,
    id='daily_summaries',
    name='Send 5 PM daily summaries',
    replace_existing=True
)

logger.info("Email alert scheduler initialized - Absent alerts every 10min, Daily summaries at 5 PM")

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
    student_id = user_data['student_id']
    course_id = request.args.get('course_id', type=int)
    semester_id = request.args.get('semester_id', type=int)
    limit = request.args.get('limit', default=50, type=int)
    
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
    elif semester_id:
        # Get students in specific semester
        students_query = """
            SELECT DISTINCT e.student_id, s.student_name
            FROM enrollments e
            JOIN students s ON e.student_id = s.id
            WHERE e.semester_id = ?
        """
        params = [semester_id]
    else:
        # Get all students (global leaderboard)
        students_query = "SELECT id as student_id, student_name FROM students"
        params = []
    
    students = conn.execute(students_query, params).fetchall()
    
    leaderboard_data = []
    user_rank_info = None
    user_stats = None
    user_badges = []
    
    for student in students:
        sid = student['student_id']
        
        # Initialize course_ids as None
        course_ids = None
        
        # Get course enrollment for this student
        if course_id:
            course_filter = course_id
            query_type = 'course'
        elif semester_id:
            # Get courses in this semester
            courses_in_semester = conn.execute(
                "SELECT id FROM courses WHERE semester_id = ?",
                (semester_id,)
            ).fetchall()
            course_ids = [c['id'] for c in courses_in_semester]
            query_type = 'semester'
        else:
            query_type = 'global'
        
        # Calculate attendance percentage
        if query_type == 'course':
            sessions = conn.execute(
                "SELECT id FROM sessions WHERE course_id = ?",
                (course_filter,)
            ).fetchall()
        elif query_type == 'semester':
            if not course_ids:
                continue
            placeholders = ','.join(['?'] * len(course_ids))
            sessions = conn.execute(
                f"SELECT id FROM sessions WHERE course_id IN ({placeholders})",
                course_ids
            ).fetchall()
        else:
            sessions = conn.execute("SELECT id FROM sessions").fetchall()
        
        session_ids = [s['id'] for s in sessions]
        total_sessions = len(session_ids)
        
        if total_sessions > 0:
            present_count = conn.execute(
                f"SELECT COUNT(id) as count FROM attendance_records WHERE student_id = ? AND session_id IN ({','.join(['?']*len(session_ids))})",
                [sid] + session_ids
            ).fetchone()['count']
        else:
            present_count = 0
        
        attendance_pct = (present_count / total_sessions * 100) if total_sessions > 0 else 0
        
        # Calculate streaks
        if query_type == 'course' and course_id:
            streaks = calculate_streaks(conn, sid, course_id)
        elif query_type == 'semester' and course_ids:
            # For semester view, use first course's streaks
            streaks = calculate_streaks(conn, sid, course_ids[0]) if course_ids else {'current_streak': 0, 'longest_streak': 0}
        else:
            # For global, use any course
            any_course = conn.execute("SELECT id FROM courses LIMIT 1").fetchone()
            streaks = calculate_streaks(conn, sid, any_course['id']) if any_course else {'current_streak': 0, 'longest_streak': 0}
        
        # Generate badges
        badge_course_id = course_id or (course_ids[0] if course_ids else 1)
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
if __name__ == '__main__':
    # host='0.0.0.0' makes the server accessible from other devices on your network
    app.run(host='0.0.0.0', port=5000, debug=False, request_handler=TimedRequestHandler)

# END OF PART 3









