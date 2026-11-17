
# ClipQueue - Barbershop Digital Service Platform

ClipQueue is a web system for a barbershop. Customers can browse services, meet the barbers, check their working hours, book appointments online, and leave feedback. Staff and administrators manage the shop from an admin area.

- **Course:** IPT1, OOP, Web Systems and Technologies
- **School:** Laguna University
- **Team members:** Ludovice, Prince Justine D.

## Features

| # | Required feature | How ClipQueue does it |
|---|---|---|
| 1 | Logo and branding | Original scissors logo (SVG), browser tab icon, and a gold and charcoal theme |
| 2 | Home page | Public landing page with the shop's open or closed status |
| 3 | Registration | Customer sign-up with client and server validation, hashed password, and a welcome email |
| 4 | Login | Email and password login with friendly error messages |
| 5 | Web security | Password hashing, parameterized SQL (SQL injection), Jinja auto-escaping (XSS), CSRF tokens with Flask-WTF, security headers, and secrets in `.env` |
| 6 | Session management | Flask sessions, logout, protected pages, role checks, and deactivated accounts are logged out |
| 7 | SMTP email | A `Mailer` class sends emails through Gmail SMTP: welcome, booking received, and appointment confirmed or cancelled |
| 8 | Dashboard | A customer dashboard, and an admin dashboard with counts and today's appointments |
| 9 | Profile management | Users edit their name and email and change their password |
| 10 | Full CRUD | Services, barbers (with schedules, services and specialties), FAQs, accounts, shop info, appointments, and feedback review. Deleting is blocked when it would break appointment records. |
| 11 | Responsive UI | Custom responsive CSS: CSS grid, media queries, and a mobile menu with icons |
| 12 | Form validation | HTML5 rules, `validation.js` (inline messages, password strength, character counter), and server-side checks in Flask |
| 13 | OOP | `app/models.py`: `BaseModel`, `User` (`Customer`, `Staff`, `Administrator`), `Appointment`, `Service`, `Barber`, `Feedback`, plus the `Mailer` class |

## User roles

- **Customer:** registers, books and cancels appointments, leaves feedback, edits their profile.
- **Staff:** manages appointments, switches the shop open or closed, and reviews feedback.
- **Administrator:** everything staff can do, plus services, barbers, schedules, FAQs, shop info, and accounts.

## Tech stack

- Python 3 and Flask (Blueprints: `main`, `auth`, `booking`, `admin`)
- MySQL 8 with `mysql-connector-python`
- Flask-WTF (CSRF protection), Werkzeug (password hashing), python-dotenv (settings)
- HTML5, CSS3, and JavaScript (no frontend framework)

## Project structure

```text
ClipQueue/
|-- run.py                  starts the app
|-- config.py               settings (reads secrets from .env)
|-- create_staff.py         creates the first staff or administrator account
|-- test_email.py           checks the email settings
|-- requirements.txt        Python packages
|-- .env.example            example of the .env file (the real .env is not uploaded)
|-- database/
|   `-- schema.sql          creates all the tables
`-- app/
    |-- __init__.py         creates the app, CSRF, error pages, security headers
    |-- models.py           the OOP classes
    |-- queries.py          all database queries
    |-- db.py               database connection helpers
    |-- emailer.py          the Mailer class (SMTP)
    |-- main/               public pages
    |-- auth/               register, login, profile, dashboard, role checks
    |-- booking/             booking steps and free time slots
    |-- admin/              staff and administrator area
    |-- templates/          HTML pages
    `-- static/             CSS, JavaScript, images
```

## How to set up and run it locally

You need Python 3.10 or newer, MySQL 8, and Git.

**1. Get the code**

```bash
git clone https://github.com/tinoclumsy/clipqueue.git
cd clipqueue
```

**2. Create a virtual environment and install the packages**

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, use `source venv/bin/activate` instead of `venv\Scripts\activate`.

**3. Create the database and tables**

This **deletes and recreates** the ClipQueue tables, so only use it on an empty or test database.

```bash
mysql -u root -p -e "source database/schema.sql"
```

(You can also open `database/schema.sql` in MySQL Workbench and run it.)

**4. Create the database user**

Run this in MySQL, with your own password:

```sql
CREATE USER IF NOT EXISTS 'clipqueue_user'@'localhost' IDENTIFIED BY 'choose_a_database_password';
GRANT SELECT, INSERT, UPDATE, DELETE ON clipqueue_db.* TO 'clipqueue_user'@'localhost';
```

**5. Create the `.env` file**

Copy `.env.example` to a new file called `.env`, and fill in the values:

```bash
copy .env.example .env
```

- `DB_PASSWORD` is the password from step 4.
- `SECRET_KEY` must be at least 32 characters. Make one with:
  `python -c "import secrets; print(secrets.token_hex(32))"`
- `MAIL_USERNAME` and `MAIL_PASSWORD` are a Gmail address and a Gmail **App Password** (Google Account, Security, 2-Step Verification, App passwords). Emails are not sent if they are empty, but the site still works.

**6. Create the first administrator**

```bash
python create_staff.py
```

Choose the role `administrator`. Customers can register on the website. More staff can be added from the admin area.

**7. Run the app**

```bash
python run.py
```

Open http://127.0.0.1:5000 in your browser.

**Optional sample data:** run the sample file in the database folder (for example, services and barbers), or add them from the admin area.

## Security notes

- Passwords are stored as hashes, never as plain text.
- All SQL uses placeholders (`%s`), so user input is never added to the query text.
- Every form that changes data has a CSRF token.
- Secrets are only in `.env`, which is listed in `.gitignore`.
- Set `FLASK_DEBUG=0` for a demo to hide technical error pages.

## Credits

- Menu icons are drawn in the style of the open-source [Lucide](https://lucide.dev) icon set (ISC license).
