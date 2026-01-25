import sqlite3

def migrate_db():
    try:
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_settings'")
        if cursor.fetchone():
            print("Table 'system_settings' already exists.")
        else:
            print("Creating table 'system_settings'...")
            cursor.execute("""
            CREATE TABLE system_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """)
            # Insert default value
            cursor.execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", ('batch_name', 'My Classroom Pod'))
            conn.commit()
            print("Table 'system_settings' created and initialized.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    migrate_db()
