from functools import wraps
from flask import session, abort
from app.db import get_db_connection

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                abort(401)
            if session.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login_get"))
        return fn(*args, **kwargs)
    return wrapper


def permission_required(permission_key: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                abort(401)

            if session.get("role") == "admin":
                return fn(*args, **kwargs)

            user_id = session["user_id"]
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

            if not ok:
                abort(403)

            return fn(*args, **kwargs)
        return wrapper
    return decorator
