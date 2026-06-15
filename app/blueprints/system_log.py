from flask import Blueprint, render_template, request
from flask_login import login_required

from ..decorators import role_required
from ..models import SystemLog

bp = Blueprint("system_log", __name__, url_prefix="/system")


@bp.route("/logs")
@login_required
@role_required("admin", "hr_manager")
def logs():
    level = request.args.get("level", "all")
    query = SystemLog.query
    if level != "all":
        query = query.filter_by(level=level)
    rows = query.order_by(SystemLog.created_at.desc()).limit(300).all()
    counts = {lv: SystemLog.query.filter_by(level=lv).count() for lv in ("info", "warn", "error", "debug")}
    return render_template("system/logs.html", rows=rows, level=level, counts=counts)
