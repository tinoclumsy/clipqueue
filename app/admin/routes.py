from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from ..emailer import Mailer

from ..auth.decorators import role_required
from ..queries import (
    DAY_NAMES,
    change_appointment_status,
    create_barber,
    create_faq,
    create_service,
    create_staff_account,
    get_active_barbers,
    get_admin_counts,
    get_all_barbers,
    get_all_faqs,
    get_all_services,
    get_all_specialties,
    get_appointment_by_id,
    get_appointments_filtered,
    get_appointments_for_date,
    get_appointment_email_info,
    get_barber_for_admin,
    get_barber_service_ids,
    get_barber_specialty_ids,
    get_barber_week,
    get_customers_for_admin,
    get_faq_for_admin,
    get_next_faq_order,
    get_service_for_admin,
    get_shop_settings,
    get_staff_for_admin,
    get_user_by_email,
    get_user_by_id,
    service_name_taken,
    set_barber_active,
    set_barber_services,
    set_barber_specialties,
    set_barber_week,
    set_faq_active,
    set_service_active,
    set_shop_status,
    set_user_active,
    update_barber,
    update_faq,
    update_service,
    update_shop_info,
    get_feedback_by_id,
    get_feedback_for_admin,
    set_feedback_status,
    count_appointments_for_barber,
    count_appointments_for_service,
    delete_barber,
    delete_faq,
    delete_service,
)

# Every route in this Blueprint starts with /admin
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

STATUSES = ("pending", "confirmed", "completed", "cancelled")

# action name -> (new status, the statuses it may change FROM)
ACTIONS = {
    "confirm":  ("confirmed", ("pending",)),
    "complete": ("completed", ("confirmed",)),
    "cancel":   ("cancelled", ("pending", "confirmed")),
}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/")
@role_required("administrator", "staff")
def dashboard():
    return render_template(
        "admin_dashboard.html",
        counts=get_admin_counts(),
        todays=get_appointments_for_date(date.today()),
    )


# ---------------------------------------------------------------------------
# Appointments (staff and administrators)
# ---------------------------------------------------------------------------

def clean_filters(values):
    """Read the filter fields from request.args or request.form.
    Keep only the valid ones, so bad input is simply ignored."""
    cleaned = {}

    status = values.get("status", "")
    if status in STATUSES:
        cleaned["status"] = status

    date_text = values.get("date", "")
    try:
        date.fromisoformat(date_text)
        cleaned["date"] = date_text
    except ValueError:
        pass

    barber_id = values.get("barber_id", "")
    if barber_id.isdecimal():
        cleaned["barber_id"] = barber_id

    if values.get("past") == "1":
        cleaned["past"] = "1"

    return cleaned


@admin_bp.route("/appointments")
@role_required("administrator", "staff")
def appointments():
    filters = clean_filters(request.args)

    rows = get_appointments_filtered(
        status=filters.get("status"),
        on_date=filters.get("date"),
        barber_id=int(filters["barber_id"]) if "barber_id" in filters else None,
        include_past="past" in filters,
    )
    return render_template(
        "admin_appointments.html",
        appointments=rows,
        filters=filters,
        barbers=get_active_barbers(),
        statuses=STATUSES,
        today=date.today(),
    )


@admin_bp.route("/appointments/<int:appointment_id>/<action>", methods=["POST"])
@role_required("administrator", "staff")
def appointment_action(appointment_id, action):
    """Confirm, complete or cancel one appointment."""
    if action not in ACTIONS:
        abort(404)
    new_status, allowed_from = ACTIONS[action]

    appointment = get_appointment_by_id(appointment_id)
    if appointment is None:
        abort(404)

    reference = appointment["booking_reference"]

    if action == "complete" and appointment["appointment_date"] > date.today():
        flash("You can only complete an appointment on or after its date.", "error")
    elif change_appointment_status(appointment_id, new_status, allowed_from):
        flash(f"Appointment {reference} is now {new_status}.", "success")

        # Tell the customer by email when their appointment is confirmed or cancelled
        if action in ("confirm", "cancel"):
            info = get_appointment_email_info(appointment_id)
            if info:
                Mailer.from_app().send_status_update(
                    info["customer_name"], info["customer_email"], info, new_status)
    else:
        flash("That change is not allowed for this appointment.", "error")

    # Go back to the list with the same filters the person had
    return redirect(url_for("admin.appointments", **clean_filters(request.form)))

# ---------------------------------------------------------------------------
# Shop status and info (staff can change the status, administrators the info)
# ---------------------------------------------------------------------------

def shop_info_values(shop):
    """The shop info fields as plain text, ready to fill the form."""
    return {
        "about_text": shop["about_text"] or "",
        "address": shop["address"] or "",
        "phone": shop["phone"] or "",
        "email": shop["email"] or "",
        "hours_text": shop["hours_text"] or "",
    }


def read_shop_info_form(form):
    """Read the shop info form. strip() removes extra spaces at the ends."""
    return {
        "about_text": form.get("about_text", "").strip(),
        "address": form.get("address", "").strip(),
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip(),
        "hours_text": form.get("hours_text", "").strip(),
    }


def check_shop_info_form(values):
    """Check the form values. Returns a list of error messages (empty = all good)."""
    errors = []

    if len(values["about_text"]) > 2000:
        errors.append("The about text is too long (maximum 2000 characters).")

    if len(values["address"]) > 255:
        errors.append("The address is too long (maximum 255 characters).")

    phone = values["phone"]
    if len(phone) > 40:
        errors.append("The phone number is too long (maximum 40 characters).")
    elif not all(c.isdigit() or c in " +-()" for c in phone):
        errors.append("The phone number can only have digits, spaces, + - and ( ).")

    email = values["email"]
    if email and ("@" not in email or "." not in email or len(email) > 120):
        errors.append("Please enter a valid email address, or leave it empty.")

    if len(values["hours_text"]) > 255:
        errors.append("The opening hours text is too long (maximum 255 characters).")

    return errors


@admin_bp.route("/shop")
@role_required("administrator", "staff")
def shop():
    settings = get_shop_settings()
    info = shop_info_values(settings) if settings else None
    return render_template("admin_shop.html", shop=settings, info=info)


@admin_bp.route("/shop/status", methods=["POST"])
@role_required("administrator", "staff")
def shop_status():
    """Switch the shop open or closed, with an optional short note."""
    state = request.form.get("state", "")
    note = request.form.get("status_note", "").strip()

    if state not in ("open", "closed"):
        flash("Please choose Open or Closed.", "error")
    elif len(note) > 255:
        flash("The note is too long (maximum 255 characters).", "error")
    else:
        set_shop_status(state == "open", note)
        flash(f"The shop is now {state}.", "success")

    return redirect(url_for("admin.shop"))


@admin_bp.route("/shop/info", methods=["POST"])
@role_required("administrator")
def shop_info_save():
    """Save the about text and contact details. Administrators only."""
    settings = get_shop_settings()
    if settings is None:
        abort(404)

    values = read_shop_info_form(request.form)
    errors = check_shop_info_form(values)
    if errors:
        for message in errors:
            flash(message, "error")
        # Show the page again with what the person typed
        return render_template("admin_shop.html", shop=settings, info=values)

    update_shop_info(values["about_text"], values["address"], values["phone"],
                     values["email"], values["hours_text"])
    flash("Shop info saved.", "success")
    return redirect(url_for("admin.shop"))


# ---------------------------------------------------------------------------
# FAQs (administrators only)
# ---------------------------------------------------------------------------

def read_faq_form(form):
    """Read the FAQ form. Everything stays as text for now."""
    return {
        "question": form.get("question", "").strip(),
        "answer": form.get("answer", "").strip(),
        "sort_order": form.get("sort_order", "").strip(),
    }


def check_faq_form(values):
    """Check the form values. Returns a list of error messages (empty = all good)."""
    errors = []

    if len(values["question"]) < 5 or len(values["question"]) > 200:
        errors.append("The question must be 5 to 200 characters.")

    if len(values["answer"]) < 5 or len(values["answer"]) > 2000:
        errors.append("The answer must be 5 to 2000 characters.")

    order = values["sort_order"]
    if not order.isdecimal() or not 1 <= int(order) <= 9999:
        errors.append("The display order must be a whole number from 1 to 9999.")

    return errors


@admin_bp.route("/faqs")
@role_required("administrator")
def faqs():
    return render_template("admin_faqs.html", faqs=get_all_faqs())


@admin_bp.route("/faqs/new", methods=["GET", "POST"])
@role_required("administrator")
def faq_new():
    if request.method == "POST":
        values = read_faq_form(request.form)
        errors = check_faq_form(values)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin_faq_form.html", values=values, title="Add a FAQ")

        create_faq(values["question"], values["answer"], int(values["sort_order"]))
        flash("FAQ added.", "success")
        return redirect(url_for("admin.faqs"))

    # A new FAQ goes last, unless the administrator changes the number
    values = {"question": "", "answer": "", "sort_order": str(get_next_faq_order())}
    return render_template("admin_faq_form.html", values=values, title="Add a FAQ")


@admin_bp.route("/faqs/<int:faq_id>/edit", methods=["GET", "POST"])
@role_required("administrator")
def faq_edit(faq_id):
    faq = get_faq_for_admin(faq_id)
    if faq is None:
        abort(404)

    if request.method == "POST":
        values = read_faq_form(request.form)
        errors = check_faq_form(values)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin_faq_form.html", values=values, title="Edit FAQ")

        update_faq(faq_id, values["question"], values["answer"], int(values["sort_order"]))
        flash("FAQ saved.", "success")
        return redirect(url_for("admin.faqs"))

    values = {
        "question": faq["question"],
        "answer": faq["answer"],
        "sort_order": str(faq["sort_order"]),
    }
    return render_template("admin_faq_form.html", values=values, title="Edit FAQ")


@admin_bp.route("/faqs/<int:faq_id>/toggle", methods=["POST"])
@role_required("administrator")
def faq_toggle(faq_id):
    """Show or hide a FAQ on the Shop Info page. We never delete FAQs."""
    faq = get_faq_for_admin(faq_id)
    if faq is None:
        abort(404)

    now_active = not faq["is_active"]
    set_faq_active(faq_id, now_active)
    state = "shown" if now_active else "hidden"
    flash(f"That FAQ is now {state}.", "success")
    return redirect(url_for("admin.faqs"))


# ---------------------------------------------------------------------------
# Services (administrators only)
# ---------------------------------------------------------------------------

def read_service_form(form):
    """Read the service form. Everything stays as text for now."""
    return {
        "name": form.get("name", "").strip(),
        "description": form.get("description", "").strip(),
        "price": form.get("price", "").strip(),
        "duration_minutes": form.get("duration_minutes", "").strip(),
    }


def check_service_form(values, service_id=0):
    """Check the form values. Returns a list of error messages (empty = all good).
    service_id is the service being edited (0 when adding a new one)."""
    errors = []

    name = values["name"]
    if len(name) < 2 or len(name) > 100:
        errors.append("The name must be 2 to 100 characters.")
    elif service_name_taken(name, service_id):
        errors.append("Another service already has that name.")

    if len(values["description"]) > 1000:
        errors.append("The description is too long (maximum 1000 characters).")

    try:
        price = Decimal(values["price"])
    except InvalidOperation:
        price = None
    if price is None or not price.is_finite() or price < 0 or price > Decimal("99999.99"):
        errors.append("The price must be a number from 0 to 99999.99.")
    elif price != price.quantize(Decimal("0.01")):
        errors.append("The price can have at most 2 decimal places.")

    duration = values["duration_minutes"]
    if not duration.isdecimal() or not 5 <= int(duration) <= 480:
        errors.append("The duration must be a whole number of minutes from 5 to 480.")

    return errors


@admin_bp.route("/services")
@role_required("administrator")
def services():
    return render_template("admin_services.html", services=get_all_services())


@admin_bp.route("/services/new", methods=["GET", "POST"])
@role_required("administrator")
def service_new():
    if request.method == "POST":
        values = read_service_form(request.form)
        errors = check_service_form(values)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin_service_form.html", values=values, title="Add a service")

        create_service(values["name"], values["description"],
                       Decimal(values["price"]), int(values["duration_minutes"]))
        flash("Service added.", "success")
        return redirect(url_for("admin.services"))

    values = {"name": "", "description": "", "price": "", "duration_minutes": "30"}
    return render_template("admin_service_form.html", values=values, title="Add a service")


@admin_bp.route("/services/<int:service_id>/edit", methods=["GET", "POST"])
@role_required("administrator")
def service_edit(service_id):
    service = get_service_for_admin(service_id)
    if service is None:
        abort(404)

    if request.method == "POST":
        values = read_service_form(request.form)
        errors = check_service_form(values, service_id)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin_service_form.html", values=values, title="Edit service")

        update_service(service_id, values["name"], values["description"],
                       Decimal(values["price"]), int(values["duration_minutes"]))
        flash("Service saved.", "success")
        return redirect(url_for("admin.services"))

    values = {
        "name": service["name"],
        "description": service["description"] or "",
        "price": f"{service['price']:.2f}",
        "duration_minutes": str(service["duration_minutes"]),
    }
    return render_template("admin_service_form.html", values=values, title="Edit service")


@admin_bp.route("/services/<int:service_id>/toggle", methods=["POST"])
@role_required("administrator")
def service_toggle(service_id):
    """Switch a service on or off. We never delete services."""
    service = get_service_for_admin(service_id)
    if service is None:
        abort(404)

    now_active = not service["is_active"]
    set_service_active(service_id, now_active)
    state = "active" if now_active else "inactive"
    flash(f"{service['name']} is now {state}.", "success")
    return redirect(url_for("admin.services"))


# ---------------------------------------------------------------------------
# Barbers (administrators only)
# ---------------------------------------------------------------------------

BARBER_TYPES = ("owner", "independent")


def read_barber_form(form):
    """Read the barber form. Everything stays as text for now."""
    return {
        "display_name": form.get("display_name", "").strip(),
        "bio": form.get("bio", "").strip(),
        "barber_type": form.get("barber_type", ""),
    }


def check_barber_form(values):
    """Check the form values. Returns a list of error messages (empty = all good)."""
    errors = []

    if len(values["display_name"]) < 2 or len(values["display_name"]) > 100:
        errors.append("The name must be 2 to 100 characters.")

    if len(values["bio"]) > 1000:
        errors.append("The bio is too long (maximum 1000 characters).")

    if values["barber_type"] not in BARBER_TYPES:
        errors.append("Please choose a barber type.")

    return errors


def read_barber_links(form):
    """Read the ticked service and specialty checkboxes.
    We only keep ids that really exist, so a fake id is ignored."""
    valid_services = {s["id"] for s in get_all_services()}
    valid_specialties = {sp["id"] for sp in get_all_specialties()}

    ticked_services = {int(x) for x in form.getlist("service_ids") if x.isdecimal()}
    ticked_specialties = {int(x) for x in form.getlist("specialty_ids") if x.isdecimal()}

    # "&" keeps only the ids found in BOTH sets.
    # Example: {1, 2, 99} & {1, 2, 3} gives {1, 2}
    return ticked_services & valid_services, ticked_specialties & valid_specialties


def render_barber_edit(values, chosen_services, chosen_specialties):
    """Show the edit page. One place for it, so barber_edit stays short."""
    return render_template(
        "admin_barber_form.html",
        values=values,
        title="Edit barber",
        barber_types=BARBER_TYPES,
        services=get_all_services(),
        specialties=get_all_specialties(),
        chosen_services=chosen_services,
        chosen_specialties=chosen_specialties,
    )


@admin_bp.route("/barbers")
@role_required("administrator")
def barbers():
    return render_template("admin_barbers.html", barbers=get_all_barbers())


@admin_bp.route("/barbers/new", methods=["GET", "POST"])
@role_required("administrator")
def barber_new():
    if request.method == "POST":
        values = read_barber_form(request.form)
        errors = check_barber_form(values)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin_barber_form.html", values=values,
                                   title="Add a barber", barber_types=BARBER_TYPES)

        create_barber(values["display_name"], values["bio"], values["barber_type"])
        flash("Barber added. Click Edit to choose their services and specialties, "
              "and Schedule to set their hours.", "success")
        return redirect(url_for("admin.barbers"))

    values = {"display_name": "", "bio": "", "barber_type": "independent"}
    return render_template("admin_barber_form.html", values=values,
                           title="Add a barber", barber_types=BARBER_TYPES)


@admin_bp.route("/barbers/<int:barber_id>/edit", methods=["GET", "POST"])
@role_required("administrator")
def barber_edit(barber_id):
    barber = get_barber_for_admin(barber_id)
    if barber is None:
        abort(404)

    if request.method == "POST":
        values = read_barber_form(request.form)
        service_ids, specialty_ids = read_barber_links(request.form)
        errors = check_barber_form(values)
        if errors:
            for message in errors:
                flash(message, "error")
            # Show the page again with the boxes still ticked
            return render_barber_edit(values, service_ids, specialty_ids)

        update_barber(barber_id, values["display_name"], values["bio"], values["barber_type"])
        set_barber_services(barber_id, service_ids)
        set_barber_specialties(barber_id, specialty_ids)
        flash("Barber saved.", "success")
        return redirect(url_for("admin.barbers"))

    values = {
        "display_name": barber["display_name"],
        "bio": barber["bio"] or "",
        "barber_type": barber["barber_type"],
    }
    return render_barber_edit(values,
                              get_barber_service_ids(barber_id),
                              get_barber_specialty_ids(barber_id))


@admin_bp.route("/barbers/<int:barber_id>/toggle", methods=["POST"])
@role_required("administrator")
def barber_toggle(barber_id):
    """Switch a barber on or off. We never delete barbers."""
    barber = get_barber_for_admin(barber_id)
    if barber is None:
        abort(404)

    now_active = not barber["is_active"]
    set_barber_active(barber_id, now_active)
    state = "active" if now_active else "inactive"
    flash(f"{barber['display_name']} is now {state}.", "success")
    return redirect(url_for("admin.barbers"))


# ---------------------------------------------------------------------------
# Barber weekly schedule (administrators only)
# ---------------------------------------------------------------------------

def read_time(text):
    """Turn text like '09:30' into a time. Returns None if it is not a valid time
    or if it is not on the hour or half hour (our appointment slots are 30 minutes)."""
    try:
        value = datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None
    if value.minute not in (0, 30):
        return None
    return value


def read_week_form(form):
    """Read the 7 rows of the schedule form (Monday to Sunday).
    Returns the week (so we can show it again if there is a mistake)
    and a list of error messages (empty = all good)."""
    week = []
    errors = []

    for number, day_name in enumerate(DAY_NAMES, start=1):
        working = form.get(f"working_{number}") == "on"   # a ticked box sends "on"
        start_text = form.get(f"start_{number}", "").strip()
        end_text = form.get(f"end_{number}", "").strip()

        if working:
            start = read_time(start_text)
            end = read_time(end_text)
            if start is None or end is None:
                errors.append(f"{day_name}: use times on the hour or half hour, like 09:00 or 09:30.")
            elif end <= start:
                errors.append(f"{day_name}: the end time must be after the start time.")
            else:
                # Clean text like "09:00", ready to save
                start_text = start.strftime("%H:%M")
                end_text = end.strftime("%H:%M")

        week.append({
            "number": number,
            "name": day_name,
            "working": working,
            "start": start_text,
            "end": end_text,
        })

    return week, errors


@admin_bp.route("/barbers/<int:barber_id>/schedule", methods=["GET", "POST"])
@role_required("administrator")
def barber_schedule(barber_id):
    barber = get_barber_for_admin(barber_id)
    if barber is None:
        abort(404)

    if request.method == "POST":
        week, errors = read_week_form(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin_barber_schedule.html", barber=barber, week=week)

        working_days = [(day["number"], day["start"], day["end"])
                        for day in week if day["working"]]
        set_barber_week(barber_id, working_days)
        flash(f"Schedule saved for {barber['display_name']}.", "success")
        return redirect(url_for("admin.barbers"))

    return render_template("admin_barber_schedule.html",
                           barber=barber, week=get_barber_week(barber_id))


# ---------------------------------------------------------------------------
# Accounts (administrators only)
# ---------------------------------------------------------------------------

STAFF_ROLES = ("staff", "administrator")


@admin_bp.route("/accounts")
@role_required("administrator")
def accounts():
    return render_template(
        "admin_accounts.html",
        staff=get_staff_for_admin(),
        customers=get_customers_for_admin(),
    )


@admin_bp.route("/accounts/<int:user_id>/toggle", methods=["POST"])
@role_required("administrator")
def account_toggle(user_id):
    """Switch an account on or off. We never delete accounts."""
    account = get_user_by_id(user_id)
    if account is None:
        abort(404)

    # Stops an administrator from locking themselves out.
    # It also means at least one active administrator always remains.
    if account["id"] == session["user_id"]:
        flash("You cannot switch off your own account.", "error")
        return redirect(url_for("admin.accounts"))

    now_active = not account["is_active"]
    set_user_active(user_id, now_active)
    state = "active" if now_active else "inactive"
    flash(f"{account['full_name']} is now {state}.", "success")
    return redirect(url_for("admin.accounts"))


def read_staff_form(form):
    """Read the add-staff form. The passwords are NOT kept here, so they are never shown again."""
    return {
        "full_name": form.get("full_name", "").strip(),
        "email": form.get("email", "").strip().lower(),
        "role": form.get("role", ""),
    }


def check_staff_form(values, password, confirm):
    """Check the form values. Returns a list of error messages (empty = all good)."""
    errors = []

    if len(values["full_name"]) < 2 or len(values["full_name"]) > 100:
        errors.append("Please enter the full name (2 to 100 characters).")

    email = values["email"]
    if "@" not in email or "." not in email or len(email) > 120:
        errors.append("Please enter a valid email address.")
    elif get_user_by_email(email):
        errors.append("That email is already registered.")

    if values["role"] not in STAFF_ROLES:
        errors.append("Please choose a role.")

    if len(password) < 8:
        errors.append("The password must be at least 8 characters.")
    elif password != confirm:
        errors.append("The two passwords do not match.")

    return errors


@admin_bp.route("/accounts/staff/new", methods=["GET", "POST"])
@role_required("administrator")
def staff_new():
    if request.method == "POST":
        values = read_staff_form(request.form)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = check_staff_form(values, password, confirm)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("admin_staff_form.html", values=values, roles=STAFF_ROLES)

        # Save the account with a HASHED password, like the register page does
        create_staff_account(values["full_name"], values["email"],
                             generate_password_hash(password), values["role"])
        flash(f"{values['role'].capitalize()} account created for {values['email']}.", "success")
        return redirect(url_for("admin.accounts"))

    values = {"full_name": "", "email": "", "role": "staff"}
    return render_template("admin_staff_form.html", values=values, roles=STAFF_ROLES)

# ---------------------------------------------------------------------------
# Feedback review (staff and administrators)
# ---------------------------------------------------------------------------

FEEDBACK_STATUSES = ("pending", "approved", "rejected")

# action name -> the new status
FEEDBACK_ACTIONS = {"approve": "approved", "reject": "rejected", "reset": "pending"}


@admin_bp.route("/feedback")
@role_required("administrator", "staff")
def feedback_review():
    status = request.args.get("status", "")
    if status not in FEEDBACK_STATUSES:
        status = ""   # anything else means "show all"

    return render_template(
        "admin_feedback.html",
        feedback=get_feedback_for_admin(status or None),
        current_status=status,
        statuses=FEEDBACK_STATUSES,
    )


@admin_bp.route("/feedback/<int:feedback_id>/<action>", methods=["POST"])
@role_required("administrator", "staff")
def feedback_action(feedback_id, action):
    """Approve, reject, or move feedback back to pending."""
    if action not in FEEDBACK_ACTIONS:
        abort(404)
    if get_feedback_by_id(feedback_id) is None:
        abort(404)

    new_status = FEEDBACK_ACTIONS[action]
    set_feedback_status(feedback_id, new_status)
    flash(f"Feedback marked as {new_status}.", "success")

    # Go back to the list with the same filter the person had
    back_to = request.form.get("status", "")
    if back_to not in FEEDBACK_STATUSES:
        back_to = None
    return redirect(url_for("admin.feedback_review", status=back_to))

# ---------------------------------------------------------------------------
# Delete (administrators only)
# ---------------------------------------------------------------------------

@admin_bp.route("/services/<int:service_id>/delete", methods=["POST"])
@role_required("administrator")
def service_delete(service_id):
    """Delete a service for good, but only if no appointment uses it."""
    service = get_service_for_admin(service_id)
    if service is None:
        abort(404)

    if count_appointments_for_service(service_id) > 0:
        flash(f"{service['name']} has appointments, so it cannot be deleted. "
              "Deactivate it instead.", "error")
    else:
        delete_service(service_id)
        flash(f"{service['name']} was deleted.", "success")
    return redirect(url_for("admin.services"))


@admin_bp.route("/barbers/<int:barber_id>/delete", methods=["POST"])
@role_required("administrator")
def barber_delete(barber_id):
    """Delete a barber for good, but only if they have no appointments."""
    barber = get_barber_for_admin(barber_id)
    if barber is None:
        abort(404)

    if count_appointments_for_barber(barber_id) > 0:
        flash(f"{barber['display_name']} has appointments, so they cannot be deleted. "
              "Deactivate them instead.", "error")
    else:
        delete_barber(barber_id)
        flash(f"{barber['display_name']} was deleted.", "success")
    return redirect(url_for("admin.barbers"))


@admin_bp.route("/faqs/<int:faq_id>/delete", methods=["POST"])
@role_required("administrator")
def faq_delete(faq_id):
    """Delete a FAQ for good."""
    faq = get_faq_for_admin(faq_id)
    if faq is None:
        abort(404)

    delete_faq(faq_id)
    flash("The FAQ was deleted.", "success")
    return redirect(url_for("admin.faqs"))