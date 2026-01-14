from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import bcrypt
import re
import secrets
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
from functools import wraps

load_dotenv()

app = Flask(__name__)

password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
username_pattern = r'^[A-Za-z0-9_]{3,}$'
email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

app.secret_key = os.getenv("SECRET_KEY") 
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Stricpip install pyopensslt"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)

send_email = os.getenv("SMTP_EMAIL")
send_password = os.getenv("SMTP_PASSWORD")

def get_db_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        database="app_sec",
        user="postgres",
        password="postgres"
    )

def hash_password(plain_password):
    hashed = bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt())
    return hashed.decode('utf-8')

def check_password(plain_password, stored_hash):
    return bcrypt.checkpw(plain_password.encode('utf-8'), stored_hash.encode('utf-8'))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET"])
def login_get():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    username = request.form["username"]
    password = request.form["password"]

    password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
    username_pattern = r'^[A-Za-z0-9_]{3,}$'

    if re.match(username_pattern, username) or re.match(email_pattern, username):
        conn = get_db_connection()
        cur = conn.cursor()
    
        cur.execute("""
                SELECT password_hash, is_activated, email, activation_token, id, username 
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
        
        session.clear()
        session.modified = True
        session["user_id"] = user[4]
        session["username"] = user[5]
        
        if request.form.get("remember_me"):
            session.permanent = True 
        else:
            session.permanent = False
        
        return redirect(url_for("index"))
    else:
        return render_template("login.html", error="Invalid username or password")

@app.route("/register", methods=["GET"])
def register_get():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register_post():
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]
    password_r = request.form["password_r"]

    if not re.match(email_pattern, email):
        return render_template("register.html", error="Invalid email format.")
    
    if re.match(username_pattern, username):
        
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
            
            if re.match(password_pattern, password):
                
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

@app.route("/activate")
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

@app.route("/resend_activation")
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

def send_token(email):
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=24)
    
    activate_link = url_for("activate", token=token, _external=True)
    
    msg = MIMEText(f"Click to activate your account:\n\n{activate_link}")
    msg["Subject"] = "Account Activation"
    msg["From"] = send_email
    msg["To"] = email
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(send_email, send_password)
        smtp.send_message(msg)
    
    return token, expiry

@app.route("/logout")
def logout():
    session.clear()
    session.modified = True
    return redirect(url_for("index"))

def send_reset_email(email, token):
    reset_link = url_for("reset_password", token=token, _external=True)
    body = f"Click this link to reset your password:\n{reset_link}"

    msg = MIMEText(body)
    msg["Subject"] = "Password Reset"
    msg["From"] = send_email
    msg["To"] = email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(send_email, send_password)
        smtp.send_message(msg)


@app.route("/forgot-password", methods=["GET", "POST"])
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


@app.route("/reset-password/<token>", methods=["GET", "POST"])
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
        
        if not re.match(password_pattern, new_pass):
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

        return redirect(url_for("login_get"))

    cur.close()
    conn.close()
    return render_template("reset_password.html", token=token)


app.run(host = "127.0.0.1", port = 8080)
