import sqlite3

conn = sqlite3.connect("history.db")
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        weight REAL,
        time REAL,
        total REAL
    )
    """)
    conn.commit()

def save_history(user_id, weight, time, total):
    cursor.execute(
        "INSERT INTO history (user_id, weight, time, total) VALUES (?, ?, ?, ?)",
        (user_id, weight, time, total)
    )
    conn.commit()

def get_history(user_id):
    cursor.execute(
        "SELECT * FROM history WHERE user_id=? ORDER BY id DESC",
        (user_id,)
    )
    return cursor.fetchall()
