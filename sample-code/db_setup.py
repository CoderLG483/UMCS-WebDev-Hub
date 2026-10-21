import sqlite3
from werkzeug.security import generate_password_hash
import os

# Define the path for the database file
DB_NAME = 'database.db'

def setup_database():
    """Initializes the SQLite database with necessary tables and an admin user."""
    # --- ⚠️ This will reset the DB – good for demo, but warn team before running.
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        print(f"Removed existing database file: {DB_NAME}")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # --- 1. Users Table (Admin Login) ---
    print("Creating 'users' table...")
    cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    # --- Insert a default admin user (Password: 1234)
    admin_username="admin@cogop.org"
    admin_password_hash = generate_password_hash('1234')
    cursor.execute("""
        INSERT INTO users (username, password_hash)
        VALUES (?, ?)
    """, (admin_username, admin_password_hash))
    print("Inserted default admin user (username: admin@cogop.org, password: 1234)")

    # --- 2. Events Table (FR-ADM-001) ---
    print("Creating 'events' table...")
    cursor.execute("""
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            event_date TEXT NOT NULL,      -- YYYY-MM-DD
            event_time TEXT,               -- HH:MM (optional)
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            is_published INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- 3. Announcements Table (FR-ADM-007) ---
    print("Creating 'announcements' table...")
    cursor.execute("""
        CREATE TABLE announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            expiration_date TEXT,          -- YYYY-MM-DD (optional)
            is_published INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- 4. Members Table (FR-MEM-001 etc.) ---
    print("Creating 'members' table...")
    cursor.execute("""
        CREATE TABLE members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_info TEXT NOT NULL,
            dob TEXT,                       -- YYYY-MM-DD (optional)
            address TEXT,
            ministry TEXT NOT NULL,
            status TEXT NOT NULL,           -- e.g. Active / Inactive / Deleted
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- 5. Member Change Logs (for audit trail) ---
    print("Creating 'member_change_logs' table...")
    cursor.execute("""
        CREATE TABLE member_change_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(member_id) REFERENCES members(id)
        )
    """)

    # --- This table holds information about the various church ministries/departments
    print("Creating 'ministries' table...")
    cursor.execute("""
        CREATE TABLE ministries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            leader_name TEXT,
            contact_email TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    # --- Sermons Table ---
    # Stores details for all preached sermons (audio or video links)
    print("Creating 'sermons' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sermons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            preacher TEXT,
            sermon_date DATE NOT NULL,
            sermon_link TEXT NOT NULL,
            summary TEXT,
            is_published INTEGER NOT NULL DEFAULT 0, 
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """) 
    conn.commit()
    conn.close()
print("Database setup complete.")

if __name__ == "__main__":
    setup_database()

