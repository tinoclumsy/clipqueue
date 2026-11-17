"""Create a staff or administrator account.

Run it from the project folder, with (venv) on:
    python create_staff.py
"""
from getpass import getpass

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import execute_write
from app.queries import get_user_by_email

app = create_app()

# db.py needs Flask's settings, so we open an "app context" ourselves
with app.app_context():
    print("Create a staff or administrator account")
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip().lower()
    role = input("Role (administrator or staff): ").strip().lower()
    password = getpass("Password (at least 8 characters, hidden while you type): ")

    # Check the input (same ideas as the register page)
    if len(full_name) < 2 or len(full_name) > 100:
        raise SystemExit("Stopped: the name must be 2 to 100 characters.")
    if "@" not in email or "." not in email or len(email) > 120:
        raise SystemExit("Stopped: that email does not look valid.")
    if role not in ("administrator", "staff"):
        raise SystemExit("Stopped: the role must be administrator or staff.")
    if len(password) < 8:
        raise SystemExit("Stopped: the password must be at least 8 characters.")
    if get_user_by_email(email):
        raise SystemExit("Stopped: that email is already registered.")

    execute_write(
        "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        (full_name, email, generate_password_hash(password), role),
    )
    print(f"Done. {role} account created for {email}.")