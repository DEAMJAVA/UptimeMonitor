import os

from flask import Flask

from config import Config
from models import init_db
from auth import auth_bp, login_manager
from monitors import monitors_bp
from checker import start_background_checker


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY

    init_db()

    login_manager.init_app(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(monitors_bp)

    if not Config.DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        start_background_checker()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
