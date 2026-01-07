from app.db import get_db_connection
from flask import session

def get_votes(post_ids):
    conn = get_db_connection()
    cur = conn.cursor()

    vote_by_post = {}

    if not post_ids:
        return vote_by_post

    cur.execute("""
    SELECT
        post_id,
        SUM(CASE WHEN value = 1 THEN 1 ELSE 0 END) AS likes,
        SUM(CASE WHEN value = -1 THEN 1 ELSE 0 END) AS dislikes,
        COALESCE(SUM(value), 0) AS score
    FROM post_votes
    WHERE post_id IN %s
    GROUP BY post_id
    """, (tuple(post_ids),))

    for post_id, likes, dislikes, score in cur.fetchall():
        vote_by_post[post_id] = {
            "likes": int(likes or 0),
            "dislikes": int(dislikes or 0),
            "score": int(score or 0),
            "user_vote": 0
        }

    for pid in post_ids:
        vote_by_post.setdefault(pid, {"likes": 0, "dislikes": 0, "score": 0, "user_vote": 0})

    viewer_id = session.get("user_id")
    if viewer_id:
        cur.execute("""
        SELECT post_id, value
        FROM post_votes
        WHERE user_id = %s AND post_id IN %s
        """, (viewer_id, tuple(post_ids)))

        for post_id, value in cur.fetchall():
            vote_by_post[post_id]["user_vote"] = int(value)

    cur.close()
    conn.close()

    return vote_by_post

def get_keywords(post_ids):
    conn = get_db_connection()
    cur = conn.cursor()

    keywords_by_post = {}
    
    if not post_ids:
        return keywords_by_post
    
    cur.execute("""
        SELECT pk.post_id, k.name
        FROM post_keywords pk
        JOIN keywords k ON k.id = pk.keyword_id
        WHERE pk.post_id IN %s
        ORDER BY pk.post_id, k.name
        """, (tuple(post_ids),))

    for post_id, name in cur.fetchall():
        keywords_by_post.setdefault(post_id, []).append(name)

    cur.close()
    conn.close()

    return keywords_by_post