import csv
import io
from datetime import datetime

from flask import (Blueprint, Response, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from ..audit import audit, syslog
from ..decorators import role_required
from ..extensions import db
from ..models import (AuditLog, Department, Employee, EMPLOYEE_STATUSES, OnboardingTask,
                      Position, Approval, STATUS_LABELS)

bp = Blueprint("employees", __name__, url_prefix="/employees")

DEFAULT_CHECKLIST = [
    ("Sign employment contract", "Paperwork"),
    ("Submit national ID / passport", "Paperwork"),
    ("Submit signed resume / CV", "Paperwork"),
    ("Provide bank & tax details", "Paperwork"),
    ("Create IT accounts & email", "IT"),
    ("Assign laptop & workstation", "IT"),
    ("Schedule orientation session", "Orientation"),
    ("Enroll in benefits & payroll", "HR"),
    ("Assign onboarding buddy", "HR"),
    ("Complete compliance training", "Training"),
]


def _date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    dept = request.args.get("department", "all")

    query = Employee.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Employee.first_name.ilike(like), Employee.last_name.ilike(like),
                                    Employee.email.ilike(like)))
    if status != "all":
        query = query.filter_by(status=status)
    if dept != "all":
        query = query.filter_by(department_id=int(dept))

    employees = query.order_by(Employee.created_at.desc()).all()
    return render_template("employees/list.html", employees=employees, q=q, status=status,
                           dept=dept, departments=Department.query.order_by(Department.name).all(),
                           statuses=EMPLOYEE_STATUSES, status_labels=STATUS_LABELS)


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    if request.method == "POST":
        f = request.form
        emp = Employee(
            first_name=f.get("first_name", "").strip(),
            last_name=f.get("last_name", "").strip(),
            email=f.get("email", "").strip().lower(),
            phone=f.get("phone", "").strip(),
            address=f.get("address", "").strip(),
            date_of_birth=_date(f.get("date_of_birth")),
            national_id=f.get("national_id", "").strip(),
            position_id=int(f["position_id"]) if f.get("position_id") else None,
            department_id=int(f["department_id"]) if f.get("department_id") else None,
            manager_name=f.get("manager_name", "").strip(),
            employment_type=f.get("employment_type", "Full-time"),
            start_date=_date(f.get("start_date")),
            status="documents",
            created_by_id=current_user.id,
        )
        if not emp.first_name or not emp.last_name or not emp.email:
            flash("First name, last name and email are required.", "error")
            return _render_form(emp)
        if Employee.query.filter_by(email=emp.email).first():
            flash("An employee with that email already exists.", "error")
            return _render_form(emp)

        db.session.add(emp)
        db.session.flush()
        for i, (title, cat) in enumerate(DEFAULT_CHECKLIST):
            db.session.add(OnboardingTask(employee_id=emp.id, title=title, category=cat, position=i))
        db.session.add(Approval(employee_id=emp.id, kind="onboarding", status="pending"))
        db.session.commit()

        audit("created", "employee", emp.id, f"Onboarded {emp.full_name}")
        syslog("info", "employees", f"New onboarding created: {emp.full_name}")
        flash(f"{emp.full_name} added to onboarding.", "success")
        return redirect(url_for("employees.detail", emp_id=emp.id))

    return _render_form(Employee(employment_type="Full-time"))


def _render_form(emp):
    return render_template("employees/form.html", emp=emp,
                           departments=Department.query.order_by(Department.name).all(),
                           positions=Position.query.order_by(Position.title).all())


@bp.route("/<int:emp_id>")
@login_required
def detail(emp_id):
    emp = db.session.get(Employee, emp_id) or abort(404)
    audit("viewed", "employee", emp.id, f"Viewed {emp.full_name}'s profile")
    trail = (AuditLog.query.filter_by(entity_type="employee", entity_id=emp.id)
             .order_by(AuditLog.created_at.desc()).limit(20).all())
    return render_template("employees/detail.html", emp=emp, trail=trail,
                           statuses=EMPLOYEE_STATUSES, status_labels=STATUS_LABELS)


@bp.route("/<int:emp_id>/status", methods=["POST"])
@login_required
def set_status(emp_id):
    emp = db.session.get(Employee, emp_id) or abort(404)
    status = request.form.get("status")
    if status in EMPLOYEE_STATUSES:
        emp.status = status
        db.session.commit()
        audit("edited", "employee", emp.id, f"Status → {STATUS_LABELS[status]}")
    return redirect(url_for("employees.detail", emp_id=emp.id))


@bp.route("/<int:emp_id>/task/<int:task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(emp_id, task_id):
    task = db.session.get(OnboardingTask, task_id) or abort(404)
    task.is_done = not task.is_done
    db.session.commit()
    audit("edited", "employee", emp_id, f"Checklist: {'done' if task.is_done else 'reopened'} — {task.title}")
    return redirect(url_for("employees.detail", emp_id=emp_id) + "#checklist")


@bp.route("/<int:emp_id>/task", methods=["POST"])
@login_required
def add_task(emp_id):
    emp = db.session.get(Employee, emp_id) or abort(404)
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(OnboardingTask(employee_id=emp.id, title=title,
                                      category=request.form.get("category", "General"),
                                      position=len(emp.tasks)))
        db.session.commit()
        audit("edited", "employee", emp.id, f"Added checklist item: {title}")
    return redirect(url_for("employees.detail", emp_id=emp_id) + "#checklist")


@bp.route("/export.csv")
@login_required
def export_csv():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Name", "Email", "Position", "Department", "Start date", "Status", "Progress %"])
    for e in Employee.query.order_by(Employee.last_name).all():
        w.writerow([e.full_name, e.email, e.position.title if e.position else "",
                    e.department.name if e.department else "", e.start_date or "",
                    e.status_label, e.progress])
    audit("downloaded", "report", None, "Exported employees CSV")
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=employees.csv"})
