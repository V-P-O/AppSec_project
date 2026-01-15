from flask import url_for, current_app
from email.mime.text import MIMEText
import secrets
from datetime import datetime, timedelta
import smtplib

def send_token(email):
    send_email = current_app.config["SMTP_EMAIL"]
    send_password = current_app.config["SMTP_PASSWORD"]
    MAIL_HOST = current_app.config["SMTP_HOST"]
    MAIL_PORT = current_app.config["SMTP_PORT"]   

    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=24)
    link = url_for("auth.activate", token=token, _external=True)

    msg = MIMEText(f"Click to activate:\n{link}")
    msg["Subject"] = "Account Activation"
    msg["From"] = send_email
    msg["To"] = email

    with smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()

        smtp.login(
            send_email,
            send_password,
        )
        smtp.send_message(msg)

    return token, expiry

def send_reset_email(email, token):
    send_email = current_app.config["SMTP_EMAIL"]
    send_password = current_app.config["SMTP_PASSWORD"]
    MAIL_HOST = current_app.config["SMTP_HOST"]
    MAIL_PORT = current_app.config["SMTP_PORT"]   

    reset_link = url_for("auth.reset_password", token=token, _external=True)
    body = f"Click this link to reset your password:\n{reset_link}"

    msg = MIMEText(body)
    msg["Subject"] = "Password Reset"
    msg["From"] = send_email
    msg["To"] = email

    with smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()

        smtp.login(send_email, send_password)
        smtp.send_message(msg)
