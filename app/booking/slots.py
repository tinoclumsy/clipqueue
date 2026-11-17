from datetime import date, datetime, timedelta

from ..queries import format_time, get_busy_times, get_schedule_for_day

SLOT_STEP = 30   # a new possible start time every 30 minutes


def to_minutes(value):
    """MySQL gives a TIME as a timedelta. Turn it into minutes since midnight (9:00 -> 540)."""
    return int(value.total_seconds() // 60)


def minutes_to_label(minutes):
    """540 -> '9:00 AM'"""
    return format_time(timedelta(minutes=minutes))


def minutes_to_sql(minutes):
    """540 -> '09:00:00' (the format MySQL wants when saving a TIME)"""
    return f"{minutes // 60:02d}:{minutes % 60:02d}:00"


def get_free_slots(barber_id, service, the_date):
    """Return a list of free start times (in minutes) for this barber, service and date."""
    # 1. Working hours for that weekday. isoweekday(): Monday = 1 ... Sunday = 7
    schedule = get_schedule_for_day(barber_id, the_date.isoweekday())
    if schedule is None:
        return []   # day off

    work_start = to_minutes(schedule["start_time"])
    work_end = to_minutes(schedule["end_time"])
    length = service["duration_minutes"]

    # 2. Times that are already booked
    busy = [(to_minutes(row["start_time"]), to_minutes(row["end_time"]))
            for row in get_busy_times(barber_id, the_date)]

    # 3. If the date is today, hide times that have already started
    now_minutes = None
    if the_date == date.today():
        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute

    # 4. Walk through the working day and keep the slots that fit and don't overlap
    slots = []
    start = work_start
    while start + length <= work_end:
        end = start + length
        overlaps = any(start < busy_end and end > busy_start
                       for busy_start, busy_end in busy)
        already_started = now_minutes is not None and start <= now_minutes
        if not overlaps and not already_started:
            slots.append(start)
        start += SLOT_STEP

    return slots