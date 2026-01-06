from flask import Flask
from .config import Config
from .auth.routes import auth_bp
from .main.routes import main_bp
from .admin.routes import admin_bp
from .posts.routes import posts_bp
from app.context_processors import inject_permissions
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(posts_bp)

    app.context_processor(inject_permissions)

    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "..", "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    return app
