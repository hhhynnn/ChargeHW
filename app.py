import sqlite3
import time

from flask import Flask, request

app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return "hello"


@app.route('/user/register/')
def user_register():
    username = request.args.get('username')
    passwd = request.args.get('passwd')
    conn = sqlite3.connect('res.db')
    print(f'user:{username}, passwd:{passwd}')
    c = conn.cursor()
    c.execute("""
        select username from user;
    """)
    result = c.fetchall()
    usernames = [x[0] for x in result]
    if username not in usernames:
        c.execute(f"""
            insert into user (username, passwd) values
            ('{username}','{passwd}');
        """)
        message = "success"
    else:
        message = "username already exists"
    conn.commit()
    conn.close()
    return message


@app.route('/user/login')
def user_login():
    username = request.args.get('username')
    passwd = request.args.get('passwd')
    conn = sqlite3.connect('res.db')
    c = conn.cursor()
    c.execute("""
        select username,passwd from user
    """)
    result = c.fetchall()
    if (username, passwd) in result:
        message = "success"
    elif username in [x[0] for x in result]:
        message = "wrong passwd"
    else:
        message = "username not exists"
    conn.commit()
    conn.close()
    return message


if __name__ == '__main__':
    app.run(threaded=True)
