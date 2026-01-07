from flask import Blueprint
from flask import render_template, request, redirect, url_for, session
from app.db import get_db_connection
from app.security import hash_password, check_password, is_valid_email, is_valid_password, is_valid_username
import secrets
from app.email import send_reset_email, send_token

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET"])
def login_get():
    if "user_id" in session:
        return redirect(url_for("main.index"))
    return render_template("login.html")

@auth_bp.route("/login", methods=["POST"])
def login_post():
    username = request.form["username"]
    password = request.form["password"]

    password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
    username_pattern = r'^[A-Za-z0-9_]{3,}$'

    if is_valid_email(username) or is_valid_username(username):
        conn = get_db_connection()
        cur = conn.cursor()
    
        cur.execute("""
                SELECT password_hash, is_activated, email, activation_token, id, username, role, is_blocked
                FROM users 
                WHERE username = %s OR email = %s
            """, (username, username))
        user = cur.fetchone()

        cur.close()
        conn.close()
    else:
        return render_template("login.html", error="Invalid username or password")
    
    if user and check_password(password, user[0]):
        if not user[1]:  # is_activated is FALSE
            return render_template("login.html",
                                error="Please activate your account first.",
                                resend_token=user[3],
                                email=user[2])
        if user[7]:  # is_blocked is TRUE
            return render_template("login.html",
                                error="You have been banned from the site.")
        
        session.clear()
        session.modified = True
        session["user_id"] = user[4]
        session["username"] = user[5]
        session["role"] = user[6]
        
        if request.form.get("remember_me"):
            session.permanent = True 
        else:
            session.permanent = False
        
        return redirect(url_for("main.index"))
    else:
        return render_template("login.html", error="Invalid username or password")

@auth_bp.route("/register", methods=["GET"])
def register_get():
    if "user_id" in session:
        return redirect(url_for("main.index"))
    return render_template("register.html")

@auth_bp.route("/register", methods=["POST"])
def register_post():
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]
    password_r = request.form["password_r"]

    if not is_valid_email(email):
        return render_template("register.html", error="Invalid email format.")
    
    if is_valid_username(username):
        
        conn = get_db_connection()
        cur = conn.cursor()
    
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        user = cur.fetchone()
    
        cur.close()
        conn.close()
    else:
        return render_template("register.html", error="Passwords must contain at least 1 upper case letter,"
                                                      "1 special character and be at least 8 characters long."
                                                      "Usernames can only contain letters, numbers and underscore.")

    if not user:
        if password == password_r:
            
            if is_valid_password(password):
                
                hashed = hash_password(password)
    
                conn = get_db_connection()
                cur = conn.cursor()
                
                token, expiry = send_token(email)
                
                cur.execute(
                    """INSERT INTO users (username, email, password_hash, 
                    activation_token, activation_token_expiry) VALUES (%s, %s, %s, %s, %s)""",
                    (username, email, hashed, token, expiry)
                )
                conn.commit()
                cur.close()
                conn.close()
                return "Registration successful! Please activate your account."
            else:
                return render_template("register.html", error="Passwords must contain at least 1 upper case letter,"
                                                              "1 special character and be at least 8 characters long."
                                                              "Usernames can only contain letters, numbers and underscore.")
        else:
            return render_template("register.html", error="Passwords are not matching.")
    else:
        return render_template("register.html", error="Unable to create account. Try again with different data.")

@auth_bp.route("/activate")
def activate():
    token = request.args.get("token")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET is_activated = TRUE, activation_token = NULL, activation_token_expiry = NULL
        WHERE activation_token = %s
          AND activation_token_expiry > NOW()
        RETURNING id
    """, (token,))

    result = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()

    return "Activation successful!" if result else "Invalid or expired token."

@auth_bp.route("/resend_activation")
def resend_activation():
    email = request.args.get("email")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    token, expiry = send_token(email)
    
    cur.execute("""
        UPDATE users SET activation_token = %s, activation_token_expiry = %s
        WHERE email = %s
    """, (token, expiry, email))
    
    conn.commit()
    cur.close()
    conn.close()
    
    return "A new activation email has been sent."

@auth_bp.route("/logout")
def logout():
    session.clear()
    session.modified = True
    return redirect(url_for("main.index"))

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email=%s AND is_activated=TRUE", (email,))
        user = cur.fetchone()

        if user:
            token = secrets.token_urlsafe(32)

            cur.execute("""
                UPDATE users 
                SET reset_token=%s, reset_token_expiry=NOW() + INTERVAL '1 hour'
                WHERE email=%s
            """, (token, email))
            conn.commit()

            send_reset_email(email, token)

        cur.close()
        conn.close()

        return render_template("forgot_password.html", message="If the email exists, a reset link was sent.")

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id 
        FROM users 
        WHERE reset_token=%s AND reset_token_expiry > NOW()
    """, (token,))
    user = cur.fetchone()

    if not user:
        return "Invalid or expired token"

    if request.method == "POST":
        new_pass = request.form["password"]
        confirm = request.form["confirm_password"]
        
        if new_pass != confirm:
            return render_template("reset_password.html",
                                token=token,
                                error="Passwords do not match.")
        
        if not is_valid_password(new_pass):
            return render_template("reset_password.html", 
                                   token = token,
                                   error="Passwords must contain at least 1 upper case letter,"
                                        "1 special character and be at least 8 characters long.")
        
        hashed = hash_password(new_pass)

        cur.execute("""
            UPDATE users
            SET password_hash=%s, reset_token=NULL, reset_token_expiry=NULL
            WHERE id=%s
        """, (hashed, user[0]))
        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("auth.login_get"))

    cur.close()
    conn.close()
    return render_template("reset_password.html", token=token)

