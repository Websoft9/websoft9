from fastapi import FastAPI
from pydantic import BaseModel
from api.model.user import User
import sqlite3

conn = sqlite3.connect('/usr/src/app/database.sqlite', check_same_thread=False)
cursor = conn.cursor()


def AppUpdateUser(user_name, password):
    sql = "UPDATE user SET password=" + password + " WHERE user_name=" + user_name
    cursor.execute(sql)
    conn.commit()

def AppSearchUsers(user_type):
    sql = "SELECT * FROM user WHERE user_type=" + user_type
    cursor.execute(sql)
    result = cursor.fetchall()
    return result