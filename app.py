from flask import Flask, render_template, request, redirect, url_for
import psycopg2
import bcrypt
import re

app = Flask(__name__)

password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
username_pattern = r'^[A-Za-z0-9_]{3,}$'

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
    return "index"

@app.route("/login", methods=["GET"])
def login_get():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    username = request.form["username"]
    password = request.form["password"]

    password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
    username_pattern = r'^[A-Za-z0-9_]{3,}$'

    if re.match(username_pattern, username):
        conn = get_db_connection()
        cur = conn.cursor()
    
        cur.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        cur.close()
        conn.close()
    else:
        return render_template("login.html", error="Invalid username or password")
    
    if user and check_password(password, user[0]):
        return "Login successful!"
    else:
        return render_template("login.html", error="Invalid username or password")

@app.route("/register", methods=["GET"])
def register_get():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register_post():
    username = request.form["username"]
    password = request.form["password"]
    password_r = request.form["password_r"]


    if re.match(username_pattern, username):
        
        conn = get_db_connection()
        cur = conn.cursor()
    
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
    
        cur.close()
        conn.close()
    else:
        return render_template("register.html", error="Passwords must contain at least 1 upper case letter, 1 special character and be at least 8 characters long.\n"
                                                      "Usernames can only contain letters, numbers and underscore.")

    if not user:
        if password == password_r:
            
            if re.match(password_pattern, password):
                
                hashed = hash_password(password)
    
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                    (username, hashed)
                )
                conn.commit()
                cur.close()
                conn.close()
                return "Register successful!"
            else:
                return render_template("register.html", error="Passwords must contain at least 1 upper case letter, 1 special character and be at least 8 characters long.\n"
                                                              "Usernames can only contain letters, numbers and underscore.")
        else:
            return render_template("register.html", error="Passwords are not matching.")
    else:
        return render_template("register.html", error="Username taken.")

app.run(host = "127.0.0.1", port = 8080)
