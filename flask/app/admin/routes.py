from flask import Blueprint
from flask import render_template, request, redirect, url_for, session, abort, jsonify
from app.decorators import roles_required, permission_required
from app.db import get_db_connection
from app.security import is_safe_redirect

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin", methods=["GET"])
@roles_required("admin")
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor() 
    cur.execute("""
        SELECT
            u.id,
            u.username,
            u.email,
            u.role,
            u.is_activated,
            u.is_blocked,
            COALESCE(
                string_agg(up.permission_key, ',' ORDER BY up.permission_key),
                ''
            ) AS permissions
        FROM users u
        LEFT JOIN user_permissions up
            ON up.user_id = u.id
        GROUP BY
            u.id, u.username, u.email, u.role, u.is_activated, u.is_blocked
        ORDER BY u.id;
    """)
    users = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_dashboard.html", users=users)

@admin_bp.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@permission_required("ban_user")
def toggle_user_status(user_id):
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
            SET is_blocked = FALSE
            WHERE id = %s
        """, (user_id, ))
    
    elif not is_blocked and is_activated:
        cur.execute("""
            UPDATE users
            SET is_blocked = TRUE
            WHERE id = %s
        """, (user_id, ))
    
    elif not is_activated:
        cur.execute("""
            UPDATE users
            SET is_activated = TRUE,
                activation_token = NULL,
                activation_token_expiry = NULL
            WHERE id = %s
        """, (user_id, ))
    
    conn.commit()
    cur.close()
    conn.close()

    next_url = request.form.get("next") or request.args.get("next")
    if is_safe_redirect(next_url):
        return redirect(next_url)

    return redirect(url_for("admin.dashboard"))

@admin_bp.route("/admin/users/<int:user_id>/permissions", methods=["GET"])
@roles_required("admin")
def get_user_permissions(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM users WHERE id=%s", (user_id,))
    if cur.fetchone() is None:
        cur.close()
        conn.close()
        abort(404)

    cur.execute("SELECT key, description FROM permissions ORDER BY key")
    all_perms = cur.fetchall()

    cur.execute("SELECT permission_key FROM user_permissions WHERE user_id=%s", (user_id,))
    assigned = [r[0] for r in cur.fetchall()]

    cur.close()
    conn.close()

    return jsonify({
        "all": [{"key": k, "description": d} for (k, d) in all_perms],
        "assigned": assigned
    })

@admin_bp.route("/admin/users/<int:user_id>/permissions", methods=["POST"])
@roles_required("admin")
def set_user_permissions(user_id):
    if user_id == session.get("user_id"):
        abort(400)

    data = request.get_json(silent=True) or {}
    perms = data.get("permissions", [])

    if not isinstance(perms, list):
        abort(400)

    perms = sorted(set([p.strip() for p in perms if isinstance(p, str) and p.strip()]))

    conn = get_db_connection()
    cur = conn.cursor()

    if perms:
        cur.execute("SELECT key FROM permissions WHERE key = ANY(%s)", (perms,))
        valid = {r[0] for r in cur.fetchall()}
        if len(valid) != len(perms):
            cur.close()
            conn.close()
            abort(400)

    cur.execute("DELETE FROM user_permissions WHERE user_id=%s", (user_id,))
    if perms:
        cur.executemany(
            "INSERT INTO user_permissions (user_id, permission_key) VALUES (%s, %s)",
            [(user_id, p) for p in perms]
        )

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True})

@admin_bp.route("/admin/users/<int:user_id>/role", methods=["POST"])
@roles_required("admin")
def set_user_role(user_id):
    if user_id == session.get("user_id"):
        abort(400)  

    data = request.get_json(silent=True) or {}
    new_role = (data.get("role") or "").strip()

    allowed = {"user", "moderator", "admin"}
    if new_role not in allowed:
        abort(400)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, user_id))

    # delte permissions if changed to user
    if new_role == "user":
        cur.execute("DELETE FROM user_permissions WHERE user_id=%s", (user_id,))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"success": True, "role": new_role})