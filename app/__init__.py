from flask import Flask, render_template, session
from flask_wtf.csrf import CSRFProtect

from config import Config
from .models import User
from .queries import get_user_by_id

# The CSRF protection object. It is connected to the app inside create_app().
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # Copy the settings from config.py into Flask
    app.config.from_object(Config)

    # Stop early, with a clear message, if a required setting is missing or too weak
    for name in ("SECRET_KEY", "DB_PASSWORD"):
        if not app.config.get(name):
            raise RuntimeError(f"Missing setting {name}. Add it to the .env file.")
    if len(app.config["SECRET_KEY"]) < 32:
        raise RuntimeError("SECRET_KEY is too short. Use at least 32 characters.")

    # Turn on CSRF protection for every form that posts
    csrf.init_app(app)

    # Make "currency" available in every template
    @app.context_processor
    def inject_settings():
        return {"currency": app.config["CURRENCY_SYMBOL"]}

    # Make "current_user" available in every template (None if nobody is logged in).
    # It is a User object: a Customer, Staff or Administrator.
    @app.context_processor
    def inject_current_user():
        user = None
        user_id = session.get("user_id")   # set by the login route
        if user_id:
            user = User.from_row(get_user_by_id(user_id))
            if user and not user.is_active:
                user = None                # a deactivated account counts as logged out
        return {"current_user": user}

    # Plug in the "main" Blueprint (the public pages)
    from .main.routes import main_bp
    app.register_blueprint(main_bp)

    # Plug in the "auth" Blueprint (register, login, logout, dashboard)
    from .auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    # Plug in the "booking" Blueprint (choose service, barber, time)
    from .booking.routes import booking_bp
    app.register_blueprint(booking_bp)

    # Plug in the "admin" Blueprint (staff and administrator area)
    from .admin.routes import admin_bp
    app.register_blueprint(admin_bp)

    # Friendly error pages. code -> (title, text)
    error_messages = {
        400: ("Request not accepted", "That request could not be processed. Please go back and try again."),
        403: ("Not allowed", "You do not have permission to open this page."),
        404: ("Page not found", "We could not find the page you asked for."),
        405: ("Not allowed", "That action is not allowed on this page."),
        500: ("Something went wrong", "An error happened on our side. Please try again in a moment."),
    }

    def show_error(error):
        code = getattr(error, "code", 500)
        title, text = error_messages.get(code, error_messages[500])
        return render_template("error.html", code=code, title=title, text=text), code

    for code in error_messages:
        app.register_error_handler(code, show_error)

    # Extra safety headers sent with every page
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"   # the browser must not guess file types
        response.headers["X-Frame-Options"] = "DENY"             # other websites cannot show our pages in a frame
        response.headers["Referrer-Policy"] = "same-origin"      # do not tell other sites which page you came from
        return response

    return app