import bcrypt
import re
from app.db import get_db_connection
from urllib.parse import urlparse, urljoin
from flask import request


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
    if user_id is None:
        return False

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


def parse_keywords(raw: str, max_keywords: int = 10):
    if not raw:
        return []

    parts = [p.strip().lower() for p in raw.split(",")]
    parts = [p for p in parts if p]

    rx = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,28}[a-z0-9]$")

    out, seen = [], set()
    for p in parts:
        if p in seen:
            continue
        if rx.fullmatch(p) is None:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= max_keywords:
            break
    return out

def is_safe_redirect(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc

