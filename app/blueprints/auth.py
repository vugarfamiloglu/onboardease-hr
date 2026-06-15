from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..audit import audit
from ..models import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            audit("login", "user", user.id, f"{user.name} signed in")
            return redirect(request.args.get("next") or url_for("dashboard.index"))
        flash("Invalid email or password.", "error")
    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    audit("logout", "user", current_user.id, f"{current_user.name} signed out")
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))
