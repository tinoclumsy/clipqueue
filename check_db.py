from app import create_app
from app.db import fetch_one

app = create_app()

# "app_context" lets code outside a web request use Flask's settings
with app.app_context():
    row = fetch_one("SELECT COUNT(*) AS total FROM services")
    print("Connected to MySQL successfully!")
    print("Services in the database:", row["total"])