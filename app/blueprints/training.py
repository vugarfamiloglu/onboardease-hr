from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..audit import audit
from ..extensions import db
from ..models import Employee, TrainingModule, TrainingSession

bp = Blueprint("training", __name__, url_prefix="/training")


def _date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


@bp.route("/")
@login_required
def index():
    modules = TrainingModule.query.order_by(TrainingModule.title).all()
    sessions = (TrainingSession.query.order_by(TrainingSession.scheduled_date).all())
    return render_template("training/index.html", modules=modules, sessions=sessions,
                           employees=Employee.query.order_by(Employee.first_name).all())


@bp.route("/modules", methods=["POST"])
@login_required
def create_module():
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(TrainingModule(
            title=title, description=request.form.get("description", "").strip(),
            category=request.form.get("category", "General"),
            duration_hours=float(request.form.get("duration_hours") or 1)))
        db.session.commit()
        audit("created", "training_module", None, f"Created training module '{title}'")
        flash("Training module created.", "success")
    return redirect(url_for("training.index"))


@bp.route("/sessions", methods=["POST"])
@login_required
def schedule():
    emp_id = request.form.get("employee_id")
    module_id = request.form.get("module_id")
    if not emp_id or not module_id:
        flash("Pick an employee and a module.", "error")
        return redirect(request.referrer or url_for("training.index"))
    session = TrainingSession(
        employee_id=int(emp_id), module_id=int(module_id),
        trainer_name=request.form.get("trainer_name", "").strip(),
        scheduled_date=_date(request.form.get("scheduled_date")), status="scheduled")
    db.session.add(session)
    # Moving into training implies the onboarding has progressed.
    emp = db.session.get(Employee, int(emp_id))
    if emp and emp.status == "approved":
        emp.status = "training"
    db.session.commit()
    audit("created", "training_session", session.id, f"Scheduled training for {emp.full_name if emp else emp_id}")
    flash("Training session scheduled.", "success")
    return redirect(request.referrer or url_for("training.index"))


@bp.route("/sessions/<int:session_id>/complete", methods=["POST"])
@login_required
def complete(session_id):
    session = db.session.get(TrainingSession, session_id) or abort(404)
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    db.session.commit()
    audit("edited", "training_session", session.id, "Marked training completed")
    flash("Training marked complete.", "success")
    return redirect(request.referrer or url_for("training.index"))
