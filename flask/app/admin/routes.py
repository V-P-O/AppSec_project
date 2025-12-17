from flask import Blueprint
from flask import render_template, request, redirect, url_for, session
from app.decorators import roles_required
from app.db import get_db_connection

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin", methods=["GET"])
@roles_required("admin")
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor() 
    cur.execute("""
        SELECT id, username, email, role, is_activated, is_blocked
        FROM users
        ORDER BY id
    """)
    users = curr.fetchall()

    curr.close()
    conn.close()

    return render_template("admin_dashboard.html", users=users)

@admin_bp.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_user(user_id):
    if user_id == session.get("user_id"):
        abort(400)
    
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT is_activated, is_blocked
        FROM users
        WHERE id = %s
    """, (user_id,))
    user = cur.fetchone()

    if not user:
        abort(404)

    is_activated, is_blocked = user

    if is_blocked:
        cur.execute("""
            UPDATE users
            SET is_blocked = FALSE,
            WHERE id = %s
        """, (user_id))
    
    elif not is_blocked and is_activated:
        cur.execute("""
            UPDATE users
            SET is_blocked = TRUE,
            WHERE id = %s
        """, (user_id))
    
    elif not is_activated:
        cur.execute("""
            UPDATE users
            SET is_activated = TRUE,
            WHERE id = %s
        """, (user_id))
    
    conn.commit()
    cur.close()
    conn.close()