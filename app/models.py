"""models.py - the main "things" of ClipQueue written as classes (OOP).

Each class wraps ONE row from the database and adds the rules and helpers that
belong to that thing. For example, a User knows its role, and an Appointment
knows which status changes are allowed.

OOP ideas used in this file:
  * Classes and objects: User, Appointment, Service, Barber, Feedback
  * Encapsulation:       the database data is kept in a private attribute (_data).
                         The password hash is kept in another private attribute and
                         can only be used through verify_password().
  * Inheritance:         every model inherits from BaseModel.
                         Customer and Staff inherit from User, and Administrator from Staff.
  * Polymorphism:        the user types answer the same questions in different ways
                         (home_endpoint(), can_manage_catalog()).
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from werkzeug.security import check_password_hash


class BaseModel:
    """The parent of every model. It holds one database row and gives easy access to it."""

    def __init__(self, data):
        self._data = dict(data)   # a private copy of the row

    @classmethod
    def from_row(cls, row):
        """Build an object from a database row. Returns None when there is no row."""
        if row is None:
            return None
        return cls(row)

    @property
    def id(self):
        return self._data.get("id")

    def to_dict(self):
        """A plain dictionary copy of the data."""
        return dict(self._data)

    # The three methods below make an object work like a dictionary too, so the
    # existing templates (a.service_name) and code (row["status"]) keep working.
    def __getattr__(self, name):
        # Python calls this only when the normal attribute lookup fails
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id}>"


# ---------------------------------------------------------------------------
# Users: Customer, Staff and Administrator
# ---------------------------------------------------------------------------

class User(BaseModel):
    """A person with an account. The three kinds are Customer, Staff and Administrator."""

    def __init__(self, data):
        super().__init__(data)
        # The password hash is kept in a private attribute and removed from the normal
        # data, so a template or to_dict() can never show it by accident.
        self._password_hash = self._data.pop("password_hash", None)

    @classmethod
    def from_row(cls, row):
        """Build the RIGHT kind of user (Customer, Staff or Administrator) from a row."""
        if row is None:
            return None
        if cls is not User:
            return cls(row)
        kinds = {"administrator": Administrator, "staff": Staff}
        return kinds.get(row.get("role"), Customer)(row)

    @property
    def full_name(self):
        return self._data["full_name"]

    @property
    def email(self):
        return self._data["email"]

    @property
    def role(self):
        return self._data["role"]

    @property
    def is_active(self):
        return bool(self._data["is_active"])

    @property
    def first_name(self):
        return self.full_name.split(" ")[0]

    def verify_password(self, typed_password):
        """True if the typed password matches the saved (hashed) one."""
        if not self._password_hash:
            return False
        return check_password_hash(self._password_hash, typed_password)

    def has_role(self, *roles):
        """True if this user's role is one of the given roles."""
        return self.role in roles

    # These two are answered differently by each kind of user (polymorphism)
    def home_endpoint(self):
        """The page this user lands on after logging in."""
        raise NotImplementedError("Each kind of user chooses its own home page.")

    def can_manage_catalog(self):
        """May this user add, edit and delete services, barbers, FAQs and accounts?"""
        return False


class Customer(User):
    def home_endpoint(self):
        return "auth.dashboard"


class Staff(User):
    def home_endpoint(self):
        return "admin.dashboard"


class Administrator(Staff):
    """An administrator is a Staff member who can also manage the catalog."""

    def can_manage_catalog(self):
        return True


# ---------------------------------------------------------------------------
# Appointment
# ---------------------------------------------------------------------------

class Appointment(BaseModel):
    """One booking. It knows which status changes are allowed."""

    # action name -> (the new status, the statuses it may change FROM)
    ACTIONS = {
        "confirm":  ("confirmed", ("pending",)),
        "complete": ("completed", ("confirmed",)),
        "cancel":   ("cancelled", ("pending", "confirmed")),
    }

    @property
    def status(self):
        return self._data["status"]

    @property
    def appointment_date(self):
        return self._data["appointment_date"]

    def is_upcoming(self, today=None):
        """Still active (pending or confirmed) and not in the past."""
        today = today or date.today()
        return self.status in ("pending", "confirmed") and self.appointment_date >= today

    def new_status_for(self, action):
        """The status an action leads to, or None if the action does not exist."""
        rule = self.ACTIONS.get(action)
        return rule[0] if rule else None

    def allowed_from_for(self, action):
        """The statuses an action may start from."""
        rule = self.ACTIONS.get(action)
        return rule[1] if rule else ()

    def action_error(self, action, today=None):
        """Why this action cannot be done now, as a message. None means it is allowed."""
        if action not in self.ACTIONS:
            return "That action does not exist."
        today = today or date.today()
        if action == "complete" and self.appointment_date > today:
            return "You can only complete an appointment on or after its date."
        if self.status not in self.allowed_from_for(action):
            return "That change is not allowed for this appointment."
        return None


# ---------------------------------------------------------------------------
# Service, Barber and Feedback
# (each one owns the validation rules for its own data)
# ---------------------------------------------------------------------------

class Service(BaseModel):
    """A service the shop offers, like a haircut or a beard trim."""

    @property
    def name(self):
        return self._data["name"]

    @property
    def price(self):
        return self._data["price"]

    @property
    def duration_minutes(self):
        return self._data["duration_minutes"]

    @property
    def is_active(self):
        return bool(self._data.get("is_active", 1))

    def price_label(self, symbol=""):
        """The price as text, like '250.00'."""
        return f"{symbol}{self.price:.2f}"

    def duration_label(self):
        """The duration as text, like '45 min' or '1 h 30 min'."""
        hours, minutes = divmod(self.duration_minutes, 60)
        if hours and minutes:
            return f"{hours} h {minutes} min"
        if hours:
            return f"{hours} h"
        return f"{minutes} min"

    @staticmethod
    def validate(values, name_taken=False):
        """Check the service form values (all text). Returns a list of error messages."""
        errors = []

        name = values["name"]
        if len(name) < 2 or len(name) > 100:
            errors.append("The name must be 2 to 100 characters.")
        elif name_taken:
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


class Barber(BaseModel):
    """A barber profile (barbers do not log in)."""

    TYPES = ("owner", "independent")

    @property
    def display_name(self):
        return self._data["display_name"]

    @property
    def barber_type(self):
        return self._data["barber_type"]

    def is_owner(self):
        return self.barber_type == "owner"

    @staticmethod
    def validate(values):
        """Check the barber form values (all text). Returns a list of error messages."""
        errors = []

        if len(values["display_name"]) < 2 or len(values["display_name"]) > 100:
            errors.append("The name must be 2 to 100 characters.")

        if len(values["bio"]) > 1000:
            errors.append("The bio is too long (maximum 1000 characters).")

        if values["barber_type"] not in Barber.TYPES:
            errors.append("Please choose a barber type.")

        return errors


class Feedback(BaseModel):
    """A customer's rating and comment about a completed appointment."""

    @property
    def rating(self):
        return self._data["rating"]

    def stars(self):
        """The rating as stars, like '★★★★☆'."""
        return "★" * self.rating + "☆" * (5 - self.rating)

    @staticmethod
    def validate(values):
        """Check the feedback form values (all text). Returns a list of error messages."""
        errors = []

        rating = values["rating"]
        if not rating.isdecimal() or not 1 <= int(rating) <= 5:
            errors.append("Please choose a rating from 1 to 5.")

        if len(values["comment"]) < 5 or len(values["comment"]) > 1000:
            errors.append("Your comment must be 5 to 1000 characters.")

        return errors