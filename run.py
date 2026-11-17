import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Debug mode shows detailed errors. Turn it on in .env with FLASK_DEBUG=1.
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")