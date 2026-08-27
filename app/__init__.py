import os

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import config


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return User.query.get(int(user_id))


def ensure_default_permissions():
    from app.models import Permission

    default_permissions = {
        "manage_business": "Manage business settings and profile",
        "manage_users": "Manage users and roles",
        "manage_products": "Create and update products and services",
        "manage_inventory": "Adjust product stock and inventory",
        "manage_sales": "Create and manage sales and invoices",
        "manage_purchases": "Create and manage purchases",
        "view_reports": "View dashboard and reports",
    }

    for code, description in default_permissions.items():
        if Permission.query.filter_by(code=code).first() is None:
            db.session.add(Permission(code=code, description=description))

    db.session.commit()


def create_app(config_name: str = None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "default")

    flask_app = Flask(__name__)
    flask_app.config.from_object(config.get(config_name, config["default"]))

    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp

    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(auth_bp)

    with flask_app.app_context():
        import app.models
        db.create_all()
        ensure_default_permissions()

    return flask_app
