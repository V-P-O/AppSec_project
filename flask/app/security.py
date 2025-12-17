import bcrypt
import re

password_pattern = r'^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$'
username_pattern = r'^[A-Za-z0-9_]{3,}$'
email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

def hash_password(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_password(pw, stored):
    return bcrypt.checkpw(pw.encode(), stored.encode())

def is_valid_email(email: str) -> bool:
    return bool(re.match(email_pattern, email))

def is_valid_username(username: str) -> bool:
    return bool(re.match(username_pattern, username))

def is_valid_password(password: str) -> bool:
    return bool(re.match(password_pattern, password))

