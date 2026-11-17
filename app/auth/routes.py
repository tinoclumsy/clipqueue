from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..emailer import Mailer
from ..models import Appointment, User
from ..queries import (
    create_customer,
    get_customer_appointments,
    get_user_by_email,
    get_user_by_id,
    get_user_password_hash,
    update_user_password,
    update_user_profile,
)
from .decorators import login_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Read what the person typed. strip() removes extra spaces at the ends.
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        # Check the input and collect any problems
        errors = []
        if len(full_name) < 2 or len(full_name) > 100:
            errors.append("Please enter your full name (2 to 100 characters).")
        if "@" not in email or "." not in email or len(email) > 120:
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Your password must be at least 8 characters.")
        if password != confirm:
            errors.append("The two passwords do not match.")
        if not errors and get_user_by_email(email):
            errors.append("That email is already registered.")

        if errors:
            for message in errors:
                flash(message, "error")
            # Show the form again, keeping what they typed (but never the password)
            return render_template("register.html", full_name=full_name, email=email)

        # All good: save the account with a HASHED password
        create_customer(full_name, email, generate_password_hash(password))
        Mailer.from_app().send_welcome(full_name, email)
        flash("Account created. You can log in now.", "success")
        return redirect(url_for("auth.login"))

    # GET request: just show the empty form
    return render_template("register.html", full_name="", email="")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Build a User object (a Customer, Staff or Administrator) from the database row
        user = User.from_row(get_user_by_email(email))
        if user and user.is_active and user.verify_password(password):
            session.clear()                  # start from a clean session
            session["user_id"] = user.id     # remember who logged in
            flash(f"Welcome, {user.full_name}!", "success")

            # Each kind of user knows its own home page (polymorphism)
            return redirect(url_for(user.home_endpoint()))

        # Same message for a wrong email or a wrong password, on purpose
        flash("Wrong email or password.", "error")
        return render_template("login.html", email=email)

    return render_template("login.html", email="")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("main.home"))


@auth_bp.route("/dashboard")
@login_required
def dashboard():
    # Each database row becomes an Appointment object
    appointments = [Appointment.from_row(row)
                    for row in get_customer_appointments(session["user_id"])]
    today = date.today()

    # Upcoming = still active (pending or confirmed) and not in the past.
    # The Appointment object knows this rule itself.
    upcoming = [a for a in appointments if a.is_upcoming(today)]
    # Everything else is "past": completed, cancelled, or already over
    past = [a for a in appointments if a not in upcoming]

    # The query lists newest first, but upcoming ones read better soonest first
    upcoming.sort(key=lambda a: (a["appointment_date"], a["start_time"]))

    return render_template("dashboard.html", upcoming=upcoming, past=past)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """The logged-in person sees and changes their own name and email."""
    user = get_user_by_id(session["user_id"])

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        errors = []
        if len(full_name) < 2 or len(full_name) > 100:
            errors.append("Please enter your full name (2 to 100 characters).")
        if "@" not in email or "." not in email or len(email) > 120:
            errors.append("Please enter a valid email address.")
        else:
            other = get_user_by_email(email)
            if other and other["id"] != user["id"]:
                errors.append("That email is already used by another account.")

        if errors:
            for message in errors:
                flash(message, "error")
            # Show the form again, keeping what they typed
            return render_template("profile.html", full_name=full_name, email=email, user=user)

        update_user_profile(user["id"], full_name, email)
        flash("Your details have been saved.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("profile.html", full_name=user["full_name"],
                           email=user["email"], user=user)


@auth_bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    """The logged-in person changes their own password."""
    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")

    errors = []
    stored_hash = get_user_password_hash(session["user_id"])
    if not stored_hash or not check_password_hash(stored_hash, current):
        errors.append("Your current password is not correct.")
    if len(new_password) < 8:
        errors.append("Your new password must be at least 8 characters.")
    elif new_password != confirm:
        errors.append("The two new passwords do not match.")
    elif new_password == current:
        errors.append("Your new password must be different from the current one.")

    if errors:
        for message in errors:
            flash(message, "error")
        return redirect(url_for("auth.profile"))   # passwords are never shown again

    update_user_password(session["user_id"], generate_password_hash(new_password))
    flash("Your password has been changed.", "success")
    return redirect(url_for("auth.profile"))