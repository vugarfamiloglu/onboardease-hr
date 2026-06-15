"""Seed demo data (idempotent for a fresh DB)."""
import random
from datetime import date, datetime, timedelta

from flask import current_app

from .audit import audit, syslog
from .extensions import db
from .models import (Approval, AuditLog, Department, Document, DocumentVersion,
                     Employee, OnboardingTask, Position, TrainingModule,
                     TrainingSession, User)


class _Up:
    """Minimal file-like for the storage layer (has .read/.filename/.mimetype)."""
    def __init__(self, name, data, mime):
        self.filename, self._data, self.mimetype = name, data, mime

    def read(self):
        return self._data


def run_seed():
    cfg = current_app.config

    admin = User(name="Aytac Rahimova", email=cfg["SEED_ADMIN_EMAIL"], role="admin", color="#15795F")
    admin.set_password(cfg["SEED_ADMIN_PASSWORD"])
    manager = User(name="Elvin Mammadov", email="manager@onboardease.test", role="hr_manager", color="#C9772E")
    manager.set_password("onboard123")
    staff = User(name="Sevda Aliyeva", email="staff@onboardease.test", role="hr_staff", color="#3B6EA5")
    staff.set_password("onboard123")
    db.session.add_all([admin, manager, staff])

    dept_names = ["Engineering", "Design", "Marketing", "Sales", "Finance", "People Ops"]
    departments = {n: Department(name=n) for n in dept_names}
    db.session.add_all(departments.values())
    db.session.flush()

    position_map = {
        "Engineering": ["Backend Engineer", "Frontend Engineer", "DevOps Engineer"],
        "Design": ["Product Designer", "UX Researcher"],
        "Marketing": ["Content Strategist", "Growth Marketer"],
        "Sales": ["Account Executive", "SDR"],
        "Finance": ["Financial Analyst"],
        "People Ops": ["HR Generalist", "Recruiter"],
    }
    positions = []
    for dn, titles in position_map.items():
        for t in titles:
            p = Position(title=t, department_id=departments[dn].id)
            positions.append(p)
            db.session.add(p)

    modules = [
        TrainingModule(title="Company Orientation", category="Orientation", duration_hours=2,
                       description="Mission, values, org structure and your first week."),
        TrainingModule(title="Security Awareness", category="Compliance", duration_hours=1.5,
                       description="Phishing, passwords, data handling and incident reporting."),
        TrainingModule(title="Code of Conduct", category="Compliance", duration_hours=1,
                       description="Workplace policies, ethics and anti-harassment."),
        TrainingModule(title="Tools & Systems", category="IT", duration_hours=2,
                       description="Email, chat, ticketing and the internal toolchain."),
        TrainingModule(title="Product 101", category="Product", duration_hours=3,
                       description="What we build, who we serve and how it works."),
    ]
    db.session.add_all(modules)
    db.session.flush()

    first_names = ["Nigar", "Murad", "Lale", "Orxan", "Gunel", "Vusal", "Aysu", "Ramin", "Sabina", "Tofiq", "Aysel", "Kanan"]
    last_names = ["Huseynli", "Quliyev", "Abbasova", "Ismayilov", "Mammadli", "Hasanova", "Rzayev", "Kerimova", "Aliyev", "Babayeva"]
    statuses = ["documents", "documents", "review", "review", "approved", "training", "training", "active", "active", "active", "invited", "documents"]
    colors = ["#15795F", "#C9772E", "#3B6EA5", "#7C5CBF", "#C2453D", "#0E8A8A"]

    doc_types = [("contract", "Employment Contract", True), ("id", "National ID", True), ("resume", "Resume / CV", False)]

    for i in range(12):
        fn, ln = first_names[i], random.choice(last_names)
        pos = random.choice(positions)
        emp = Employee(
            first_name=fn, last_name=ln, email=f"{fn.lower()}.{ln.lower()}@newhire.test",
            phone=f"+994 5{random.randint(0,5)} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}",
            address=f"{random.randint(1,200)} Nizami St, Baku",
            date_of_birth=date(random.randint(1985, 2001), random.randint(1, 12), random.randint(1, 28)),
            national_id=f"AZE{random.randint(1000000, 9999999)}",
            position_id=pos.id, department_id=pos.department_id,
            manager_name=random.choice(["Elvin Mammadov", "Leyla Quliyeva", "Tural Hasanov"]),
            employment_type=random.choice(["Full-time", "Full-time", "Contract"]),
            start_date=date.today() + timedelta(days=random.randint(-30, 25)),
            status=statuses[i], color=random.choice(colors), created_by_id=staff.id,
            created_at=datetime.utcnow() - timedelta(days=random.randint(0, 40)),
        )
        db.session.add(emp)
        db.session.flush()

        # onboarding checklist (some done depending on stage)
        from .blueprints.employees import DEFAULT_CHECKLIST
        done_through = {"invited": 0, "documents": 3, "review": 6, "approved": 8, "training": 9, "active": 10}.get(emp.status, 2)
        for j, (title, cat) in enumerate(DEFAULT_CHECKLIST):
            db.session.add(OnboardingTask(employee_id=emp.id, title=title, category=cat,
                                          position=j, is_done=j < done_through))

        # documents (encrypted via the storage backend) for past-invited stages
        if emp.status != "invited":
            for dtype, dtitle, expires in random.sample(doc_types, k=random.randint(1, 3)):
                doc = Document(employee_id=emp.id, doc_type=dtype, title=dtitle,
                               status=random.choice(["pending", "approved", "approved"]),
                               expires_on=(date.today() + timedelta(days=random.choice([20, 120, 365]))) if expires else None,
                               created_by_id=staff.id)
                db.session.add(doc)
                db.session.flush()
                blob = f"%PDF-1.4 demo {dtitle} for {emp.full_name}\n".encode() + bytes(random.getrandbits(8) for _ in range(256))
                meta = current_app.storage.save(blob, f"{dtype}.pdf")
                db.session.add(DocumentVersion(document_id=doc.id, version_no=1, storage_key=meta["key"],
                                               original_filename=f"{dtype}.pdf", mime="application/pdf",
                                               size=meta["size"], sha256=meta["sha256"],
                                               uploaded_by_id=staff.id, note="Initial upload"))
                if doc.status == "pending":
                    db.session.add(Approval(employee_id=emp.id, document_id=doc.id, kind="document", status="pending"))

        # onboarding approval
        if emp.status in ("review", "documents", "invited"):
            db.session.add(Approval(employee_id=emp.id, kind="onboarding", status="pending"))
        else:
            db.session.add(Approval(employee_id=emp.id, kind="onboarding", status="approved",
                                    approver_id=manager.id, signature_name=manager.name,
                                    comment="All paperwork verified.", decided_at=datetime.utcnow()))

        # trainings for approved+ stages
        if emp.status in ("training", "active"):
            for mod in random.sample(modules, k=random.randint(2, 4)):
                completed = emp.status == "active" and random.random() > 0.4
                db.session.add(TrainingSession(
                    employee_id=emp.id, module_id=mod.id,
                    trainer_name=random.choice(["Elvin Mammadov", "Sevda Aliyeva", "External: ACME Learning"]),
                    scheduled_date=date.today() + timedelta(days=random.randint(-10, 12)),
                    status="completed" if completed else "scheduled",
                    completed_at=datetime.utcnow() if completed else None))

    db.session.commit()

    # a few log entries
    syslog("info", "system", "Database seeded with demo data")
    db.session.add(AuditLog(actor_name="system", action="created", entity_type="system",
                            summary="Seeded demo dataset", ip="127.0.0.1"))
    db.session.commit()
