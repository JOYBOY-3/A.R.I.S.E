# =================================================================
#   A.R.I.S.E. - Database Backup Script
#   Creates timestamped backups of the SQLite database
#
#   Usage: python backup_db.py
#   Cron:  0 */6 * * * cd /path/to/arise && python backup_db.py
# =================================================================

import shutil
import os
import datetime
import glob
from dotenv import load_dotenv

# Load environment
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# --- Configuration ---
DB_PATH = os.environ.get('DATABASE_PATH', 'attendance.db')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
MAX_BACKUPS = 10  # Keep last N backups


def create_backup():
    """Create a timestamped backup of the database."""
    
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        return False
    
    # Create backup directory
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Generate timestamped filename
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    db_name = os.path.splitext(os.path.basename(DB_PATH))[0]
    backup_filename = f"{db_name}_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    try:
        # Copy the database file
        shutil.copy2(DB_PATH, backup_path)
        
        # Get file size
        size_mb = os.path.getsize(backup_path) / (1024 * 1024)
        print(f"[OK] Backup created: {backup_filename} ({size_mb:.2f} MB)")
        
        # Cleanup old backups
        cleanup_old_backups()
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Backup failed: {e}")
        return False


def cleanup_old_backups():
    """Remove old backups, keeping only the most recent MAX_BACKUPS."""
    pattern = os.path.join(BACKUP_DIR, '*_backup_*.db')
    backups = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    
    if len(backups) > MAX_BACKUPS:
        for old_backup in backups[MAX_BACKUPS:]:
            try:
                os.remove(old_backup)
                print(f"[CLEANUP] Removed old backup: {os.path.basename(old_backup)}")
            except Exception as e:
                print(f"[WARN] Could not remove {old_backup}: {e}")


def list_backups():
    """List all available backups."""
    pattern = os.path.join(BACKUP_DIR, '*_backup_*.db')
    backups = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    
    if not backups:
        print("No backups found.")
        return
    
    print(f"\n{'='*60}")
    print(f"  A.R.I.S.E. Database Backups ({len(backups)} found)")
    print(f"{'='*60}")
    
    for i, backup in enumerate(backups, 1):
        size_mb = os.path.getsize(backup) / (1024 * 1024)
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(backup))
        print(f"  {i}. {os.path.basename(backup)} - {size_mb:.2f} MB - {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--list':
        list_backups()
    else:
        print("A.R.I.S.E. Database Backup")
        print(f"Source: {DB_PATH}")
        create_backup()
        print("\nUse --list to see all available backups.")
