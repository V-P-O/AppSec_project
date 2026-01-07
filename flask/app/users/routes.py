from flask import Blueprint
from flask import render_template, request, redirect, url_for, session, abort, jsonify
from flask import current_app, send_file
from app.decorators import roles_required, login_required, permission_required
from app.db import get_db_connection
from app.uploads import save_upload_hardened
from app.security import user_has_permission, parse_keywords
import os
from app.post_helpers import get_votes, get_keywords

users_bp = Blueprint("users", __name__)

@users_bp.get("/users/<int:user_id>")
def user_profile(user_id: int):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username, is_blocked, role
        FROM users
        WHERE id = %s
    """, (user_id,))
    profile_user = cur.fetchone()

    if not profile_user:
        abort(404)


    current_user = session.get("user_id")
    role = session.get("role")

    can_see_deleted = (current_user is not None and current_user == user_id) or user_has_permission(current_user, "delete_any_post") or role == "admin"

    cur.execute("""
        SELECT p.id, p.title, p.created_at, u.username,
                pm.media_type, pm.file_path, p.user_id
        FROM posts p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN post_media pm ON pm.post_id = p.id
        WHERE p.user_id = %s
            AND (p.is_deleted = FALSE OR %s = TRUE)
        ORDER BY p.created_at DESC
        LIMIT 50
        """, (user_id, can_see_deleted))

    posts = cur.fetchall()

    post_ids = [p[0] for p in posts]
    keywords_by_post = get_keywords(post_ids)
    
    vote_by_post = get_votes(post_ids)

    can_ban = (user_has_permission(current_user, "ban_user") and profile_user[3] != "admin") or role == "admin"

    is_banned =  profile_user[2]

    cur.close()
    conn.close()

    if is_banned and not can_ban:
        abort(404)

    return render_template(
        "user_profile.html",
        profile_user=profile_user,
        posts=posts,
        keywords_by_post=keywords_by_post,
        vote_by_post=vote_by_post,
        can_ban=can_ban,
        is_banned=is_banned,
    )
