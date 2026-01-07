from flask import Blueprint, render_template, Flask, session
from app.db import get_db_connection
from app.post_helpers import get_votes, get_keywords

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.created_at, u.username,
            pm.media_type, pm.file_path, p.user_id
        FROM posts p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN post_media pm ON pm.post_id = p.id
        WHERE p.is_deleted = FALSE
        ORDER BY p.created_at DESC
        LIMIT 50
    """)
    posts = cur.fetchall()

    post_ids = [p[0] for p in posts]

    keywords_by_post = get_keywords(post_ids)
    vote_by_post = get_votes(post_ids)
    

    cur.close()
    conn.close()

    return render_template(
        "index.html",
        posts=posts,
        keywords_by_post=keywords_by_post,
        vote_by_post=vote_by_post,
    )


