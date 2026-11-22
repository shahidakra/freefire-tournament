import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app_tournament.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        ff_name TEXT,
        ff_uid TEXT,
        balance INTEGER DEFAULT 100,
        total_kills INTEGER DEFAULT 0,
        matches_played INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Matches
    c.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        map_name TEXT,
        mode TEXT,
        entry_fee INTEGER DEFAULT 0,
        per_kill INTEGER DEFAULT 0,
        win_prize INTEGER DEFAULT 0,
        match_time TEXT,
        total_slots INTEGER DEFAULT 48,
        room_id TEXT DEFAULT '',
        room_pass TEXT DEFAULT '',
        status TEXT DEFAULT 'UPCOMING'
    )
    ''')
    
    # Participants
    c.execute('''
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        user_id INTEGER,
        ff_name TEXT,
        ff_uid TEXT,
        slot_number INTEGER,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(match_id, user_id)
    )
    ''')
    
    # Add default admin if not exists
    admin = c.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
    if not admin:
        c.execute('''
            INSERT INTO users (username, password, ff_name, ff_uid, balance, is_admin)
            VALUES ('admin', 'admin123', 'Admin_Boss', '1000000001', 5000, 1)
        ''')
        
    # Add a sample match if none exists
    matches_count = c.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    if matches_count == 0:
        c.execute('''
            INSERT INTO matches (title, map_name, mode, entry_fee, per_kill, win_prize, match_time, total_slots, status)
            VALUES 
            ('Grand Bermuda Solo Cup #1', 'Bermuda', 'SOLO', 20, 10, 250, 'Today 06:00 PM', 48, 'UPCOMING'),
            ('Purgatory Duo Rush #2', 'Purgatory', 'DUO', 40, 20, 500, 'Today 08:30 PM', 24, 'UPCOMING'),
            ('Squad Battle Royale Mega #3', 'Kalahari', 'SQUAD', 80, 40, 1200, 'Tomorrow 05:00 PM', 12, 'UPCOMING')
        ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("App database initialized successfully.")
