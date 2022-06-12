import sqlite3

conn = sqlite3.connect('res.db')


def create_user():
    c = conn.cursor()
    c.execute("""
        drop table if exists user
    """)
    c.execute("""
        create table  if not exists user (
            uID INTEGER PRIMARY KEY NOT NULL,
            username TEXT UNIQUE NOT NULL,
            passwd TEXT NOT NULL
        );
    
    """)
    conn.commit()
    conn.close()


if __name__ == '__main__':
    create_user()
