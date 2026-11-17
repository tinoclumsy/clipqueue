from functools import wraps

from flask import abort, flash, redirect, session, url_for

from ..models import User
from ..queries import get_user_by_id


def current_user_object():
    """The logged-in User object, or None if nobody is logged in or the account is switched off."""
    user_id = session.get("user_id")
    user = User.from_row(get_user_by_id(user_id)) if user_id else None
    if user is None or not user.is_active:
        return None
    return user


def login_required(view):
    """Put @login_required above a route to block people who are not logged in."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        # Not logged in, or the account was deactivated
        if current_user_object() is None:
            session.clear()
            flash("Please log in to see that page.", "error")
            return redirect(url_for("auth.login"))

        # Logged in: run the real page
        return view(*args, **kwargs)

    return wrapped_view


def role_required(*allowed_roles):
    """Put @role_required("administrator", "staff") above a route.
    Only logged-in people with one of those roles can open the page."""

    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user = current_user_object()

            # Not logged in, or deactivated: send to login
            if user is None:
                session.clear()
                flash("Please log in to see that page.", "error")
                return redirect(url_for("auth.login"))

            # Logged in but the wrong role: "Forbidden"
            if not user.has_role(*allowed_roles):
                abort(403)

            return view(*args, **kwargs)

        return wrapped_view

    return decorator