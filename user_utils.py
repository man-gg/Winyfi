# user_utils.py

from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection

# Only two roles in this system
ROLES = ("admin", "user")

def get_user_by_username(username):
    """
    Fetch a single user by username.
    Returns a dict with keys:
      id, first_name, last_name, username, password_hash, role
    or None if not found.
    """
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT id, first_name, last_name, username, password_hash, role
              FROM users
             WHERE username = %s
            """,
            (username,)
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def insert_user(username, password, first_name, last_name, role="user"):
    """
    Create a new user record.
    role must be 'admin' or 'user'.
    """
    if role not in ROLES:
        raise ValueError(f"Invalid role: {role!r}")
    pw_hash = generate_password_hash(password)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users
              (first_name, last_name, username, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (first_name, last_name, username, pw_hash, role)
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

def get_all_users():
    """
    Return a list of all users as dicts:
      [ {id, first_name, last_name, username, role}, … ]
    """
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, first_name, last_name, username, role "
            "FROM users ORDER BY id"
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def delete_user(user_id):
    """
    Delete a user by their ID.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

def verify_user(username, password):
    """
    Verify username & password.
    Returns the full user dict (including role) if valid, else None.
    """
    user = get_user_by_username(username)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None

# user_utils.py

from werkzeug.security import generate_password_hash, check_password_hash
from db import get_connection

# Only two roles in this system
ROLES = ("admin", "user")

# … your existing get_user_by_username, insert_user, get_all_users, delete_user, verify_user …

def update_user(user_id, username, password, first_name, last_name):
    """
    Update an existing user's info.
    If `password` is None or empty, leave the hash unchanged.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        if password:
            pw_hash = generate_password_hash(password)
            cur.execute(
                """
                UPDATE users
                   SET first_name    = %s,
                       last_name     = %s,
                       username      = %s,
                       password_hash = %s
                 WHERE id = %s
                """,
                (first_name, last_name, username, pw_hash, user_id)
            )
        else:
            cur.execute(
                """
                UPDATE users
                   SET first_name = %s,
                       last_name  = %s,
                       username   = %s
                 WHERE id = %s
                """,
                (first_name, last_name, username, user_id)
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()
