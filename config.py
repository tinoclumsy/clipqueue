import os
from pathlib import Path

from dotenv import load_dotenv

# Find the folder this file is in (C:\ClipQueue) and load the .env file from it
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # Database settings (the password comes from .env, never from the code)
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_NAME = os.environ.get("DB_NAME", "clipqueue_db")
    DB_USER = os.environ.get("DB_USER", "clipqueue_user")
    DB_PASSWORD = os.environ.get("DB_PASSWORD")

    # Used to sign the login cookie (the "session"). It comes from .env.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Email (SMTP) settings. The login details come from .env
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    
    # Safety settings for the login cookie
    SESSION_COOKIE_HTTPONLY = True    # JavaScript on a page cannot read the cookie
    SESSION_COOKIE_SAMESITE = "Lax"   # the cookie is not sent with requests from other websites

    # Symbol shown before prices. "\u20b1" is the peso sign.
    # Change it here if the shop uses another currency.
    CURRENCY_SYMBOL = "\u20b1"