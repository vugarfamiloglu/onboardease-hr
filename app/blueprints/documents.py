import io
from datetime import datetime

from flask import (Blueprint, abort, current_app, flash, redirect, request,
                   send_file, url_for)
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from ..audit import audit, syslog
from ..decorators import role_required
from ..extensions import db
from ..models import Approval, Document, DocumentVersion, Employee

bp = Blueprint("documents", __name__, url_prefix="/documents")


def _date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def _allowed(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _store_version(doc, file, note=""):
    data = file.read()
    meta = current_app.storage.save(data, file.filename)
    version_no = (max((v.version_no for v in doc.versions), default=0)) + 1
    db.session.add(DocumentVersion(
        document_id=doc.id, version_no=version_no, storage_key=meta["key"],
        original_filename=secure_filename(file.filename), mime=file.mimetype,
        size=meta["size"], sha256=meta["sha256"], uploaded_by_id=current_user.id, note=note,
    ))
    return version_no


@bp.route("/upload/<int:emp_id>", methods=["POST"])
@login_required
def upload(emp_id):
    emp = db.session.get(Employee, emp_id) or abort(404)
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("employees.detail", emp_id=emp_id) + "#documents")
    if not _allowed(file.filename):
        flash("That file type is not allowed.", "error")
        return redirect(url_for("employees.detail", emp_id=emp_id) + "#documents")

    doc = Document(
        employee_id=emp.id,
        doc_type=request.form.get("doc_type", "other"),
        title=request.form.get("title", "").strip() or file.filename,
        expires_on=_date(request.form.get("expires_on")),
        created_by_id=current_user.id,
    )
    db.session.add(doc)
    db.session.flush()
    _store_version(doc, file, note="Initial upload")
    # A document needs HR sign-off.
    db.session.add(Approval(employee_id=emp.id, document_id=doc.id, kind="document", status="pending"))
    db.session.commit()

    audit("uploaded", "document", doc.id, f"Uploaded '{doc.title}' (encrypted) for {emp.full_name}")
    syslog("info", "documents", f"Encrypted document stored via {current_app.storage.backend}",
           {"doc": doc.title, "employee": emp.full_name})
    flash(f"'{doc.title}' uploaded and encrypted at rest.", "success")
    return redirect(url_for("employees.detail", emp_id=emp_id) + "#documents")


@bp.route("/<int:doc_id>/version", methods=["POST"])
@login_required
def new_version(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    file = request.files.get("file")
    if not file or not file.filename or not _allowed(file.filename):
        flash("Choose a valid file.", "error")
        return redirect(url_for("employees.detail", emp_id=doc.employee_id) + "#documents")
    v = _store_version(doc, file, note=request.form.get("note", "").strip() or "New version")
    doc.status = "pending"
    db.session.commit()
    audit("edited", "document", doc.id, f"Uploaded version v{v} of '{doc.title}'")
    flash(f"New version (v{v}) uploaded.", "success")
    return redirect(url_for("employees.detail", emp_id=doc.employee_id) + "#documents")


@bp.route("/version/<int:version_id>/download")
@login_required
def download(version_id):
    version = db.session.get(DocumentVersion, version_id) or abort(404)
    doc = version.document
    try:
        data = current_app.storage.load(version.storage_key)
    except Exception:
        syslog("error", "documents", f"Failed to decrypt document {doc.id} v{version.version_no}")
        abort(500)
    audit("downloaded", "document", doc.id, f"Downloaded '{doc.title}' v{version.version_no}")
    return send_file(io.BytesIO(data), mimetype=version.mime or "application/octet-stream",
                     as_attachment=True, download_name=version.original_filename or "document")


@bp.route("/<int:doc_id>/decision", methods=["POST"])
@login_required
@role_required("admin", "hr_manager")
def decision(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    action = request.form.get("action")
    doc.status = "approved" if action == "approve" else "rejected"
    appr = Approval.query.filter_by(document_id=doc.id, kind="document", status="pending").first()
    if appr:
        appr.status = doc.status
        appr.approver_id = current_user.id
        appr.signature_name = current_user.name
        appr.comment = request.form.get("comment", "").strip()
        appr.decided_at = datetime.utcnow()
    db.session.commit()
    audit(doc.status, "document", doc.id, f"{doc.status.title()} '{doc.title}' (signed: {current_user.name})")
    flash(f"Document {doc.status}.", "success")
    return redirect(url_for("employees.detail", emp_id=doc.employee_id) + "#documents")


@bp.route("/<int:doc_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    emp_id = doc.employee_id
    for v in doc.versions:
        current_app.storage.delete(v.storage_key)
    db.session.delete(doc)
    db.session.commit()
    audit("deleted", "document", doc_id, f"Deleted document '{doc.title}'")
    flash("Document deleted.", "info")
    return redirect(url_for("employees.detail", emp_id=emp_id) + "#documents")
