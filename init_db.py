from pathlib import Path
import sqlite3
"""
Database files will be stored in the data/ folder.
We will use Pathlib to create the files in data/ 
& to be able to run the database from any location 
even if we're in different directories.
"""
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "database.db"

def init_db(conn):
    # Create tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL
                CHECK (role IN ('مدير', 'مشرف', 'موظف')),
            department TEXT NOT NULL
                CHECK (department IN ('المالية', 'المشاريع', 'الإدارة'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            scheduled_at TEXT NOT NULL,
            creator_id INTEGER NOT NULL,
            assignee_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN (
                    'pending', 
                    'in_progress', 
                    'completed',
                    'cancelled'
                    )
                ),
            FOREIGN KEY (creator_id) 
                REFERENCES employees(id),
            FOREIGN KEY (assignee_id) 
                REFERENCES employees(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            action_taken TEXT NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('success', 'rejected', 'error', 'clarify'))
        )
    """)
    # Prevent accidental modification or deletion of audit records.
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_audit_update
        BEFORE UPDATE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'Audit logs are append-only');
        END
    """)

    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
        BEFORE DELETE ON audit_logs
        BEGIN
            SELECT RAISE(ABORT, 'Audit logs are append-only');
        END
    """)
    # Verify 
    print(f"Database initialized successfully. Location: {DB_PATH}")
    

"""
including everything in a main function to avoid running the code (making db connection) when importing this file in other modules.
"""

if __name__ == "__main__":
    # Connect to SQLite databases
    conn = sqlite3.connect(DB_PATH)
    # foreign keys supported
    conn.execute("PRAGMA foreign_keys = ON;")
    # Initialize the database and create tables
    init_db(conn)

    # Insert initial employees in the table
    employees = [
        (1, 'مدير', 'منيرة', 'الإدارة'),
        (2, 'مشرف', 'سارة', 'المشاريع'),
        (3, 'موظف', 'فهد', 'المشاريع'),
        (4, 'موظف', 'خالد', 'المشاريع'),
        (5, 'موظف', 'نورة', 'المالية'),
        (6, 'مشرف', 'عبدالرحمن', 'المالية'),
    ]

    conn.executemany("""
        INSERT OR IGNORE INTO employees
            (id, role, name, department)
        VALUES (?, ?, ?, ?);
    """, employees)
    conn.commit()

    # Verify the inserted employees.
    rows = conn.execute("""
        SELECT id, name, role, department
        FROM employees
        ORDER BY id;
    """).fetchall()

    print(f"Database initialized successfully! Location: {DB_PATH}")
    print("\nEmployees:")

    for row in rows:
        print(row)
        
    # Close the database connection
    conn.close() 
