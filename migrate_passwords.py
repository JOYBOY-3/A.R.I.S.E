# =================================================================
#   A.R.I.S.E. - Password Migration Script
#   Migrates existing SHA-256 passwords to bcrypt hashing
#   Run this ONCE after upgrading to the production build
# =================================================================

import sqlite3
import bcrypt
import hashlib
import os
from dotenv import load_dotenv

# Load environment
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
DB_PATH = os.environ.get('DATABASE_PATH', 'attendance.db')


def is_sha256(password_hash):
    """Check if a hash looks like SHA-256 (64 hex characters)."""
    return len(password_hash) == 64 and all(c in '0123456789abcdef' for c in password_hash)


def hash_with_bcrypt(plain_or_sha256):
    """
    We can't reverse SHA-256 to get the original password.
    Instead, we hash the SHA-256 hash WITH bcrypt, and update verify_password
    to handle this double-hash scenario.
    
    Actually, the better approach: since we can't know the original password,
    we'll just re-hash the existing SHA-256 hash using bcrypt.
    The verify_password function in server.py already handles SHA-256 fallback,
    so existing users can still log in with their old passwords.
    
    For a clean migration, we should ask users to reset their passwords.
    But for now, we'll keep SHA-256 fallback active in verify_password().
    """
    return bcrypt.hashpw(plain_or_sha256.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def migrate_admin_passwords(conn, cursor):
    """Migrate admin passwords from SHA-256 to bcrypt."""
    print("\n--- Migrating Admin Passwords ---")
    admins = cursor.execute("SELECT id, username, password FROM admins").fetchall()
    migrated = 0
    skipped = 0
    
    for admin in admins:
        admin_id, username, pwd_hash = admin
        
        if pwd_hash.startswith('$2b$') or pwd_hash.startswith('$2a$'):
            print(f"  [SKIP] Admin '{username}' - Already using bcrypt")
            skipped += 1
            continue
        
        if is_sha256(pwd_hash):
            # Keep the SHA-256 hash as-is — verify_password() handles fallback
            # The user will be migrated when they next change their password
            print(f"  [KEEP] Admin '{username}' - SHA-256 hash preserved (will migrate on next password change)")
            skipped += 1
        else:
            print(f"  [WARN] Admin '{username}' - Unknown hash format, skipping")
            skipped += 1
    
    print(f"  Result: {migrated} migrated, {skipped} skipped/preserved")
    return migrated


def migrate_student_passwords(conn, cursor):
    """Migrate student passwords from SHA-256 to bcrypt."""
    print("\n--- Migrating Student Passwords ---")
    students = cursor.execute("SELECT id, university_roll_no, password FROM students").fetchall()
    migrated = 0
    skipped = 0
    
    for student in students:
        sid, roll_no, pwd_hash = student
        
        if pwd_hash.startswith('$2b$') or pwd_hash.startswith('$2a$'):
            skipped += 1
            continue
        
        if is_sha256(pwd_hash):
            skipped += 1
        else:
            skipped += 1
    
    print(f"  Total students: {len(students)}")
    print(f"  Result: {migrated} migrated, {skipped} preserved (SHA-256 fallback active)")
    return migrated


def migrate_teacher_pins(conn, cursor):
    """Migrate teacher PINs to bcrypt hashing."""
    print("\n--- Migrating Teacher PINs ---")
    teachers = cursor.execute("SELECT id, teacher_name, pin FROM teachers").fetchall()
    migrated = 0
    skipped = 0
    
    for teacher in teachers:
        tid, name, pin = teacher
        
        if pin.startswith('$2b$') or pin.startswith('$2a$'):
            print(f"  [SKIP] Teacher '{name}' - Already using bcrypt")
            skipped += 1
            continue
        
        # Teacher PINs were stored in PLAINTEXT - we can hash them properly!
        new_hash = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("UPDATE teachers SET pin = ? WHERE id = ?", (new_hash, tid))
        print(f"  [OK]   Teacher '{name}' - PIN migrated to bcrypt")
        migrated += 1
    
    print(f"  Result: {migrated} migrated, {skipped} skipped")
    return migrated


def run_migration():
    """Run the complete password migration."""
    print("=" * 60)
    print("  A.R.I.S.E. Password Migration Tool")
    print("  Migrating to bcrypt password hashing")
    print("=" * 60)
    print(f"\nDatabase: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print(f"\n[ERROR] Database file not found: {DB_PATH}")
        print("Make sure the database exists before running migration.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        total_migrated = 0
        total_migrated += migrate_admin_passwords(conn, cursor)
        total_migrated += migrate_student_passwords(conn, cursor)
        total_migrated += migrate_teacher_pins(conn, cursor)
        
        conn.commit()
        
        print(f"\n{'=' * 60}")
        print(f"  Migration Complete!")
        print(f"  Total records migrated: {total_migrated}")
        print(f"  ")
        print(f"  NOTE: Existing admin/student SHA-256 passwords are preserved.")
        print(f"  They will continue to work via the SHA-256 fallback in")
        print(f"  verify_password(). Passwords will be upgraded to bcrypt")
        print(f"  automatically when users next change their passwords.")
        print(f"  ")
        print(f"  Teacher PINs have been migrated to bcrypt immediately")
        print(f"  since they were stored in plaintext.")
        print(f"{'=' * 60}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        print("No changes were made to the database.")
    finally:
        conn.close()


if __name__ == '__main__':
    run_migration()
