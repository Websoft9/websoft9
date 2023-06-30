from fastapi import FastAPI
from pydantic import BaseModel
from api.model.user import User
import sqlite3

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def AppUpdateUser(user_name, password):
    conn = sqlite3.connect('database.sqlite')
    cursor = conn.cursor()
    cursor.execute("UPDATE user SET password=? WHERE user_name=?", ( password,user_name,))
    conn.commit()
    conn.close()

def AppSearchUsers(user_type):
    conn = sqlite3.connect('/usr/src/app/database.sqlite')
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT user_name,password,nick_name FROM user WHERE user_type=?", (user_type,))
    rows = cursor.fetchone()
    conn.close()
    return rows
