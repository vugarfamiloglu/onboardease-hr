"""SQLAlchemy models for OnboardEase HR."""
from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db

# Onboarding funnel stages (ordered).
EMPLOYEE_STATUSES = ["invited", "documents", "review", "approved", "training", "active", "rejected"]
STATUS_LABELS = {
    "invited": "Invited", "documents": "Collecting Docs", "review": "In Review",
    "approved": "Approved", "training": "In Training", "active": "Active", "rejected": "Rejected",
}


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="hr_staff")  # admin | hr_manager | hr_staff
    color = db.Column(db.String(7), default="#15795F")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def has_role(self, *roles):
        return self.role in roles

    @property
    def can_approve(self):
        return self.role in ("admin", "hr_manager")

    @property
    def initials(self):
        return "".join(p[0] for p in self.name.split()[:2]).upper()


class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)


class Position(db.Model):
    __tablename__ = "positions"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    department = db.relationship("Department")


class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    phone = db.Column(db.String(40))
    address = db.Column(db.String(255))
    date_of_birth = db.Column(db.Date)
    national_id = db.Column(db.String(60))
    position_id = db.Column(db.Integer, db.ForeignKey("positions.id"))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    manager_name = db.Column(db.String(120))
    employment_type = db.Column(db.String(40), default="Full-time")
    start_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="invited")
    color = db.Column(db.String(7), default="#15795F")
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    position = db.relationship("Position")
    department = db.relationship("Department")
    created_by = db.relationship("User")
    tasks = db.relationship("OnboardingTask", backref="employee", cascade="all, delete-orphan", order_by="OnboardingTask.position")
    documents = db.relationship("Document", backref="employee", cascade="all, delete-orphan")
    trainings = db.relationship("TrainingSession", backref="employee", cascade="all, delete-orphan")
    approvals = db.relationship("Approval", backref="employee", cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper()

    @property
    def status_label(self):
        return STATUS_LABELS.get(self.status, self.status.title())

    @property
    def masked_national_id(self):
        if not self.national_id:
            return "—"
        v = self.national_id
        return "•" * max(0, len(v) - 4) + v[-4:]

    @property
    def progress(self):
        total = len(self.tasks)
        if not total:
            return 0
        done = sum(1 for t in self.tasks if t.is_done)
        return round(done / total * 100)

    @property
    def stage_index(self):
        try:
            return EMPLOYEE_STATUSES.index(self.status)
        except ValueError:
            return 0


class OnboardingTask(db.Model):
    __tablename__ = "onboarding_tasks"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(60), default="General")
    is_done = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.Date)
    position = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    doc_type = db.Column(db.String(40), default="other")  # contract | id | resume | visa | certificate | other
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected
    expires_on = db.Column(db.Date)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    versions = db.relationship("DocumentVersion", backref="document", cascade="all, delete-orphan", order_by="DocumentVersion.version_no.desc()")

    @property
    def current(self):
        return self.versions[0] if self.versions else None

    @property
    def is_expiring(self):
        if not self.expires_on:
            return False
        return 0 <= (self.expires_on - date.today()).days <= 30

    @property
    def is_expired(self):
        return self.expires_on is not None and self.expires_on < date.today()


class DocumentVersion(db.Model):
    __tablename__ = "document_versions"
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))
    version_no = db.Column(db.Integer, default=1)
    storage_key = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    mime = db.Column(db.String(120))
    size = db.Column(db.Integer, default=0)
    sha256 = db.Column(db.String(64))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_by = db.relationship("User")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(255))


class TrainingModule(db.Model):
    __tablename__ = "training_modules"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(60), default="General")
    duration_hours = db.Column(db.Float, default=1)


class TrainingSession(db.Model):
    __tablename__ = "training_sessions"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    module_id = db.Column(db.Integer, db.ForeignKey("training_modules.id"))
    trainer_name = db.Column(db.String(120))
    scheduled_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="scheduled")  # scheduled | completed | missed
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    module = db.relationship("TrainingModule")

    @property
    def is_upcoming(self):
        return self.status == "scheduled" and self.scheduled_date and self.scheduled_date >= date.today()


class Approval(db.Model):
    __tablename__ = "approvals"
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"))
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"))
    kind = db.Column(db.String(20), default="onboarding")  # onboarding | document
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    approver = db.relationship("User")
    signature_name = db.Column(db.String(120))
    comment = db.Column(db.String(500))
    decided_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    document = db.relationship("Document")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor_name = db.Column(db.String(120))
    action = db.Column(db.String(40))  # viewed | created | edited | downloaded | uploaded | approved | rejected | deleted
    entity_type = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    summary = db.Column(db.String(255))
    ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SystemLog(db.Model):
    __tablename__ = "system_logs"
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(12), default="info")  # debug | info | warn | error
    source = db.Column(db.String(40))
    message = db.Column(db.String(500))
    meta = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
