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

load_dotenv()

app = Flask(__name__)

password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
username_pattern = r'^[A-Za-z0-9_]{3,}$'
email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

app.secret_key = os.getenv("SECRET_KEY") 

def get_db_connection():
    return psycopg2.connect(
        host="127.0.0.1",
        database="postgres",
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
        
        session["user_id"] = user[4]
        session["username"] = user[5]
        
        return "Login successful!"
    else:
        return render_template("login.html", error="Invalid username or password")

@app.route("/register", methods=["GET"])
def register_get():
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
                return "Register successful!"
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
    send_email = os.getenv("SMTP_EMAIL")
    send_password = os.getenv("SMTP_PASSWORD")
    
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=24)
    
    msg = MIMEText(f"Click to activate your account:\n\nhttp://127.0.0.1:8080/activate?token={token}")
    msg["Subject"] = "Account Activation"
    msg["From"] = send_email
    msg["To"] = email
    
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(send_email, send_password)
        smtp.send_message(msg)
    
    return token, expiry

app.run(host = "127.0.0.1", port = 8080)
