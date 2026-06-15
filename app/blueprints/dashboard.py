from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required
from sqlalchemy import func

from ..extensions import db
from ..models import (Approval, Document, Employee, EMPLOYEE_STATUSES, STATUS_LABELS,
                      TrainingSession)
from ..reminders import expiring_documents, pending_approvals, send_reminders, upcoming_trainings

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    total = Employee.query.count()
    active = Employee.query.filter_by(status="active").count()
    in_progress = Employee.query.filter(Employee.status.notin_(["active", "rejected"])).count()
    pending = Approval.query.filter_by(status="pending").count()

    kpis = {
        "total": total,
        "in_progress": in_progress,
        "active": active,
        "pending_approvals": pending,
        "documents": Document.query.count(),
        "trainings_scheduled": TrainingSession.query.filter_by(status="scheduled").count(),
    }

    # Onboarding funnel by status
    rows = dict(db.session.query(Employee.status, func.count(Employee.id)).group_by(Employee.status).all())
    funnel = [{"status": s, "label": STATUS_LABELS[s], "count": rows.get(s, 0)}
              for s in EMPLOYEE_STATUSES if s != "rejected"]

    # Documents by type (for the hover chart)
    doc_rows = dict(db.session.query(Document.doc_type, func.count(Document.id)).group_by(Document.doc_type).all())

    reminders = {
        "trainings": upcoming_trainings(7),
        "expiring": expiring_documents(),
        "approvals": pending_approvals(),
    }

    recent = Employee.query.order_by(Employee.created_at.desc()).limit(6).all()

    return render_template("dashboard/index.html", kpis=kpis, funnel=funnel,
                           doc_rows=doc_rows, reminders=reminders, recent=recent, today=date.today())


@bp.route("/reminders/run", methods=["POST"])
@login_required
def run_reminders():
    result = send_reminders(3)
    flash(f"Sent {result['sent']} reminder email(s) "
          f"({result['trainings']} trainings, {result['expiring_docs']} expiring docs, "
          f"{result['pending_approvals']} approvals).", "success")
    return redirect(url_for("dashboard.index"))
