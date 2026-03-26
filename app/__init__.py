from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dvf-gpt-dev-key")

    from app.routes.api import api_bp
    from app.routes.web import web_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    return app
