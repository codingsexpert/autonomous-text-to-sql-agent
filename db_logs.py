import sqlite3
import datetime

LOG_DB_PATH = "chat_logs.db"

def init_log_db():
    """Initializes the chat logs database and creates the conversations table."""
    conn = sqlite3.connect(LOG_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            sql_generated TEXT,
            insights TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_chat(session_id, role, message, sql_generated=None, insights=None):
    """Inserts a new chat log entry into the database."""
    try:
        conn = sqlite3.connect(LOG_DB_PATH)
        cursor = conn.cursor()
        
        # Ensure message is a string
        if not isinstance(message, str):
            message = str(message)
            
        cursor.execute(
            "INSERT INTO conversations (session_id, timestamp, role, message, sql_generated, insights) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, datetime.datetime.now().isoformat(), role, message, sql_generated, insights)
        )
        conn.commit()
    except Exception as e:
        print(f"Failed to log chat: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Initialize the db when module is imported
init_log_db()
