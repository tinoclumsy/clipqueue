"""Email test. Run it from the project folder, with (venv) on:  python test_email.py"""
import os
import smtplib

from dotenv import load_dotenv

load_dotenv()
user = os.environ.get("MAIL_USERNAME")
password = os.environ.get("MAIL_PASSWORD")
print("Username set:", bool(user), "| Password length:", len(password or ""), "(an App Password has 16)")

print("--- Part A: step by step ---")
try:
    smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
    print("1. connected")
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    print("2. encrypted")
    smtp.login(user, password)
    print("3. logged in")
    smtp.quit()
except Exception as error:
    print("FAILED right after the last OK line:", type(error).__name__, "-", error)

print("--- Part B: send a real email to yourself with Mailer ---")
from app import create_app
from app.emailer import Mailer

app = create_app()
with app.app_context():
    mailer = Mailer.from_app()
    print("Sent:", mailer.send(user, "ClipQueue email test", "If you can read this, email works."))