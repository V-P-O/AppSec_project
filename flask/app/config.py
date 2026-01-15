import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    DB_HOST = "127.0.0.1"
    DB_NAME = "app_sec"
    DB_USER = "postgres"
    DB_PASSWORD = "postgres"

    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = os.getenv("SMTP_PORT")

    UPLOAD_FOLDER = "flask/uploads" 
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024   #25 MB

    ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "webp"}  
    ALLOWED_GIF_EXT = {"gif"}                           
    ALLOWED_VIDEO_EXT = {"mp4", "webm"}  

