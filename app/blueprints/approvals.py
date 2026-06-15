from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..audit import audit, syslog
from ..decorators import role_required
from ..extensions import db
from ..models import Approval, Employee

bp = Blueprint("approvals", __name__, url_prefix="/approvals")


@bp.route("/")
@login_required
def index():
    pending = Approval.query.filter_by(status="pending").order_by(Approval.created_at).all()
    decided = (Approval.query.filter(Approval.status != "pending")
               .order_by(Approval.decided_at.desc()).limit(30).all())
    return render_template("approvals/index.html", pending=pending, decided=decided)


@bp.route("/<int:approval_id>/decision", methods=["POST"])
@login_required
@role_required("admin", "hr_manager")
def decision(approval_id):
    appr = db.session.get(Approval, approval_id) or abort(404)
    action = request.form.get("action")
    status = "approved" if action == "approve" else "rejected"

    appr.status = status
    appr.approver_id = current_user.id
    appr.signature_name = current_user.name  # e-signature
    appr.comment = request.form.get("comment", "").strip()
    appr.decided_at = datetime.utcnow()

    # Cascade the decision to the underlying entity.
    if appr.kind == "document" and appr.document:
        appr.document.status = status
        target = f"document '{appr.document.title}'"
    else:
        emp = appr.employee
        if emp:
            emp.status = "approved" if status == "approved" else "rejected"
        target = f"onboarding for {appr.employee.full_name if appr.employee else '—'}"

    db.session.commit()
    audit(status, "approval", appr.id, f"{status.title()} {target} — signed by {current_user.name}")
    syslog("info", "approvals", f"{status.title()}: {target}")
    flash(f"{target.capitalize()} {status}.", "success")
    return redirect(request.referrer or url_for("approvals.index"))
