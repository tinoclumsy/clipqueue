from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from ..auth.decorators import login_required
from ..queries import (
    create_feedback,
    get_active_barbers,
    get_active_faqs,
    get_active_services,
    get_appointment_for_feedback,
    get_approved_feedback,
    get_barber_schedules,
    get_feedback_summary,
    get_shop_settings,
)

# A Blueprint is a group of routes. This one is for the public pages.
main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    # "shop" holds the open/closed status for the Shop Status box
    return render_template("home.html", shop=get_shop_settings())


@main_bp.route("/services")
def services():
    service_list = get_active_services()
    return render_template("services.html", services=service_list)


@main_bp.route("/barbers")
def barbers():
    barber_list = get_active_barbers()
    return render_template("barbers.html", barbers=barber_list)


@main_bp.route("/schedules")
def schedules():
    schedule_list = get_barber_schedules()
    return render_template("schedules.html", schedules=schedule_list)


@main_bp.route("/shop-info")
def shop_info():
    return render_template(
        "shop_info.html",
        shop=get_shop_settings(),
        faqs=get_active_faqs(),
    )


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@main_bp.route("/feedback")
def feedback():
    """The public page: approved feedback and the average rating."""
    return render_template(
        "feedback.html",
        reviews=get_approved_feedback(),
        summary=get_feedback_summary(),
    )


def read_feedback_form(form):
    """Read the feedback form. The rating stays as text for now."""
    return {
        "rating": form.get("rating", "").strip(),
        "comment": form.get("comment", "").strip(),
    }


def check_feedback_form(values):
    """Check the form values. Returns a list of error messages (empty = all good)."""
    errors = []

    rating = values["rating"]
    if not rating.isdecimal() or not 1 <= int(rating) <= 5:
        errors.append("Please choose a rating from 1 to 5.")

    if len(values["comment"]) < 5 or len(values["comment"]) > 1000:
        errors.append("Your comment must be 5 to 1000 characters.")

    return errors


@main_bp.route("/feedback/new/<int:appointment_id>", methods=["GET", "POST"])
@login_required
def feedback_new(appointment_id):
    """The feedback form for ONE completed appointment of the logged-in customer."""
    appointment = get_appointment_for_feedback(appointment_id, session["user_id"])

    # Not this person's appointment, or it is not completed: "Not Found"
    if appointment is None:
        abort(404)

    if appointment["feedback_id"]:
        flash("You already sent feedback for that appointment.", "error")
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        values = read_feedback_form(request.form)
        errors = check_feedback_form(values)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("feedback_form.html", appointment=appointment, values=values)

        saved = create_feedback(session["user_id"], appointment_id, appointment["barber_id"],
                                int(values["rating"]), values["comment"])
        if saved:
            flash("Thank you! Your feedback will appear on the Feedback page after staff review.",
                  "success")
        else:
            flash("You already sent feedback for that appointment.", "error")
        return redirect(url_for("auth.dashboard"))

    values = {"rating": "", "comment": ""}
    return render_template("feedback_form.html", appointment=appointment, values=values)