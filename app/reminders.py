"""Deadline reminders: upcoming trainings, expiring documents, pending approvals."""
from datetime import date, timedelta

from .audit import syslog
from .mailer import send_mail
from .models import Approval, Document, Employee, TrainingSession, User


def upcoming_trainings(days=3):
    horizon = date.today() + timedelta(days=days)
    return (TrainingSession.query
            .filter(TrainingSession.status == "scheduled",
                    TrainingSession.scheduled_date >= date.today(),
                    TrainingSession.scheduled_date <= horizon)
            .order_by(TrainingSession.scheduled_date).all())


def expiring_documents(days=30):
    horizon = date.today() + timedelta(days=days)
    return (Document.query
            .filter(Document.expires_on.isnot(None),
                    Document.expires_on >= date.today(),
                    Document.expires_on <= horizon)
            .order_by(Document.expires_on).all())


def pending_approvals():
    return Approval.query.filter_by(status="pending").order_by(Approval.created_at).all()


def hr_recipients():
    return [u.email for u in User.query.filter(User.role.in_(["admin", "hr_manager"])).all()]


def send_reminders(days=3):
    trainings = upcoming_trainings(days)
    docs = expiring_documents()
    approvals = pending_approvals()
    sent = 0

    for s in trainings:
        emp = s.employee
        if emp and emp.email:
            send_mail(emp.email, f"Upcoming training: {s.module.title if s.module else 'Session'}",
                      f"Hi {emp.first_name},\n\nYou have '{s.module.title if s.module else 'a training'}' "
                      f"scheduled for {s.scheduled_date} with {s.trainer_name}.\n\n— OnboardEase HR")
            sent += 1

    hr = hr_recipients()
    if docs and hr:
        lines = "\n".join(f"- {d.title} ({d.employee.full_name if d.employee else '—'}) expires {d.expires_on}" for d in docs)
        for to in hr:
            send_mail(to, f"{len(docs)} document(s) expiring soon", f"The following documents expire within 30 days:\n\n{lines}\n\n— OnboardEase HR")
            sent += 1
    if approvals and hr:
        for to in hr:
            send_mail(to, f"{len(approvals)} approval(s) awaiting sign-off",
                      f"You have {len(approvals)} pending approval(s) in OnboardEase HR.\n\n— OnboardEase HR")
            sent += 1

    syslog("info", "reminders", f"Sent {sent} reminder email(s)",
           {"trainings": len(trainings), "expiring_docs": len(docs), "pending_approvals": len(approvals)})
    return {"sent": sent, "trainings": len(trainings), "expiring_docs": len(docs), "pending_approvals": len(approvals)}
