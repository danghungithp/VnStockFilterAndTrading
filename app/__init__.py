from pathlib import Path

from dotenv import load_dotenv
from flask import Flask


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config["JSON_SORT_KEYS"] = False

    from app.routes import register_routes

    register_routes(app)
    return app
