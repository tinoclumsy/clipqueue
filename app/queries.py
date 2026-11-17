from mysql.connector import IntegrityError

from .db import fetch_all, fetch_one, execute_write, execute_update, get_connection


# ===========================================================================
# PUBLIC PAGES: services, barbers, schedules
# ===========================================================================

def get_active_services():
    """Return all services that are turned on, A to Z."""
    sql = """
        SELECT id, name, description, price, duration_minutes
        FROM services
        WHERE is_active = 1
        ORDER BY name
    """
    return fetch_all(sql)


def get_active_barbers():
    """Return all active barbers, each with a text list of their specialties."""
    sql = """
        SELECT
            b.id,
            b.display_name,
            b.bio,
            b.barber_type,
            (
                SELECT GROUP_CONCAT(sp.name ORDER BY sp.name SEPARATOR ', ')
                FROM barber_specialties bs
                JOIN specialties sp ON sp.id = bs.specialty_id
                WHERE bs.barber_id = b.id
            ) AS specialties
        FROM barbers b
        WHERE b.is_active = 1
        ORDER BY b.display_name
    """
    return fetch_all(sql)


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]


def format_time(value):
    """MySQL gives a TIME as a 'timedelta' (time since midnight).
    Turn it into text like '9:00 AM'."""
    total_minutes = int(value.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    suffix = "AM" if hours < 12 else "PM"
    hour_12 = hours % 12 or 12
    return f"{hour_12}:{minutes:02d} {suffix}"


def get_barber_schedules():
    """Return each active barber with a Monday-to-Sunday week.
    A day with hours has text like '9:00 AM - 6:00 PM'; a day off has None."""
    barbers = fetch_all(
        "SELECT id, display_name FROM barbers WHERE is_active = 1 ORDER BY display_name"
    )
    rows = fetch_all(
        "SELECT barber_id, day_of_week, start_time, end_time FROM barber_schedules"
    )

    # Lookup table: (barber_id, day_number) -> "9:00 AM - 6:00 PM"
    hours = {}
    for row in rows:
        start = format_time(row["start_time"])
        end = format_time(row["end_time"])
        hours[(row["barber_id"], row["day_of_week"])] = f"{start} - {end}"

    result = []
    for barber in barbers:
        week = []
        for number, day_name in enumerate(DAY_NAMES, start=1):
            week.append({"day": day_name, "hours": hours.get((barber["id"], number))})
        result.append({
            "name": barber["display_name"],
            "week": week,
            "has_schedule": any(day["hours"] for day in week),
        })
    return result


# ===========================================================================
# ACCOUNTS
# ===========================================================================

def get_user_by_email(email):
    """Return the user with this email, or None. Used for login and to stop duplicate sign-ups."""
    sql = """
        SELECT id, full_name, email, password_hash, role, is_active
        FROM users
        WHERE email = %s
    """
    return fetch_one(sql, (email,))


def get_user_by_id(user_id):
    """Return the user with this id, or None. The password hash is left out on purpose."""
    sql = """
        SELECT id, full_name, email, role, is_active
        FROM users
        WHERE id = %s
    """
    return fetch_one(sql, (user_id,))


def create_customer(full_name, email, password_hash):
    """Save a new customer account and return its new id."""
    sql = """
        INSERT INTO users (full_name, email, password_hash, role)
        VALUES (%s, %s, %s, 'customer')
    """
    return execute_write(sql, (full_name, email, password_hash))


# ===========================================================================
# BOOKING (customer side)
# ===========================================================================

def get_service_by_id(service_id):
    """Return one active service, or None if it doesn't exist or is switched off."""
    sql = """
        SELECT id, name, description, price, duration_minutes
        FROM services
        WHERE id = %s AND is_active = 1
    """
    return fetch_one(sql, (service_id,))


def get_barbers_for_service(service_id):
    """Return the active barbers who offer this service."""
    sql = """
        SELECT b.id, b.display_name, b.bio, b.barber_type
        FROM barbers b
        JOIN barber_services bs ON bs.barber_id = b.id
        WHERE bs.service_id = %s AND b.is_active = 1
        ORDER BY b.display_name
    """
    return fetch_all(sql, (service_id,))


def _with_time_labels(row):
    """Add readable times like '9:00 AM' to an appointment row."""
    row["start_label"] = format_time(row["start_time"])
    row["end_label"] = format_time(row["end_time"])
    return row


def get_schedule_for_day(barber_id, day_of_week):
    """Return the barber's working hours for one weekday (1 = Monday), or None for a day off."""
    sql = """
        SELECT start_time, end_time
        FROM barber_schedules
        WHERE barber_id = %s AND day_of_week = %s
    """
    return fetch_one(sql, (barber_id, day_of_week))


def get_busy_times(barber_id, appointment_date):
    """Return the times already booked for this barber on this date (cancelled ones don't count)."""
    sql = """
        SELECT start_time, end_time
        FROM appointments
        WHERE barber_id = %s AND appointment_date = %s AND status <> 'cancelled'
    """
    return fetch_all(sql, (barber_id, appointment_date))


def count_bookings_on(barber_id, appointment_date):
    """How many (non-cancelled) appointments this barber has on this date."""
    sql = """
        SELECT COUNT(*) AS total
        FROM appointments
        WHERE barber_id = %s AND appointment_date = %s AND status <> 'cancelled'
    """
    return fetch_one(sql, (barber_id, appointment_date))["total"]


def create_appointment(reference, customer_id, barber_id, service_id,
                       appointment_date, start_time, end_time):
    """Save a new appointment with the status 'pending'. Returns its new id."""
    sql = """
        INSERT INTO appointments
            (booking_reference, customer_id, barber_id, service_id,
             appointment_date, start_time, end_time, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
    """
    return execute_write(sql, (reference, customer_id, barber_id, service_id,
                               appointment_date, start_time, end_time))


def get_appointment_by_reference(reference):
    """Return one appointment with its service and barber names, or None."""
    sql = """
        SELECT a.id, a.booking_reference, a.customer_id, a.appointment_date,
               a.start_time, a.end_time, a.status,
               s.name AS service_name, s.price,
               b.display_name AS barber_name
        FROM appointments a
        JOIN services s ON s.id = a.service_id
        JOIN barbers b ON b.id = a.barber_id
        WHERE a.booking_reference = %s
    """
    row = fetch_one(sql, (reference,))
    return _with_time_labels(row) if row else None


def get_customer_appointments(customer_id):
    """Return all appointments of one customer, newest first.
    Each one also has feedback_status: 'pending', 'approved', 'rejected',
    or None if the customer has not sent feedback for it."""
    sql = """
        SELECT a.id, a.booking_reference, a.appointment_date,
               a.start_time, a.end_time, a.status,
               s.name AS service_name, s.price,
               b.display_name AS barber_name,
               f.status AS feedback_status
        FROM appointments a
        JOIN services s ON s.id = a.service_id
        JOIN barbers b ON b.id = a.barber_id
        LEFT JOIN feedback f ON f.appointment_id = a.id
        WHERE a.customer_id = %s
        ORDER BY a.appointment_date DESC, a.start_time DESC
    """
    return [_with_time_labels(row) for row in fetch_all(sql, (customer_id,))]


def cancel_appointment(appointment_id, customer_id):
    """Cancel one of THIS customer's upcoming appointments. Returns 1 if it worked, 0 if not."""
    sql = """
        UPDATE appointments
        SET status = 'cancelled'
        WHERE id = %s AND customer_id = %s
          AND status IN ('pending', 'confirmed')
          AND appointment_date >= CURDATE()
    """
    return execute_update(sql, (appointment_id, customer_id))


# ===========================================================================
# ADMIN: dashboard and appointments
# ===========================================================================

def get_admin_counts():
    """Return the numbers shown on the admin dashboard cards."""
    sql = """
        SELECT
            (SELECT COUNT(*) FROM appointments
              WHERE appointment_date = CURDATE() AND status <> 'cancelled') AS today_total,
            (SELECT COUNT(*) FROM appointments
              WHERE status = 'pending' AND appointment_date >= CURDATE()) AS pending_total,
            (SELECT COUNT(*) FROM users
              WHERE role = 'customer' AND is_active = 1) AS customer_total,
            (SELECT COUNT(*) FROM barbers WHERE is_active = 1) AS barber_total
    """
    return fetch_one(sql)


def get_appointments_for_date(appointment_date):
    """Return all non-cancelled appointments on one date, earliest first."""
    sql = """
        SELECT a.id, a.booking_reference, a.start_time, a.end_time, a.status,
               u.full_name AS customer_name,
               s.name AS service_name,
               b.display_name AS barber_name
        FROM appointments a
        JOIN users u ON u.id = a.customer_id
        JOIN services s ON s.id = a.service_id
        JOIN barbers b ON b.id = a.barber_id
        WHERE a.appointment_date = %s AND a.status <> 'cancelled'
        ORDER BY a.start_time
    """
    return [_with_time_labels(row) for row in fetch_all(sql, (appointment_date,))]


def get_appointments_filtered(status=None, on_date=None, barber_id=None, include_past=False):
    """Return appointments for the admin list. Every filter is optional."""
    conditions = []
    params = []

    if status:
        conditions.append("a.status = %s")
        params.append(status)

    if on_date:
        conditions.append("a.appointment_date = %s")
        params.append(on_date)
    elif not include_past:
        conditions.append("a.appointment_date >= CURDATE()")   # hide past days by default

    if barber_id:
        conditions.append("a.barber_id = %s")
        params.append(barber_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # Only OUR fixed text goes into the SQL. The values go through %s placeholders.
    sql = f"""
        SELECT a.id, a.booking_reference, a.appointment_date,
               a.start_time, a.end_time, a.status,
               u.full_name AS customer_name,
               s.name AS service_name,
               b.display_name AS barber_name
        FROM appointments a
        JOIN users u ON u.id = a.customer_id
        JOIN services s ON s.id = a.service_id
        JOIN barbers b ON b.id = a.barber_id
        {where}
        ORDER BY a.appointment_date, a.start_time
        LIMIT 200
    """
    return [_with_time_labels(row) for row in fetch_all(sql, tuple(params))]


def get_appointment_by_id(appointment_id):
    """Return the basic details of one appointment, or None."""
    sql = """
        SELECT id, booking_reference, appointment_date, status
        FROM appointments
        WHERE id = %s
    """
    return fetch_one(sql, (appointment_id,))


def change_appointment_status(appointment_id, new_status, allowed_from):
    """Change the status, but only if it is currently one of the allowed ones.
    Returns 1 if it changed, 0 if not."""
    placeholders = ", ".join(["%s"] * len(allowed_from))   # e.g. "%s, %s"
    sql = f"""
        UPDATE appointments
        SET status = %s
        WHERE id = %s AND status IN ({placeholders})
    """
    return execute_update(sql, (new_status, appointment_id, *allowed_from))


# ===========================================================================
# ADMIN: manage services (9F)
# ===========================================================================

def get_all_services():
    """Return every service, active ones first. Used by the admin list."""
    sql = """
        SELECT id, name, description, price, duration_minutes, is_active
        FROM services
        ORDER BY is_active DESC, name
    """
    return fetch_all(sql)


def get_service_for_admin(service_id):
    """Return one service whether it is active or not, or None."""
    sql = """
        SELECT id, name, description, price, duration_minutes, is_active
        FROM services
        WHERE id = %s
    """
    return fetch_one(sql, (service_id,))


def service_name_taken(name, exclude_id=0):
    """True if ANOTHER service already has this name. exclude_id is the service being edited."""
    sql = "SELECT id FROM services WHERE name = %s AND id <> %s"
    return fetch_one(sql, (name, exclude_id)) is not None


def create_service(name, description, price, duration_minutes):
    """Add a new service. Returns its new id."""
    sql = """
        INSERT INTO services (name, description, price, duration_minutes)
        VALUES (%s, %s, %s, %s)
    """
    return execute_write(sql, (name, description or None, price, duration_minutes))


def update_service(service_id, name, description, price, duration_minutes):
    """Save changes to a service."""
    sql = """
        UPDATE services
        SET name = %s, description = %s, price = %s, duration_minutes = %s
        WHERE id = %s
    """
    return execute_update(sql, (name, description or None, price, duration_minutes, service_id))


def set_service_active(service_id, is_active):
    """Switch a service on (True) or off (False)."""
    sql = "UPDATE services SET is_active = %s WHERE id = %s"
    return execute_update(sql, (1 if is_active else 0, service_id))


# ===========================================================================
# ADMIN: manage barbers (9G-1)
# ===========================================================================

def get_all_barbers():
    """Every barber (active and inactive) for the admin Barbers page."""
    return fetch_all(
        "SELECT id, display_name, bio, barber_type, is_active "
        "FROM barbers ORDER BY is_active DESC, display_name",
        (),
    )


def get_barber_for_admin(barber_id):
    """One barber by id (active or not). Returns None if not found."""
    return fetch_one(
        "SELECT id, display_name, bio, barber_type, is_active "
        "FROM barbers WHERE id = %s",
        (barber_id,),
    )


def create_barber(display_name, bio, barber_type):
    execute_write(
        "INSERT INTO barbers (display_name, bio, barber_type) VALUES (%s, %s, %s)",
        (display_name, bio, barber_type),
    )


def update_barber(barber_id, display_name, bio, barber_type):
    execute_write(
        "UPDATE barbers SET display_name = %s, bio = %s, barber_type = %s WHERE id = %s",
        (display_name, bio, barber_type, barber_id),
    )


def set_barber_active(barber_id, active):
    execute_write(
        "UPDATE barbers SET is_active = %s WHERE id = %s",
        (1 if active else 0, barber_id),
    )


# ===========================================================================
# ADMIN: barber services and specialties (9G-2)
# ===========================================================================

def get_all_specialties():
    """Every specialty, A to Z. Used for the checkboxes."""
    return fetch_all("SELECT id, name FROM specialties ORDER BY name", ())


def get_barber_service_ids(barber_id):
    """The ids of the services this barber offers, as a set like {1, 3}."""
    rows = fetch_all(
        "SELECT service_id FROM barber_services WHERE barber_id = %s",
        (barber_id,),
    )
    return {row["service_id"] for row in rows}


def get_barber_specialty_ids(barber_id):
    """The ids of this barber's specialties, as a set like {2, 4}."""
    rows = fetch_all(
        "SELECT specialty_id FROM barber_specialties WHERE barber_id = %s",
        (barber_id,),
    )
    return {row["specialty_id"] for row in rows}


def set_barber_services(barber_id, service_ids):
    """Replace this barber's services with the new list.
    Step 1: delete the old rows. Step 2: insert the ticked ones.
    Both steps use ONE connection, so they are saved together (commit)
    or both undone if something goes wrong (rollback)."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM barber_services WHERE barber_id = %s", (barber_id,))
        for service_id in service_ids:
            cursor.execute(
                "INSERT INTO barber_services (barber_id, service_id) VALUES (%s, %s)",
                (barber_id, service_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def set_barber_specialties(barber_id, specialty_ids):
    """Same idea as set_barber_services, but for specialties."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM barber_specialties WHERE barber_id = %s", (barber_id,))
        for specialty_id in specialty_ids:
            cursor.execute(
                "INSERT INTO barber_specialties (barber_id, specialty_id) VALUES (%s, %s)",
                (barber_id, specialty_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


# ===========================================================================
# ADMIN: barber weekly schedule (9H)
# ===========================================================================

def time_to_input(value):
    """MySQL gives a TIME as a 'timedelta'. Turn it into text like '09:00',
    which is the format an <input type="time"> box understands."""
    total_minutes = int(value.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def get_barber_week(barber_id):
    """Return 7 days (Monday to Sunday) for the schedule form.
    Each day says if the barber works, and the start and end time as text.
    A day off gets the shop's usual 09:00 - 19:00 as a starting suggestion."""
    rows = fetch_all(
        "SELECT day_of_week, start_time, end_time "
        "FROM barber_schedules WHERE barber_id = %s",
        (barber_id,),
    )
    by_day = {row["day_of_week"]: row for row in rows}   # day number -> row

    week = []
    for number, day_name in enumerate(DAY_NAMES, start=1):
        row = by_day.get(number)
        week.append({
            "number": number,
            "name": day_name,
            "working": row is not None,
            "start": time_to_input(row["start_time"]) if row else "09:00",
            "end": time_to_input(row["end_time"]) if row else "19:00",
        })
    return week


def set_barber_week(barber_id, working_days):
    """Replace the barber's whole week.
    working_days is a list like [(1, "09:00", "17:00"), (2, "09:00", "17:00")]
    (day number, start, end). Days that are not in the list become days off.
    Delete and insert use ONE connection, so they are saved together or not at all."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM barber_schedules WHERE barber_id = %s", (barber_id,))
        for day_number, start, end in working_days:
            cursor.execute(
                "INSERT INTO barber_schedules (barber_id, day_of_week, start_time, end_time) "
                "VALUES (%s, %s, %s, %s)",
                (barber_id, day_number, start, end),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


# ===========================================================================
# ADMIN: accounts (9I)
# ===========================================================================

def get_customers_for_admin():
    """Every customer account (active first), with how many appointments each has made."""
    sql = """
        SELECT u.id, u.full_name, u.email, u.is_active, u.created_at,
               (SELECT COUNT(*) FROM appointments a WHERE a.customer_id = u.id) AS appointment_count
        FROM users u
        WHERE u.role = 'customer'
        ORDER BY u.is_active DESC, u.full_name
    """
    return fetch_all(sql)


def get_staff_for_admin():
    """Every staff and administrator account. Administrators come first."""
    sql = """
        SELECT id, full_name, email, role, is_active, created_at
        FROM users
        WHERE role IN ('administrator', 'staff')
        ORDER BY is_active DESC, role, full_name
    """
    return fetch_all(sql)


def set_user_active(user_id, is_active):
    """Switch an account on (True) or off (False). An off account cannot log in."""
    sql = "UPDATE users SET is_active = %s WHERE id = %s"
    return execute_update(sql, (1 if is_active else 0, user_id))


def create_staff_account(full_name, email, password_hash, role):
    """Save a new staff or administrator account and return its new id."""
    sql = """
        INSERT INTO users (full_name, email, password_hash, role)
        VALUES (%s, %s, %s, %s)
    """
    return execute_write(sql, (full_name, email, password_hash, role))


# ===========================================================================
# SHOP: status and info (Stage 10A)
# ===========================================================================

def get_shop_settings():
    """The one row of shop_settings (id = 1): open/closed, note, about text, contact info.
    Returns None if the row does not exist."""
    sql = """
        SELECT id, is_open, status_note, about_text, address, phone, email, hours_text
        FROM shop_settings
        WHERE id = 1
    """
    return fetch_one(sql)


def is_shop_open():
    """True if the shop is open. If the settings row is missing, we do not block anyone."""
    settings = get_shop_settings()
    if settings is None:
        return True
    return bool(settings["is_open"])


def set_shop_status(is_open, status_note):
    """Switch the shop open (True) or closed (False), with an optional short note."""
    sql = "UPDATE shop_settings SET is_open = %s, status_note = %s WHERE id = 1"
    return execute_update(sql, (1 if is_open else 0, status_note or None))


def update_shop_info(about_text, address, phone, email, hours_text):
    """Save the shop's about text and contact details."""
    sql = """
        UPDATE shop_settings
        SET about_text = %s, address = %s, phone = %s, email = %s, hours_text = %s
        WHERE id = 1
    """
    return execute_update(sql, (about_text or None, address or None, phone or None,
                                email or None, hours_text or None))


# ===========================================================================
# FAQs (Stage 10A shows them, Stage 10B manages them)
# ===========================================================================

def get_active_faqs():
    """The FAQs that are switched on, in the order the admin chose."""
    sql = """
        SELECT id, question, answer
        FROM faqs
        WHERE is_active = 1
        ORDER BY sort_order, id
    """
    return fetch_all(sql)


def get_all_faqs():
    """Every FAQ, shown ones first, then hidden ones. Used by the admin list."""
    sql = """
        SELECT id, question, answer, sort_order, is_active
        FROM faqs
        ORDER BY is_active DESC, sort_order, id
    """
    return fetch_all(sql)


def get_faq_for_admin(faq_id):
    """One FAQ whether it is shown or hidden, or None."""
    sql = """
        SELECT id, question, answer, sort_order, is_active
        FROM faqs
        WHERE id = %s
    """
    return fetch_one(sql, (faq_id,))


def get_next_faq_order():
    """The next free display order: the biggest one now, plus 10 (so a new FAQ goes last).
    COALESCE gives 0 when there are no FAQs yet, so the first one gets 10."""
    row = fetch_one("SELECT COALESCE(MAX(sort_order), 0) + 10 AS next_order FROM faqs")
    return int(row["next_order"])


def create_faq(question, answer, sort_order):
    """Add a new FAQ. Returns its new id."""
    sql = "INSERT INTO faqs (question, answer, sort_order) VALUES (%s, %s, %s)"
    return execute_write(sql, (question, answer, sort_order))


def update_faq(faq_id, question, answer, sort_order):
    """Save changes to a FAQ."""
    sql = "UPDATE faqs SET question = %s, answer = %s, sort_order = %s WHERE id = %s"
    return execute_update(sql, (question, answer, sort_order, faq_id))


def set_faq_active(faq_id, is_active):
    """Show (True) or hide (False) a FAQ on the Shop Info page."""
    sql = "UPDATE faqs SET is_active = %s WHERE id = %s"
    return execute_update(sql, (1 if is_active else 0, faq_id))


# ===========================================================================
# FEEDBACK (Stage 10C: customers send it. Stage 10D: staff review it)
# ===========================================================================

def get_appointment_for_feedback(appointment_id, customer_id):
    """Return one of THIS customer's COMPLETED appointments, or None.
    feedback_id is filled in if the customer already sent feedback for it."""
    sql = """
        SELECT a.id, a.booking_reference, a.appointment_date, a.barber_id,
               s.name AS service_name,
               b.display_name AS barber_name,
               (SELECT f.id FROM feedback f WHERE f.appointment_id = a.id) AS feedback_id
        FROM appointments a
        JOIN services s ON s.id = a.service_id
        JOIN barbers b ON b.id = a.barber_id
        WHERE a.id = %s AND a.customer_id = %s AND a.status = 'completed'
    """
    return fetch_one(sql, (appointment_id, customer_id))


def create_feedback(customer_id, appointment_id, barber_id, rating, comment):
    """Save new feedback as 'pending'. Returns True if it was saved.
    The table allows only ONE feedback per appointment. If it already exists,
    MySQL raises an IntegrityError and we return False instead of crashing."""
    sql = """
        INSERT INTO feedback (customer_id, appointment_id, barber_id, rating, comment)
        VALUES (%s, %s, %s, %s, %s)
    """
    try:
        execute_write(sql, (customer_id, appointment_id, barber_id, rating, comment))
    except IntegrityError:
        return False
    return True


def get_approved_feedback():
    """Approved feedback for the public Feedback page, newest first.
    Only the customer's FIRST name is kept, for privacy."""
    sql = """
        SELECT f.rating, f.comment, f.created_at,
               u.full_name AS customer_name,
               b.display_name AS barber_name,
               s.name AS service_name
        FROM feedback f
        JOIN users u ON u.id = f.customer_id
        LEFT JOIN barbers b ON b.id = f.barber_id
        LEFT JOIN appointments a ON a.id = f.appointment_id
        LEFT JOIN services s ON s.id = a.service_id
        WHERE f.status = 'approved'
        ORDER BY f.created_at DESC
        LIMIT 50
    """
    rows = fetch_all(sql)
    for row in rows:
        row["reviewer"] = row.pop("customer_name").split(" ")[0]
    return rows


def get_feedback_summary():
    """How many approved reviews there are, and their average rating (like 4.5)."""
    row = fetch_one(
        "SELECT COUNT(*) AS total, AVG(rating) AS average "
        "FROM feedback WHERE status = 'approved'"
    )
    average = round(float(row["average"]), 1) if row["average"] is not None else None
    return {"total": row["total"], "average": average}


def get_feedback_for_admin(status=None):
    """Feedback for the admin review page. Pending first, then newest first.
    Pass a status ('pending', 'approved' or 'rejected') to see only that kind."""
    where = "WHERE f.status = %s" if status else ""
    params = (status,) if status else ()

    sql = f"""
        SELECT f.id, f.rating, f.comment, f.status, f.created_at,
               u.full_name AS customer_name,
               b.display_name AS barber_name,
               s.name AS service_name,
               a.booking_reference
        FROM feedback f
        JOIN users u ON u.id = f.customer_id
        LEFT JOIN barbers b ON b.id = f.barber_id
        LEFT JOIN appointments a ON a.id = f.appointment_id
        LEFT JOIN services s ON s.id = a.service_id
        {where}
        ORDER BY FIELD(f.status, 'pending', 'approved', 'rejected'), f.created_at DESC
        LIMIT 200
    """
    return fetch_all(sql, params)


def get_feedback_by_id(feedback_id):
    """One feedback row, or None."""
    return fetch_one("SELECT id, status FROM feedback WHERE id = %s", (feedback_id,))


def set_feedback_status(feedback_id, new_status):
    """Approve or reject feedback ('approved', 'rejected' or back to 'pending')."""
    return execute_update("UPDATE feedback SET status = %s WHERE id = %s",
                          (new_status, feedback_id))

# ===========================================================================
# PROFILE (the logged-in person edits their own account)
# ===========================================================================

def update_user_profile(user_id, full_name, email):
    """Save a new name and email for one account."""
    sql = "UPDATE users SET full_name = %s, email = %s WHERE id = %s"
    return execute_update(sql, (full_name, email, user_id))


def get_user_password_hash(user_id):
    """The saved (hashed) password of one account, or None. Used to check the current password."""
    row = fetch_one("SELECT password_hash FROM users WHERE id = %s", (user_id,))
    return row["password_hash"] if row else None


def update_user_password(user_id, password_hash):
    """Save a new HASHED password."""
    sql = "UPDATE users SET password_hash = %s WHERE id = %s"
    return execute_update(sql, (password_hash, user_id))

# ===========================================================================
# DELETE (Stage: full CRUD)
# ===========================================================================

def count_appointments_for_service(service_id):
    """How many appointments use this service (any status)."""
    row = fetch_one("SELECT COUNT(*) AS total FROM appointments WHERE service_id = %s", (service_id,))
    return row["total"]


def count_appointments_for_barber(barber_id):
    """How many appointments this barber has (any status)."""
    row = fetch_one("SELECT COUNT(*) AS total FROM appointments WHERE barber_id = %s", (barber_id,))
    return row["total"]


def delete_service(service_id):
    """Delete a service for good. Only call this when it has no appointments."""
    return execute_update("DELETE FROM services WHERE id = %s", (service_id,))


def delete_barber(barber_id):
    """Delete a barber for good. Only call this when they have no appointments.
    Their schedule, services and specialties are removed automatically (ON DELETE CASCADE)."""
    return execute_update("DELETE FROM barbers WHERE id = %s", (barber_id,))


def delete_faq(faq_id):
    """Delete a FAQ for good."""
    return execute_update("DELETE FROM faqs WHERE id = %s", (faq_id,))

# ===========================================================================
# EMAIL (details for the status emails)
# ===========================================================================

def get_appointment_email_info(appointment_id):
    """Everything the status email needs about one appointment, or None."""
    sql = """
        SELECT a.booking_reference AS reference, a.start_time, a.end_time, a.appointment_date,
               u.full_name AS customer_name, u.email AS customer_email,
               s.name AS service_name,
               b.display_name AS barber_name
        FROM appointments a
        JOIN users u ON u.id = a.customer_id
        JOIN services s ON s.id = a.service_id
        JOIN barbers b ON b.id = a.barber_id
        WHERE a.id = %s
    """
    row = fetch_one(sql, (appointment_id,))
    if row is None:
        return None
    row["date_label"] = row["appointment_date"].strftime("%A, %d %B %Y")
    row["time_label"] = f"{format_time(row['start_time'])} - {format_time(row['end_time'])}"
    return row