from flask import session
from app.db import get_db_connection

def inject_permissions():
    if not session.get("user_id"):
        return {"user_permissions": set()}

    if session.get("role") == "admin":
        return {"user_permissions": {"*"}}

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT permission_key
        FROM user_permissions
        WHERE user_id = %s
    """, (session["user_id"],))
    perms = {r[0] for r in cur.fetchall()}
    cur.close()
    conn.close()

    return {"user_permissions": perms}
