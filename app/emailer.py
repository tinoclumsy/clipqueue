import smtplib
from email.message import EmailMessage

from flask import current_app


class Mailer:
    """Sends emails through an SMTP server (Gmail by default).
    One Mailer object holds the server settings, and its methods send the emails."""

    def __init__(self, server, port, username, password):
        self.server = server
        self.port = port
        self.username = username
        self._password = password   # the leading underscore means: only this class should use it

    @classmethod
    def from_app(cls):
        """Build a Mailer from the settings in config.py (which come from .env)."""
        config = current_app.config
        return cls(config["MAIL_SERVER"], config["MAIL_PORT"],
                   config["MAIL_USERNAME"], config["MAIL_PASSWORD"])

    def is_ready(self):
        """True if the email login details were filled in."""
        return bool(self.username and self._password)

    def send(self, to_address, subject, body):
        """Send one plain-text email. Returns True if it was sent, False if not.
        A failed email never crashes the website. The reason goes to the terminal."""
        if not self.is_ready():
            current_app.logger.warning("Email not sent: MAIL_USERNAME or MAIL_PASSWORD is missing in .env")
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = f"ClipQueue <{self.username}>"
        message["To"] = to_address
        message.set_content(body)

        try:
            with smtplib.SMTP(self.server, self.port, timeout=15) as smtp:
                smtp.starttls()                          # turn on encryption
                smtp.login(self.username, self._password)
                smtp.send_message(message)
            return True
        except (smtplib.SMTPException, OSError) as error:
            current_app.logger.error("Email to %s failed: %s", to_address, error)
            return False

    def send_welcome(self, full_name, to_address):
        body = (
            f"Hi {full_name},\n\n"
            "Welcome to ClipQueue! Your account is ready.\n"
            "You can now log in, choose a service, and book your barber.\n\n"
            "See you soon,\n"
            "The ClipQueue team"
        )
        return self.send(to_address, "Welcome to ClipQueue", body)

    def send_booking_confirmation(self, full_name, to_address, appointment):
        """appointment is a dict with: reference, service_name, barber_name, date_label, time_label."""
        body = (
            f"Hi {full_name},\n\n"
            "We received your appointment request.\n\n"
            f"Reference: {appointment['reference']}\n"
            f"Service:   {appointment['service_name']}\n"
            f"Barber:    {appointment['barber_name']}\n"
            f"Date:      {appointment['date_label']}\n"
            f"Time:      {appointment['time_label']}\n\n"
            "Status: pending. We will email you again when the shop confirms it.\n\n"
            "The ClipQueue team"
        )
        return self.send(to_address, f"Your ClipQueue booking {appointment['reference']}", body)

    def send_status_update(self, full_name, to_address, appointment, new_status):
        """Tell the customer that staff changed the status of their appointment."""
        body = (
            f"Hi {full_name},\n\n"
            f"Your appointment {appointment['reference']} is now {new_status}.\n\n"
            f"Service:   {appointment['service_name']}\n"
            f"Barber:    {appointment['barber_name']}\n"
            f"Date:      {appointment['date_label']}\n"
            f"Time:      {appointment['time_label']}\n\n"
            "The ClipQueue team"
        )
        return self.send(to_address, f"Appointment {appointment['reference']} {new_status}", body)