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
            uid TEXT UNIQUE NOT NULL,
            passwd TEXT NOT NULL,
            capacity REAL NOT NULL,
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
            
            consume FLOAT NULL,
            
            cost_charge FLOAT NULL,
            cost_serve FLOAT NULL,
            
            generate_time TEXT NULL,
            finish TEXT NOT NULL
        );

    """)
    conn.commit()
    conn.close()


def creat_user_to_charge_stmt():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        drop table if exists user_to_charge_stmt
    """)
    c.execute("""
        create table  if not exists user_to_charge_stmt (
            id INTEGER PRIMARY KEY NOT NULL,
            uid TEXT NOT NULL,
            csid INTEGER NOT NULL
        );

    """)
    conn.commit()
    conn.close()


def create_pile():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        drop table if exists charge_pile
    """)
    c.execute("""
        create table  if not exists charge_pile (
            pileid TEXT PRIMARY KEY NOT NULL,
            charge_cnt INTEGER INTEGER NOT NULL DEFAULT 0,
            charge_time FLOAT NOT NULL DEFAULt 0,
            charge_capacity FLOAT NOT NULL DEFAULT 0,
            cost_charge FLOAT NOT NULL DEFAULT 0,
            cost_serve FLOAT NOT NULL DEFAULT 0,
            state TEXT NOT NULL DEFAULT 'on'
        );

    """)
    c.execute("""
        insert into charge_pile (pileid) values
        ('T#1'),
        ('T#2'),
        ('T#3'),
        ('F#1'),
        ('F#2')
    """)
    conn.commit()
    conn.close()


if __name__ == '__main__':
    # create_user()
    create_charge_stmt()
    creat_user_to_charge_stmt()
    create_pile()
