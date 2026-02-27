import sqlite3
import bcrypt
import os
from dotenv import load_dotenv

# =================================================================
#   A.R.I.S.E. Database Setup Script - Production Build
#   - Creates the complete database schema from scratch.
#   - Adds a default administrator for first-time login.
#   - Uses bcrypt for password hashing (production-grade security).
# =================================================================

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))


def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def setup_database():
    """
    Connects to the database, drops old tables for a clean slate,
    creates all new tables with the final schema, and adds a default admin user.
    """
    db_path = os.environ.get('DATABASE_PATH', 'attendance.db')
    
    try:
        connection = sqlite3.connect(db_path)
        # Enable foreign key support in SQLite
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        print("--- Dropping old tables (if they exist)...")
        cursor.execute("DROP TABLE IF EXISTS attendance_records")
        cursor.execute("DROP TABLE IF EXISTS sessions")
        cursor.execute("DROP TABLE IF EXISTS enrollments")
        cursor.execute("DROP TABLE IF EXISTS courses")
        cursor.execute("DROP TABLE IF EXISTS students")
        cursor.execute("DROP TABLE IF EXISTS teachers")
        cursor.execute("DROP TABLE IF EXISTS semesters")
        cursor.execute("DROP TABLE IF EXISTS admins")
        print("Old tables dropped successfully.")

        print("\n--- Creating new tables with final schema...")

        # 1. Admins Table: For secure login to the Admin Panel.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)
        print("Table 'admins' created.")

        # 2. Semesters Table: The top-level container for academic terms.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS semesters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semester_name TEXT UNIQUE NOT NULL
        )
        """)
        print("Table 'semesters' created.")

        # 3. Teachers Table: Stores faculty details and their login PINs.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_name TEXT NOT NULL,
            pin TEXT NOT NULL
        )
        """)
        print("Table 'teachers' created.")

        # 4. Students Table: The master list of all students.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university_roll_no TEXT UNIQUE NOT NULL,
            enrollment_no TEXT UNIQUE NOT NULL,
            student_name TEXT NOT NULL,
            password TEXT NOT NULL,
            email1 TEXT,
            email2 TEXT
        )
        """)
        print("Table 'students' created.")

        # 5. Courses Table: Defines subjects and links them to semesters and teachers.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semester_id INTEGER,
            teacher_id INTEGER,
            course_name TEXT NOT NULL,
            course_code TEXT UNIQUE NOT NULL,
            default_duration_minutes INTEGER DEFAULT 30,
            FOREIGN KEY (semester_id) REFERENCES semesters (id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES teachers (id) ON DELETE SET NULL
        )
        """)
        print("Table 'courses' created.")

        # 6. Enrollments Table: The critical junction table linking students to courses.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            student_id INTEGER,
            course_id INTEGER,
            class_roll_id INTEGER NOT NULL,
            PRIMARY KEY (student_id, course_id),
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses (id) ON DELETE CASCADE
        )
        """)
        print("Table 'enrollments' created.")

        # 7. Sessions Table: Logs every single lecture that takes place.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            is_active BOOLEAN DEFAULT 0,
            session_type TEXT DEFAULT 'offline' NOT NULL,
            topic TEXT,
            session_token TEXT,
            otp_seed TEXT
        )
        """)
        print("Table 'sessions' created.")

        # 8. Attendance Records Table: Stores every single "Present" mark.
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            student_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            override_method TEXT,
            manual_reason TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
        """)
        print("Table 'attendance_records' created.")

        # 9. System Settings Table: Stores global configuration like "Batch Name".
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)
        # Insert default batch name if not exists
        cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)", ('batch_name', 'My Classroom Pod'))
        print("Table 'system_settings' created.")
        
        print("\n--- All tables created successfully.")

        # --- Create a Default Admin User ---
        print("\n--- Adding default admin user...")
        admin_password = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'admin')
        # Hash the default password with bcrypt (production-grade)
        hashed_admin_password = hash_password(admin_password)
        try:
            cursor.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ('admin', hashed_admin_password))
            print("Default admin user created successfully.")
            print("  Username: admin")
            print(f"  Password: {admin_password}")
            print("  \u26a0\ufe0f  CHANGE THIS PASSWORD IMMEDIATELY after first login!")
        except sqlite3.IntegrityError:
            print("Admin user already exists.")

        # Save (commit) all changes to the database file
        connection.commit()
        print("\nDatabase changes committed.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure the connection is always closed, even if errors occur
        if connection:
            connection.close()
            print("Database connection closed.")

# This block allows the script to be run directly from the command line
if __name__ == '__main__':
    print("Starting database setup...")
    setup_database()
    print("\nDatabase setup complete.")
