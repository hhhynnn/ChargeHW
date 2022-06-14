import sqlite3
from config import DB_PATH


def create_user():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        drop table if exists user
    """)
    c.execute("""
        create table  if not exists user (
            id INTEGER PRIMARY KEY NOT NULL,
            uID TEXT UNIQUE NOT NULL,
            passwd TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0
        );
    
    """)
    conn.commit()
    conn.close()


def create_charge_stmt():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        drop table if exists charge_stmt
    """)
    c.execute("""
        create table  if not exists charge_stmt (
            csid INTEGER PRIMARY KEY NOT NULL,
            uid TEXT NOT NULL,
            mode TEXT NOT NULL,
            reserve FLOAT NOT NULL,
            pileid TEXT NULL,
            
            time_start TEXT NULL,
            time_end TEXT NULL,
            time_total TEXT NULL,
            
            consume TEXT NULL,
            
            cost_charge FLOAT NULL,
            cost_serve FLOAT NULL,
            cost_total FLOAT NULL,
            
            generate_time TEXT NULL,
            finish TEXT NOT NULL
        );

    """)
    conn.commit()
    conn.close()


if __name__ == '__main__':
    create_charge_stmt()
