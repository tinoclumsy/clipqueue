import secrets
from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from ..emailer import Mailer

from ..auth.decorators import login_required
from ..queries import (
    cancel_appointment,
    count_bookings_on,
    create_appointment,
    get_active_services,
    get_appointment_by_reference,
    get_barbers_for_service,
    get_service_by_id,
    is_shop_open,
    get_user_by_id,
)
from .slots import get_free_slots, minutes_to_label, minutes_to_sql

# url_prefix means every route in this Blueprint starts with /book
booking_bp = Blueprint("booking", __name__, url_prefix="/book")

DAYS_AHEAD = 30   # customers can book up to 30 days from today

# Letters and digits for booking references (no O, 0, I or 1, so they are easy to read)
REFERENCE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def shop_closed_redirect():
    """If the shop is closed, tell the customer and return a redirect to the Shop Info page.
    If the shop is open, return None, and the booking step carries on."""
    if is_shop_open():
        return None
    flash("The shop is closed right now, so new bookings are paused. Please check back soon.", "error")
    return redirect(url_for("main.shop_info"))


def parse_booking_date(text):
    """Turn '2026-11-15' into a date. Return None if it is invalid, in the past, or too far ahead."""
    try:
        the_date = date.fromisoformat(text)
    except ValueError:
        return None
    today = date.today()
    if the_date < today or the_date > today + timedelta(days=DAYS_AHEAD):
        return None
    return the_date


def make_reference():
    """Make a booking reference like CQ8F3K2A2 that no other appointment uses."""
    while True:
        reference = "CQ" + "".join(secrets.choice(REFERENCE_CHARS) for _ in range(8))
        if get_appointment_by_reference(reference) is None:
            return reference


def get_candidate_barbers(service, barber_choice):
    """The barbers who could take this booking.
    'any' = every barber who offers the service. A number = only that barber (if he offers it)."""
    barbers = get_barbers_for_service(service["id"])
    if barber_choice == "any":
        return barbers
    if barber_choice.isdecimal():
        return [b for b in barbers if b["id"] == int(barber_choice)]
    return []


@booking_bp.route("/")
@login_required
def choose_service():
    """Page 1: the customer picks a service."""
    closed = shop_closed_redirect()
    if closed:
        return closed

    return render_template("book_service.html", services=get_active_services())


@booking_bp.route("/details")
@login_required
def choose_barber_and_date():
    """Page 2: the customer picks a barber and a date for the chosen service."""
    closed = shop_closed_redirect()
    if closed:
        return closed

    service_id = request.args.get("service_id", type=int)
    service = get_service_by_id(service_id) if service_id else None

    if service is None:
        flash("Please choose a service first.", "error")
        return redirect(url_for("booking.choose_service"))

    today = date.today()
    return render_template(
        "book_details.html",
        service=service,
        barbers=get_barbers_for_service(service["id"]),
        min_date=today.isoformat(),
        max_date=(today + timedelta(days=DAYS_AHEAD)).isoformat(),
    )


@booking_bp.route("/times")
@login_required
def choose_time():
    """Page 3 (8B): show the free times."""
    closed = shop_closed_redirect()
    if closed:
        return closed

    service_id = request.args.get("service_id", type=int)
    barber_choice = request.args.get("barber_id", "any")
    date_text = request.args.get("date", "")

    service = get_service_by_id(service_id) if service_id else None
    if service is None:
        flash("Please choose a service first.", "error")
        return redirect(url_for("booking.choose_service"))

    the_date = parse_booking_date(date_text)
    candidates = get_candidate_barbers(service, barber_choice)
    if the_date is None or not candidates:
        flash("Please choose a barber and a valid date (today up to 30 days ahead).", "error")
        return redirect(url_for("booking.choose_barber_and_date", service_id=service["id"]))

    # Collect every start time that is free for at least one candidate barber
    starts = set()
    for barber in candidates:
        starts.update(get_free_slots(barber["id"], service, the_date))

    times = [{"value": start, "label": minutes_to_label(start)} for start in sorted(starts)]
    barber_label = "Any available barber" if barber_choice == "any" else candidates[0]["display_name"]

    return render_template(
        "book_times.html",
        service=service,
        times=times,
        barber_choice=barber_choice,
        barber_label=barber_label,
        date_iso=the_date.isoformat(),
        date_label=the_date.strftime("%A, %d %B %Y"),
    )


@booking_bp.route("/create", methods=["POST"])
@login_required
def create():
    """(8C) Save the appointment, after checking again that the time is still free."""
    # The shop may have closed while the customer was choosing a time
    closed = shop_closed_redirect()
    if closed:
        return closed

    service_id = request.form.get("service_id", type=int)
    barber_choice = request.form.get("barber_id", "any")
    date_text = request.form.get("date", "")
    start = request.form.get("start", type=int)   # minutes since midnight

    service = get_service_by_id(service_id) if service_id else None
    the_date = parse_booking_date(date_text)
    if service is None or the_date is None or start is None:
        flash("Something was wrong with that booking. Please try again.", "error")
        return redirect(url_for("booking.choose_service"))

    # Check again: which candidate barbers are STILL free at this exact start time?
    candidates = get_candidate_barbers(service, barber_choice)
    free_barbers = [b for b in candidates
                    if start in get_free_slots(b["id"], service, the_date)]

    if not free_barbers:
        flash("Sorry, that time is no longer available. Please choose another time.", "error")
        return redirect(url_for("booking.choose_time", service_id=service["id"],
                                barber_id=barber_choice, date=the_date.isoformat()))

    # (8F) The rule: among the free barbers, take the one with the fewest bookings that day.
    # If a specific barber was chosen, there is only one barber in the list.
    chosen = min(free_barbers, key=lambda b: count_bookings_on(b["id"], the_date))

    end = start + service["duration_minutes"]
    reference = make_reference()
    create_appointment(
        reference,
        session["user_id"],
        chosen["id"],
        service["id"],
        the_date,
        minutes_to_sql(start),
        minutes_to_sql(end),
    )

        # Email the customer a confirmation
    customer = get_user_by_id(session["user_id"])
    Mailer.from_app().send_booking_confirmation(
        customer["full_name"],
        customer["email"],
        {
            "reference": reference,
            "service_name": service["name"],
            "barber_name": chosen["display_name"],
            "date_label": the_date.strftime("%A, %d %B %Y"),
            "time_label": f"{minutes_to_label(start)} - {minutes_to_label(end)}",
        },
    )
    return redirect(url_for("booking.confirmation", reference=reference))


@booking_bp.route("/confirmation/<reference>")
@login_required
def confirmation(reference):
    """(8D) Show the booking details and the reference number."""
    appointment = get_appointment_by_reference(reference)
    # Only the owner may see it. Everyone else gets "Not Found".
    if appointment is None or appointment["customer_id"] != session["user_id"]:
        abort(404)
    return render_template("book_confirmation.html", appointment=appointment)


@booking_bp.route("/cancel/<int:appointment_id>", methods=["POST"])
@login_required
def cancel(appointment_id):
    """(8E) Cancel one of the logged-in customer's own appointments.
    This is allowed even when the shop is closed."""
    changed = cancel_appointment(appointment_id, session["user_id"])
    if changed:
        flash("Your appointment has been cancelled.", "success")
    else:
        flash("That appointment could not be cancelled.", "error")
    return redirect(url_for("auth.dashboard"))