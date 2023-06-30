from fastapi import FastAPI
from pydantic import BaseModel
from api.exception.command_exception import CommandException
from api.utils import const
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
    if user_type == None or user_type == "undefine":
      raise CommandException(const.ERROR_CLIENT_PARAM_BLANK, "This plugin is blank!", "This plugin is blank!")
    if user_type != "nginx" and user_type != "portainer":
      raise CommandException(const.ERROR_CLIENT_PARAM_NOTEXIST, "This plugin doesn't exist!", "This plugin doesn't exist!")
    conn = sqlite3.connect('/usr/src/app/database.sqlite')
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT user_name,password,nick_name FROM user WHERE user_type=?", (user_type,))
    rows = cursor.fetchone()
    conn.close()
    return rows
