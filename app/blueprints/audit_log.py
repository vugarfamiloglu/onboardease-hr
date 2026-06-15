import csv
import io

from flask import Blueprint, Response, render_template, request
from flask_login import login_required

from ..decorators import role_required
from ..models import AuditLog

bp = Blueprint("audit_log", __name__, url_prefix="/audit")


@bp.route("/")
@login_required
@role_required("admin", "hr_manager")
def index():
    action = request.args.get("action", "all")
    entity = request.args.get("entity", "all")
    q = request.args.get("q", "").strip()

    query = AuditLog.query
    if action != "all":
        query = query.filter_by(action=action)
    if entity != "all":
        query = query.filter_by(entity_type=entity)
    if q:
        query = query.filter(AuditLog.summary.ilike(f"%{q}%"))

    logs = query.order_by(AuditLog.created_at.desc()).limit(300).all()
    actions = sorted({a[0] for a in AuditLog.query.with_entities(AuditLog.action).distinct()})
    entities = sorted({e[0] for e in AuditLog.query.with_entities(AuditLog.entity_type).distinct()})
    return render_template("audit/index.html", logs=logs, actions=actions, entities=entities,
                           action=action, entity=entity, q=q)


@bp.route("/export.csv")
@login_required
@role_required("admin", "hr_manager")
def export_csv():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["When", "Actor", "Action", "Entity", "Entity ID", "Detail", "IP"])
    for log in AuditLog.query.order_by(AuditLog.created_at.desc()).all():
        w.writerow([log.created_at, log.actor_name, log.action, log.entity_type,
                    log.entity_id, log.summary, log.ip])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=audit-log.csv"})
