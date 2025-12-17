from flask import Flask
from .config import Config
from .auth.routes import auth_bp
from .main.routes import main_bp
from .admin.routes import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    return app
