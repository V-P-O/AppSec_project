from flask import Blueprint, render_template, Flask
from app.db import get_db_connection

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.title, p.created_at, u.username,
            pm.media_type, pm.file_path
        FROM posts p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN post_media pm ON pm.post_id = p.id
        WHERE p.is_deleted = FALSE
        ORDER BY p.created_at DESC
        LIMIT 50
    """)
    posts = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("index.html", posts=posts)

