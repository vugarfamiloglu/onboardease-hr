"""OnboardEase HR — application factory."""
import click
from flask import Flask, render_template
from flask.cli import with_appcontext

from config import Config, DATA_DIR
from .extensions import db, login_manager, csrf
from .storage import build_storage


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    app.storage = build_storage(app.config, DATA_DIR)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    _register_blueprints(app)
    _register_context(app)
    _register_filters(app)
    _register_errors(app)
    _register_cli(app)

    return app


def _register_blueprints(app):
    from .blueprints import auth, dashboard, employees, documents, training, approvals, audit_log, system_log
    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(documents.bp)
    app.register_blueprint(training.bp)
    app.register_blueprint(approvals.bp)
    app.register_blueprint(audit_log.bp)
    app.register_blueprint(system_log.bp)


def _register_context(app):
    from flask_login import current_user
    from .models import Approval, Employee

    @app.context_processor
    def inject_globals():
        nav = {"pending_approvals": 0, "active_onboarding": 0}
        if current_user.is_authenticated:
            nav["pending_approvals"] = Approval.query.filter_by(status="pending").count()
            nav["active_onboarding"] = Employee.query.filter(Employee.status.notin_(["active", "rejected"])).count()
        return {"APP_NAME": app.config["APP_NAME"], "nav_counts": nav,
                "storage_backend": app.storage.backend}


def _register_filters(app):
    @app.template_filter("dt")
    def _dt(value, fmt="%b %d, %Y"):
        return value.strftime(fmt) if value else "—"

    @app.template_filter("dtime")
    def _dtime(value, fmt="%b %d, %Y · %H:%M"):
        return value.strftime(fmt) if value else "—"

    @app.template_filter("filesize")
    def _filesize(num):
        num = num or 0
        for unit in ("B", "KB", "MB", "GB"):
            if num < 1024:
                return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
            num /= 1024
        return f"{num:.1f} TB"


def _register_errors(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="You don't have permission to do that."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404


def _register_cli(app):
    @app.cli.command("init-db")
    @with_appcontext
    def init_db():
        """Create all tables."""
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("seed")
    @with_appcontext
    def seed_cmd():
        """Drop, recreate and seed the database with demo data."""
        from .seed import run_seed
        db.drop_all()
        db.create_all()
        run_seed()
        click.echo("Database seeded.")

    @app.cli.command("send-reminders")
    @click.option("--days", default=3)
    @with_appcontext
    def send_reminders_cmd(days):
        """Email reminders for upcoming trainings, expiring docs and pending approvals."""
        from .reminders import send_reminders
        result = send_reminders(days)
        click.echo(f"Sent {result['sent']} reminder(s): {result}")
