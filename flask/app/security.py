import bcrypt
import re
from app.db import get_db_connection

password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
username_pattern = r'^[A-Za-z0-9_]{3,}$'
email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

def hash_password(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_password(pw, stored):
    return bcrypt.checkpw(pw.encode(), stored.encode())

def is_valid_email(email: str) -> bool:
    return bool(re.match(email_pattern, email))

def is_valid_username(username: str) -> bool:
    return bool(re.match(username_pattern, username))

def is_valid_password(password: str) -> bool:
    return bool(re.match(password_pattern, password))

def user_has_permission(user_id: int, permission_key: str) -> bool:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 1
        FROM user_permissions
        WHERE user_id = %s AND permission_key = %s
        LIMIT 1
    """, (user_id, permission_key))
    ok = cur.fetchone() is not None
    cur.close()
    conn.close()
    return ok

def sanitize_text(text):
    return

