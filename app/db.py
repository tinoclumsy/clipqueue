import mysql.connector
from flask import current_app


def get_connection():
    """Open a new connection to MySQL using the settings from config.py."""
    return mysql.connector.connect(
        host=current_app.config["DB_HOST"],
        port=current_app.config["DB_PORT"],
        user=current_app.config["DB_USER"],
        password=current_app.config["DB_PASSWORD"],
        database=current_app.config["DB_NAME"],
    )


def fetch_all(sql, params=None):
    """Run a SELECT and return ALL rows as a list of dictionaries."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def fetch_one(sql, params=None):
    """Run a SELECT and return only the FIRST row (or None if there is none)."""
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()

def execute_write(sql, params=None):
    """Run an INSERT, UPDATE or DELETE, save it (commit), and return the new row's id."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params or ())
        connection.commit()
        return cursor.lastrowid   # the AUTO_INCREMENT id of a newly inserted row
    finally:
        cursor.close()
        connection.close()

def execute_update(sql, params=None):
    """Run an UPDATE or DELETE, save it, and return how many rows were changed."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params or ())
        connection.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        connection.close()