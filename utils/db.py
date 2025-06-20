import sqlite3

DB_PATH = "data/survey.db"  # Путь к файлу БД

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS surveys (
        user_id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        age TEXT NOT NULL,
        creative_fields TEXT NOT NULL,
        about TEXT NOT NULL,
        socials TEXT
    )
    """)
    conn.commit()
    conn.close()

def save_survey(user_id, name, age, creative_fields, about, socials):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO surveys (user_id, name, age, creative_fields, about, socials)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        name=excluded.name,
        age=excluded.age,
        creative_fields=excluded.creative_fields,
        about=excluded.about,
        socials=excluded.socials
    """, (user_id, name, age, creative_fields, about, socials))
    conn.commit()
    conn.close()

def get_survey_by_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT name, age, creative_fields, about, socials
    FROM surveys
    WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "name": row[0],
        "age": row[1],
        "creative_fields": row[2],
        "about": row[3],
        "socials": row[4]
    }
