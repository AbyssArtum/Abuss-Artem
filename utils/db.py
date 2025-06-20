import sqlite3
import os

DB_PATH = "data/users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        guild_id INTEGER,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        text_xp INTEGER DEFAULT 0,
        voice_xp INTEGER DEFAULT 0,
        voice_time INTEGER DEFAULT 0,
        last_update TEXT,
        name TEXT,
        age TEXT,
        creative_fields TEXT,
        about TEXT,
        socials TEXT,
        FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS guilds (
        guild_id INTEGER PRIMARY KEY,
        mod_channel_id INTEGER,
        pub_channel_id INTEGER,
        leaderboard_channel_id INTEGER,
        leaderboard_time TEXT
    )''')
    
    conn.commit()
    conn.close()