from flask import Blueprint
from flask import render_template, request, redirect, url_for, session, abort, jsonify
from flask import current_app, send_file
from app.decorators import roles_required, login_required, permission_required
from app.db import get_db_connection
from app.uploads import save_upload_hardened
from app.security import user_has_permission, parse_keywords
import os
from app.post_helpers import get_votes, get_keywords

posts_bp = Blueprint("posts", __name__)

@posts_bp.route("/posts/new", methods=["GET"])
@login_required
def new_post_get():
    return render_template("post_new.html")


@posts_bp.route("/posts/new", methods=["POST"])
@login_required
def new_post_post():
    title = (request.form.get("title") or "").strip()
    file = request.files.get("media")

    if not title:
        return render_template("post_new.html", error="Title is required.")

    media_info = None
    if file and file.filename:
        media_info = save_upload_hardened(file)
        if not media_info:
            return render_template("post_new.html", error="Invalid or unsafe file.")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO posts (user_id, title) VALUES (%s, %s) RETURNING id",
        (session["user_id"], title)
    )
    post_id = cur.fetchone()[0]

    if media_info:
        stored_name = os.path.basename(media_info["file_path"])
        cur.execute("""
            INSERT INTO post_media (post_id, media_type, file_path, original_filename, mime_type, file_size_bytes)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            post_id,
            media_info["media_type"],
            stored_name,
            media_info["original_filename"],
            None, 
            media_info["file_size_bytes"]
        ))

    keywords = parse_keywords(request.form.get("keywords", ""))
    add_keywords_to_post(conn, post_id, keywords)

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("posts.view_post", post_id=post_id))


@posts_bp.route("/posts/<int:post_id>", methods=["GET"])
def view_post(post_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT p.id, p.title, p.created_at, u.username, p.user_id,
            pm.media_type, pm.file_path,
            p.is_deleted, p.deleted_at, du.username
        FROM posts p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN post_media pm ON pm.post_id = p.id
        LEFT JOIN users du ON du.id = p.deleted_by_user_id
        WHERE p.id = %s
    """, (post_id,))
    post = cur.fetchone()

    if not post:
        cur.close()
        conn.close()
        abort(404)
        
    is_deleted = post[7]
    owner_id = post[4]

    if is_deleted:
        viewer_id = session.get("user_id")
        viewer_role = session.get("role")

        if not viewer_id:
            abort(404)

        if viewer_id != owner_id and viewer_role != "admin":
            if not user_has_permission(viewer_id, "delete_any_post"):
                abort(404)
    

    cur.execute("""
        SELECT
        COALESCE(SUM(value), 0) AS score,
        COALESCE(SUM(CASE WHEN value = 1 THEN 1 ELSE 0 END), 0) AS likes,
        COALESCE(SUM(CASE WHEN value = -1 THEN 1 ELSE 0 END), 0) AS dislikes
        FROM post_votes
        WHERE post_id = %s
    """, (post_id,))
    score, likes, dislikes = cur.fetchone()

    user_vote = 0
    if session.get("user_id"):
        cur.execute("""
            SELECT value FROM post_votes
            WHERE post_id = %s AND user_id = %s
        """, (post_id, session["user_id"]))
        row = cur.fetchone()
    user_vote = row[0] if row else 0

    cur.execute("""
        SELECT c.id, c.parent_comment_id, c.body, c.created_at,
            u.username, c.user_id
        FROM comments c
        JOIN users u ON u.id = c.user_id
        WHERE c.post_id = %s AND c.is_deleted = FALSE
        ORDER BY c.created_at ASC
    """, (post_id,))
    comments = cur.fetchall()

    cur.execute("""
        SELECT k.name
        FROM post_keywords pk
        JOIN keywords k ON k.id = pk.keyword_id
        WHERE pk.post_id = %s
        ORDER BY k.name;
    """, (post_id, ))
    keywords = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "post_detail.html",
        post=post,
        score=score, likes=likes, dislikes=dislikes,
        user_vote=user_vote,
        comments=comments,
        keywords=keywords
    )



@posts_bp.route("/media/<path:filename>", methods=["GET"])
def media(filename):
    if "/" in filename or ".." in filename:
        abort(404)

    abs_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(abs_path):
        abort(404)

    resp = send_file(abs_path, conditional=True)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp

@posts_bp.route("/posts/<int:post_id>/vote", methods=["POST"])
@login_required
def vote_post(post_id):
    data = request.get_json(silent=True) or {}
    v = data.get("value")

    if v not in (1, -1):
        abort(400)

    conn = get_db_connection()
    cur = conn.cursor()

    # toggle behavior: same vote again => remove vote
    cur.execute("""
        SELECT value FROM post_votes
        WHERE post_id=%s AND user_id=%s
    """, (post_id, session["user_id"]))
    row = cur.fetchone()

    if row and row[0] == v:
        cur.execute("""
            DELETE FROM post_votes
            WHERE post_id=%s AND user_id=%s
        """, (post_id, session["user_id"]))
    else:
        cur.execute("""
            INSERT INTO post_votes (post_id, user_id, value)
            VALUES (%s, %s, %s)
            ON CONFLICT (post_id, user_id)
            DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
        """, (post_id, session["user_id"], v))

    conn.commit()

    # return updated totals
    cur.execute("""
        SELECT
          COALESCE(SUM(value), 0) AS score,
          COALESCE(SUM(CASE WHEN value = 1 THEN 1 ELSE 0 END), 0) AS likes,
          COALESCE(SUM(CASE WHEN value = -1 THEN 1 ELSE 0 END), 0) AS dislikes
        FROM post_votes
        WHERE post_id = %s
    """, (post_id,))
    score, likes, dislikes = cur.fetchone()

    cur.close()
    conn.close()
    return jsonify({"score": score, "likes": likes, "dislikes": dislikes})

@posts_bp.route("/posts/<int:post_id>/comments", methods=["POST"])
@login_required
def add_comment(post_id):
    body = (request.form.get("body") or "").strip()
    parent_id = request.form.get("parent_comment_id")

    if not body:
        abort(400)

    parent_id_int = None
    if parent_id:
        try:
            parent_id_int = int(parent_id)
        except ValueError:
            abort(400)

    conn = get_db_connection()
    cur = conn.cursor()

    # If replying to a comment, ensure it belongs to same post
    if parent_id_int is not None:
        cur.execute("SELECT 1 FROM comments WHERE id=%s AND post_id=%s", (parent_id_int, post_id))
        if cur.fetchone() is None:
            cur.close(); conn.close()
            abort(400)

    cur.execute("""
        INSERT INTO comments (post_id, user_id, parent_comment_id, body)
        VALUES (%s, %s, %s, %s)
    """, (post_id, session["user_id"], parent_id_int, body))

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("posts.view_post", post_id=post_id))

@posts_bp.route("/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id, is_deleted FROM posts WHERE id=%s", (post_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        abort(404)

    owner_id, is_deleted = row
    if is_deleted:
        cur.close(); conn.close()
        return redirect(url_for("posts.view_post", post_id=post_id))

    viewer_id = session["user_id"]
    viewer_role = session.get("role")

    can_delete = (
        viewer_id == owner_id
        or viewer_role == "admin"
        or user_has_permission(viewer_id, "delete_any_post")
    )
    if not can_delete:
        cur.close(); conn.close()
        abort(403)

    cur.execute("""
        UPDATE posts
        SET is_deleted = TRUE,
            deleted_at = NOW(),
            deleted_by_user_id = %s
        WHERE id = %s
    """, (viewer_id, post_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("posts.view_post", post_id=post_id))

@posts_bp.route("/posts/<int:post_id>/recover", methods=["POST"])
@permission_required("delete_any_post")
def recover_post(post_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT user_id, is_deleted FROM posts WHERE id=%s", (post_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        abort(404)

    owner_id, is_deleted = row
    if not is_deleted:
        cur.close(); conn.close()
        return redirect(url_for("posts.view_post", post_id=post_id))

    viewer_id = session["user_id"]
    viewer_role = session.get("role")

    can_recover = (
        viewer_role == "admin"
        or user_has_permission(viewer_id, "delete_any_post")
    )
    if not can_recover:
        cur.close(); conn.close()
        abort(403)

    cur.execute("""
        UPDATE posts
        SET is_deleted = FALSE,
            deleted_at = NOW(),
            deleted_by_user_id = %s
        WHERE id = %s
    """, (viewer_id, post_id))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("posts.view_post", post_id=post_id))

def add_keywords_to_post(conn, post_id: int, keywords: list[str]):
    if not keywords:
        return

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO keywords(name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            [(k,) for k in keywords],
        )

        cur.execute("SELECT id, name FROM keywords WHERE name = ANY(%s)", (keywords,))
        rows = cur.fetchall()  # [(id, name), ...]

        cur.executemany(
            "INSERT INTO post_keywords(post_id, keyword_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            [(post_id, kid) for (kid, _name) in rows],
        )

@posts_bp.get("/feed")
def feed():
    q = (request.args.get("q") or "").strip()
    tag = (request.args.get("tag") or "").strip().lower()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT
            p.id, p.title, p.created_at, u.username,
            pm.media_type, pm.file_path, p.user_id
        FROM posts p
        JOIN users u ON u.id = p.user_id
        LEFT JOIN post_media pm ON pm.post_id = p.id
        LEFT JOIN post_keywords pk ON pk.post_id = p.id
        LEFT JOIN keywords k ON k.id = pk.keyword_id
        WHERE
            p.is_deleted = FALSE
            AND (%s = '' OR k.name = %s)
            AND (
                %s = ''
                OR p.title ILIKE concat('%%', %s, '%%')
                OR k.name ILIKE concat('%%', %s, '%%')
            )
        ORDER BY p.created_at DESC
        LIMIT 50
    """, (tag, tag, q, q, q))

    posts = cur.fetchall()

    post_ids = [p[0] for p in posts]
    keywords_by_post = get_keywords(post_ids)
    
    vote_by_post = get_votes(post_ids)

    cur.close()
    conn.close()

    return render_template(
        "feed.html",
        posts=posts,
        keywords_by_post=keywords_by_post,
        vote_by_post=vote_by_post,
        q=q,
        tag=tag
    )
